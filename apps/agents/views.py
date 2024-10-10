from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Crew, CrewExecution, CrewMessage, Pipeline, Agent  # Add Agent here
from .forms import CrewExecutionForm, HumanInputForm, AgentForm
from .tasks import execute_crew, resume_crew_execution
from django.core.exceptions import ValidationError
import logging
import json
from django.urls import reverse

logger = logging.getLogger(__name__)

@login_required
def crewai_home(request):
    crews = Crew.objects.all()[:3]  # Get the first 3 crews for the summary
    recent_executions = CrewExecution.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    context = {
        'crews': crews,
        'recent_executions': recent_executions,
    }
    return render(request, 'agents/crewai_home.html', context)

@login_required
def crew_list(request):
    logger.debug("Entering crew_list view")
    crews = Crew.objects.all()
    return render(request, 'agents/crew_list.html', {'crews': crews})

@login_required
def crew_detail(request, crew_id):
    crew = get_object_or_404(Crew, id=crew_id)
    recent_executions = CrewExecution.objects.filter(crew=crew).order_by('-created_at')[:5]
    
    if request.method == 'POST':
        form = CrewExecutionForm(request.POST)
        if form.is_valid():
            execution = form.save(commit=False)
            execution.crew = crew  # Set the crew here
            execution.user = request.user
            execution.inputs = form.cleaned_data.get('inputs') or {}
            execution.save()
            
            # Start the Celery task
            task = execute_crew.delay(execution.id)
            
            messages.success(request, 'Crew execution started successfully. You will be notified when it completes.')
            return JsonResponse({'redirect_url': reverse('agents:execution_detail', args=[execution.id]), 'execution_id': execution.id})
        else:
            return JsonResponse({'errors': form.errors}, status=400)
    else:
        form = CrewExecutionForm()
    
    context = {
        'crew': crew,
        'form': form,
        'recent_executions': recent_executions,
    }
    return render(request, 'agents/crew_detail.html', context)

@login_required
def execution_list(request):
    logger.debug("Entering execution_list view")
    executions = CrewExecution.objects.filter(user=request.user).order_by('-created_at')
    crews = Crew.objects.all()

    # Apply filters
    crew_id = request.GET.get('crew')
    status = request.GET.get('status')

    if crew_id:
        executions = executions.filter(crew_id=crew_id)
    if status:
        executions = executions.filter(status=status)

    # Pagination
    paginator = Paginator(executions, 10)  # Show 10 executions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'executions': page_obj,
        'crews': crews,
    }
    return render(request, 'agents/execution_list.html', context)

@login_required
def execution_detail(request, execution_id):
    logger.debug(f"Entering execution_detail view for execution_id: {execution_id}")
    execution = get_object_or_404(CrewExecution, id=execution_id, user=request.user)
    logger.info(f"Execution details: id={execution.id}, status={execution.status}, crew={execution.crew.name}")
    
    crew_messages = CrewMessage.objects.filter(execution=execution).order_by('timestamp')
    logger.info(f"Number of crew messages: {crew_messages.count()}")
    for message in crew_messages:
        logger.debug(f"Message: {message.content[:100]}...")  # Log first 100 characters of each message
    
    human_input_form = None
    if execution.status == 'WAITING_FOR_HUMAN_INPUT':
        human_input_form = HumanInputForm()
        logger.info("Human input form created")
    
    if execution.outputs:
        logger.info(f"Execution outputs: {json.dumps(execution.outputs)}")
    else:
        logger.info("No execution outputs available")

    context = {
        'execution': execution,
        'messages': crew_messages,
        'human_input_form': human_input_form,
    }
    logger.debug("Rendering execution_detail.html template")
    return render(request, 'agents/execution_detail.html', context)

@login_required
def execution_status(request, execution_id):
    try:
        execution = CrewExecution.objects.get(id=execution_id, user=request.user)
        recent_messages = CrewMessage.objects.filter(execution=execution).order_by('-timestamp')[:10]
        response_data = {
            'status': execution.status,
            'outputs': execution.outputs,
            'human_input_request': execution.human_input_request,
            'messages': [{'agent': msg.agent, 'content': msg.content} for msg in recent_messages],
        }
        return JsonResponse(response_data)
    except CrewExecution.DoesNotExist:
        return JsonResponse({'error': 'Execution not found'}, status=404)

@login_required
@require_POST
def submit_human_input(request, execution_id):
    logger.debug(f"Entering submit_human_input view for execution_id: {execution_id}")
    execution = get_object_or_404(CrewExecution, id=execution_id, user=request.user)
    
    if execution.status != 'WAITING_FOR_HUMAN_INPUT':
        logger.warning(f"Execution {execution_id} is not waiting for human input")
        messages.error(request, 'This execution is not waiting for human input.')
        return redirect('agents:execution_detail', execution_id=execution.id)

    form = HumanInputForm(request.POST)
    if form.is_valid():
        try:
            execution.human_input_response = form.cleaned_data['response']
            execution.status = 'RUNNING'
            execution.save()

            logger.info(f"Resuming Celery task for CrewExecution id: {execution.id}")
            # Resume the Celery task
            task = resume_crew_execution.delay(execution.id)
            logger.info(f"Celery task resumed with task id: {task.id}")

            messages.success(request, 'Human input submitted successfully. The execution will resume shortly.')
        except ValidationError as e:
            logger.error(f"Error saving human input for execution {execution_id}: {str(e)}")
            messages.error(request, f'Error saving human input: {str(e)}')
    else:
        logger.warning(f"Invalid human input form for execution {execution_id}. Errors: {form.errors}")
        messages.error(request, 'Invalid input. Please try again.')

    return redirect('agents:execution_detail', execution_id=execution.id)

@login_required
def manage_pipelines(request):
    pipelines = Pipeline.objects.all()
    context = {
        'pipelines': pipelines,
    }
    return render(request, 'agents/manage_pipelines.html', context)

@login_required
def manage_agents_card_view(request):
    agents = Agent.objects.prefetch_related('crew_set', 'task_set', 'tools').all()
    form = AgentForm()  # Create an instance of the form
    context = {
        'agents': agents,
        'form': form,  # Pass the form to the template
    }
    return render(request, 'agents/manage_agents_card_view.html', context)

@login_required
def manage_crews_card_view(request):
    crews = Crew.objects.all()
    context = {
        'crews': crews,
    }
    return render(request, 'agents/manage_crews_card_view.html', context)
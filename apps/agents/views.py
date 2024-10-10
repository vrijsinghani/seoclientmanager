from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import Crew, CrewExecution, CrewMessage, Pipeline, Agent  # Add Agent here
from .forms import CrewExecutionForm, HumanInputForm, AgentForm
from .tasks import execute_crew, resume_crew_execution
from django.core.exceptions import ValidationError
import logging
import json
from django.urls import reverse
from django.core.cache import cache

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
            execution.crew = crew
            execution.user = request.user
            execution.inputs = form.cleaned_data.get('inputs') or {}
            execution.save()
            
            # Start the Celery task
            execute_crew.delay(execution.id)
            
            # Return a JSON response
            return JsonResponse({
                'message': 'Crew execution started successfully',
                'execution_id': execution.id
            })
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
    execution = get_object_or_404(CrewExecution, id=execution_id, user=request.user)
    context = {
        'execution': execution,
    }
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
@csrf_exempt
@require_POST
def provide_human_input(request, execution_id):
    try:
        execution = CrewExecution.objects.get(id=execution_id, user=request.user)
        if execution.status != 'WAITING_FOR_HUMAN_INPUT':
            return JsonResponse({'error': 'Execution is not waiting for human input'}, status=400)

        data = json.loads(request.body)
        user_input = data.get('input')

        if not user_input:
            return JsonResponse({'error': 'No input provided'}, status=400)

        # Store the user input in the cache
        cache.set(f'human_input_response_{execution_id}', user_input, timeout=3600)

        # Update the execution status
        execution.status = 'RUNNING'
        execution.save()

        # Resume the Celery task
        resume_crew_execution.delay(execution_id)

        return JsonResponse({'message': 'Human input received and processing resumed'})
    except CrewExecution.DoesNotExist:
        return JsonResponse({'error': 'Execution not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in provide_human_input: {str(e)}")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)

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

def connection_test(request):
    return render(request, 'agents/connection_test.html')

@csrf_exempt
@require_http_methods(["POST"])
def provide_human_input(request, execution_id):
    try:
        execution = CrewExecution.objects.get(id=execution_id)
        data = json.loads(request.body)
        user_input = data.get('input')
        
        if not user_input:
            return JsonResponse({'error': 'No input provided'}, status=400)
        
        execution.human_input_response = user_input
        execution.save()
        
        # Resume the execution
        resume_crew_execution.delay(execution_id)
        
        return JsonResponse({'status': 'success', 'message': 'Input received and execution resumed'})
    except CrewExecution.DoesNotExist:
        return JsonResponse({'error': 'Execution not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
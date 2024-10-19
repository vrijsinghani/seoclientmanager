from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from .models import Crew, CrewExecution, CrewMessage, Pipeline, Agent
from .forms import CrewExecutionForm, HumanInputForm, AgentForm
from .tasks import execute_crew
from django.core.exceptions import ValidationError
import logging
import json
from django.urls import reverse
from django.core.cache import cache
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
import os
from apps.seo_manager.models import Client  # Import the Client model

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()

@login_required
def crewai_home(request):
    crews = Crew.objects.all()[:3]  # Get the first 3 crews for the summary
    recent_executions = CrewExecution.objects.filter(user=request.user).order_by('-created_at')[:5]
    clients = Client.objects.all()  # Get all clients
    
    # Get the selected client_id from the request, fallback to session
    selected_client_id = request.GET.get('client_id') or request.session.get('selected_client_id')
    
    if selected_client_id:
        request.session['selected_client_id'] = selected_client_id
    else:
        # If no client is selected, remove it from the session
        request.session.pop('selected_client_id', None)
    
    context = {
        'crews': crews,
        'recent_executions': recent_executions,
        'clients': clients,
        'selected_client_id': selected_client_id,
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
    
    # Get the selected client_id from the session
    selected_client_id = request.session.get('selected_client_id')
    selected_client = None
    if selected_client_id:
        selected_client = get_object_or_404(Client, id=selected_client_id)
    
    if request.method == 'POST':
        form = CrewExecutionForm(request.POST)
        if form.is_valid():
            execution = form.save(commit=False)
            execution.crew = crew
            execution.user = request.user
            execution.client = selected_client  # Associate the selected client with the execution
            
            # Handle input variables
            input_variables = json.loads(request.POST.get('input_variables', '{}'))
            execution.inputs = input_variables
            
            execution.save()
            
            # Start the execution
            execute_crew.delay(execution.id)
            
            messages.success(request, 'Crew execution started.')
            return JsonResponse({'status': 'success', 'execution_id': execution.id})
    else:
        form = CrewExecutionForm()
    
    context = {
        'crew': crew,
        'form': form,
        'recent_executions': recent_executions,
        'selected_client': selected_client,
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
@csrf_protect
@require_POST
def provide_human_input(request, execution_id):
    try:
        execution = CrewExecution.objects.get(id=execution_id, user=request.user)
        if execution.status != 'WAITING_FOR_HUMAN_INPUT':
            return JsonResponse({'error': 'Execution is not waiting for human input'}, status=400)

        data = json.loads(request.body)
        user_input = data.get('input')

        if user_input is None:
            return JsonResponse({'error': 'No input provided'}, status=400)

        # Store the user input in the cache
        cache.set(f'human_input_response_{execution_id}', user_input, timeout=3600)

        logger.info(f"Stored user input for execution {execution_id}: {user_input}")

        # Update execution status
        execution.status = 'RUNNING'
        execution.save()

        # Send a WebSocket message to update the frontend
        async_to_sync(channel_layer.group_send)(
            f'crew_execution_{execution_id}',
            {
                'type': 'crew_execution_update',
                'status': 'RUNNING',
                'messages': [{'agent': 'Human', 'content': f'Input provided: {user_input}'}],
            }
        )

        # Return the actual user input
        return JsonResponse({'message': 'Human input received and processing resumed', 'input': user_input})
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
    form = AgentForm()  # Now AgentForm is defined
    context = {
        'agents': agents,
        'form': form,
    }
    return render(request, 'agents/manage_agents_card_view.html', context)

@login_required
def manage_crews(request):
    crews = Crew.objects.all()
    
    # Get the selected client_id from the session
    selected_client_id = request.session.get('selected_client_id')
    selected_client = None
    
    if selected_client_id:
        selected_client = get_object_or_404(Client, id=selected_client_id)
        # Optionally, you can filter crews by the selected client if there's a relationship
        # crews = crews.filter(client=selected_client)
    
    context = {
        'crews': crews,
        'selected_client': selected_client,
    }
    return render(request, 'agents/manage_crews.html', context)

@login_required
def manage_crews_card_view(request):
    crews = Crew.objects.all()
    
    # Get the selected client_id from the session
    selected_client_id = request.session.get('selected_client_id')
    selected_client = None
    
    if selected_client_id:
        selected_client = get_object_or_404(Client, id=selected_client_id)
        # Optionally, you can filter crews by the selected client if there's a relationship
        # crews = crews.filter(client=selected_client)
    
    context = {
        'crews': crews,
        'selected_client': selected_client,
    }
    return render(request, 'agents/manage_crews_card_view.html', context)

def connection_test(request):
    return render(request, 'agents/connection_test.html')@csrf_exempt

@login_required
@require_POST
def submit_human_input(request, execution_id):
    input_key = request.POST.get('input_key')
    response = request.POST.get('response')
    
    if not input_key or not response:
        return JsonResponse({'error': 'Missing input_key or response'}, status=400)
    
    execution = get_object_or_404(CrewExecution, id=execution_id, user=request.user)
    
    # Store the response in the cache
    cache_key = f"{input_key}_response"
    cache.set(cache_key, response, timeout=3600)
    
    # Verify that the input was stored correctly
    stored_value = cache.get(cache_key)
    logger.info(f"Stored human input in cache for execution {execution_id}: key={cache_key}, value={response}")
    logger.info(f"Verified stored value: {stored_value}")
    
    # Create a CrewMessage for the human input
    CrewMessage.objects.create(
        execution=execution,
        agent='Human',
        content=f"Human input received: {response}"
    )
    
    # Notify the WebSocket that human input has been received
    async_to_sync(channel_layer.group_send)(
        f'crew_execution_{execution_id}',
        {
            'type': 'crew_execution_update',
            'status': 'RUNNING',
            'messages': [{'agent': 'Human', 'content': f'Input provided: {response}'}],
        }
    )
    
    return JsonResponse({'message': 'Human input received and processed'})

def task_create_or_update(request, task_id=None):
    # ... existing view code ...

    if form.is_valid():
        task = form.save(commit=False)
        
        # Handle the output_file path
        output_file_path = form.cleaned_data['output_file']
        if output_file_path:
            # Ensure the path is relative to MEDIA_ROOT
            full_path = os.path.join(settings.MEDIA_ROOT, output_file_path)
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Create an empty file if it doesn't exist
            if not os.path.exists(full_path):
                open(full_path, 'a').close()
            
            # Save the relative path to the model
            task.output_file = output_file_path

        task.save()
        # ... rest of your view logic ...

    # ... rest of your view ...

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
import json

from .models import Crew, CrewExecution, ExecutionStage, Task, Agent, CrewTask
from apps.seo_manager.models import Client

@login_required
def crew_kanban(request, crew_id):
    crew = get_object_or_404(Crew, id=crew_id)
    client_id = request.GET.get('client_id')
    client = get_object_or_404(Client, id=client_id) if client_id else None
    
    # Get all tasks for this crew through CrewTask
    crew_tasks = CrewTask.objects.filter(crew=crew).select_related('task')
    kanban_tasks = []
    
    for crew_task in crew_tasks:
        task = crew_task.task
        # Get executions that are associated with this task
        executions = CrewExecution.objects.filter(
            crew=crew,
            task=task
        ).prefetch_related('stages')
        
        execution_data = []
        for execution in executions:
            stages = execution.stages.all()
            stage_data = {}
            
            for stage in stages:
                stage_data[stage.stage_type] = {
                    'title': stage.title,
                    'content': stage.content,
                    'status': stage.status,
                    'agent': stage.agent.name if stage.agent else None
                }
                
                # Add stage-specific metadata
                if stage.metadata:
                    stage_data[stage.stage_type].update(stage.metadata)
            
            execution_data.append({
                'id': execution.id,
                'name': f'Execution #{execution.id}',
                'status': execution.status,
                'stages': stage_data
            })
        
        kanban_tasks.append({
            'id': task.id,
            'name': task.description,
            'executions': execution_data
        })
    
    return render(request, 'agents/crew_kanban.html', {
        'crew': crew,
        'client': client,
        'tasks': kanban_tasks
    })

@login_required
@require_http_methods(['POST'])
@csrf_protect
def start_execution(request, crew_id):
    crew = get_object_or_404(Crew, id=crew_id)
    
    try:
        data = json.loads(request.body)
        client_id = data.get('client_id')
            
        if not client_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Client ID is required'
            }, status=400)
            
        client = get_object_or_404(Client, id=client_id)
        
        # Get the first task for this crew
        crew_task = CrewTask.objects.filter(crew=crew).order_by('order').first()
        if not crew_task:
            return JsonResponse({
                'status': 'error',
                'message': 'No tasks found for this crew'
            }, status=400)
        
        # Create new execution
        execution = CrewExecution.objects.create(
            crew=crew,
            status='PENDING',
            inputs={
                'client_id': client_id
            },
            user=request.user,
            client=client
        )
        
        # Create initial stage
        stage = ExecutionStage.objects.create(
            execution=execution,
            stage_type='task_start',
            title='Starting New Execution',
            content='Initializing crew execution workflow',
            status='pending'
        )
        
        # Start the Celery task
        from .tasks import execute_crew
        task = execute_crew.delay(execution.id)
        
        # Update execution with task_id immediately
        execution.task_id = task.id
        execution.save()
        
        # Notify WebSocket clients
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'crew_{crew_id}_kanban',
            {
                'type': 'execution_update',
                'execution_id': execution.id,
                'task_id': crew_task.task.id,  # Send the task ID for proper board placement
                'status': 'PENDING',
                'message': 'New execution started',
                'stage': {
                    'stage_type': 'task_start',
                    'title': 'Starting New Execution',
                    'content': 'Initializing crew execution workflow',
                    'status': 'pending'
                }
            }
        )
        
        return JsonResponse({
            'status': 'success',
            'execution_id': execution.id,
            'task_id': crew_task.task.id
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error starting execution: {str(e)}', exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(['GET'])
def get_active_executions(request, crew_id):
    """Get all active executions for a crew"""
    crew = get_object_or_404(Crew, id=crew_id)
    
    # Get all in-progress executions for this crew
    executions = CrewExecution.objects.filter(
        crew=crew,
        status__in=['pending', 'in_progress']
    ).prefetch_related('stages')
    
    execution_data = []
    for execution in executions:
        stages = execution.stages.all()
        stage_data = {}
        
        for stage in stages:
            stage_data[stage.stage_type] = {
                'title': stage.title,
                'content': stage.content,
                'status': stage.status,
                'agent': stage.agent.name if stage.agent else None
            }
            
            if stage.metadata:
                stage_data[stage.stage_type].update(stage.metadata)
        
        execution_data.append({
            'execution_id': execution.id,
            'task_id': execution.task_id if hasattr(execution, 'task_id') else None,
            'name': f'Execution #{execution.id}',
            'status': execution.status,
            'stages': stage_data
        })
    
    return JsonResponse({'executions': execution_data})

@login_required
@require_http_methods(['POST'])
@csrf_protect
def submit_human_input(request, execution_id):
    execution = get_object_or_404(CrewExecution, id=execution_id)
    
    try:
        data = json.loads(request.body)
        input_text = data.get('input')
        
        if not input_text:
            return JsonResponse({
                'status': 'error',
                'message': 'Input text is required'
            }, status=400)
        
        # Update execution with human input
        execution.human_input_response = {'input': input_text}
        execution.status = 'RUNNING'
        execution.save()
        
        # Create human input stage
        stage = ExecutionStage.objects.create(
            execution=execution,
            stage_type='human_input',
            title='Human Input Received',
            content=input_text,
            status='completed',
            metadata={
                'input_timestamp': timezone.now().isoformat()
            }
        )
        
        # Notify WebSocket clients
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'crew_{execution.crew.id}_kanban',
            {
                'type': 'stage_update',
                'execution_id': execution.id,
                'stage_type': 'human_input',
                'stage_data': {
                    'title': stage.title,
                    'content': stage.content,
                    'status': stage.status,
                    'completed': True
                }
            }
        )
        
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
import logging
import time
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from apps.agents.models import CrewMessage, CrewExecution, Task
from ..handlers.websocket import send_message_to_websocket

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()

def log_crew_message(execution, content, agent=None, human_input_request=None, task_id=None):
    try:
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                async_to_sync(channel_layer.group_send)(
                    f"crew_execution_{execution.id}",
                    {
                        "type": "crew_execution_update",
                        "status": execution.status,
                        "messages": [{"agent": agent or "System", "content": content}],
                        "human_input_request": human_input_request,
                        "task_id": task_id
                    }
                )
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to send WebSocket message after {max_retries} attempts: {str(e)}")
                else:
                    logger.warning(f"WebSocket send attempt {attempt + 1} failed, retrying in {retry_delay}s: {str(e)}")
                    time.sleep(retry_delay)
        
        # Log message to database
        if content:  # Only create a message if there's content
            message = CrewMessage.objects.create(execution=execution, content=content, agent=agent)
            logger.debug(f"Sent message to WebSocket: {content[:100]}")
        else:
            logger.warning("Attempted to log an empty message, skipping.")
    except Exception as e:
        logger.error(f"Error in log_crew_message: {str(e)}")

def update_execution_status(execution, status, message=None, task_id=None):
    """Update execution status and send WebSocket message"""
    execution.status = status
    execution.save()
    
    # Use the provided task_id if available, otherwise get the current task
    crewai_task_id = task_id
    if not crewai_task_id:
        current_task = Task.objects.filter(crew_execution=execution).first()
        crewai_task_id = current_task.id if current_task else None
    
    # Create properly formatted event
    event = {
        'type': 'execution_update',
        'execution_id': execution.id,
        'status': status,
        'message': message,
        'crewai_task_id': crewai_task_id,
        'stage': {
            'stage_type': 'status_update',
            'title': 'Status Update',
            'content': message or f'Status changed to {status}',
            'status': status.lower(),
            'agent': 'System'
        }
    }
    
    # Send WebSocket message with proper format
    send_message_to_websocket(event) 
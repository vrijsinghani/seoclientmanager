import logging
import traceback
from crewai.agents.parser import AgentAction, AgentFinish
from apps.agents.models import CrewExecution
from ..utils.logging import log_crew_message
from ..handlers.websocket import send_message_to_websocket

logger = logging.getLogger(__name__)

class TaskCallback:
    def __init__(self, execution_id):
        self.execution_id = execution_id

    def __call__(self, task_output):
        """Handle task callback from CrewAI."""
        try:
            execution = CrewExecution.objects.get(id=self.execution_id)
            
            # Extract task ID from task output
            crewai_task_id = None
            if hasattr(task_output, 'task'):
                crewai_task_id = str(task_output.task.id)
            elif hasattr(task_output, 'id'):
                crewai_task_id = str(task_output.id)
                
            logger.debug(f"Task callback task ID: {crewai_task_id}")
            
            if task_output.raw:
                # Format as a proper execution update
                event = {
                    'type': 'execution_update',
                    'execution_id': self.execution_id,
                    'status': execution.status,
                    'crewai_task_id': crewai_task_id,
                    'stage': {
                        'stage_type': 'task_output',
                        'title': 'Task Output',
                        'content': task_output.raw,
                        'status': 'completed'
                    }
                }
                send_message_to_websocket(event)
                
                # Log to database with CrewAI task ID
                log_crew_message(
                    execution=execution,
                    content=task_output.raw,
                    agent="Task Output",
                    task_id=crewai_task_id
                )

        except Exception as e:
            logger.error(f"Error in task callback: {str(e)}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            raise

class StepCallback:
    def __init__(self, execution_id):
        self.execution_id = execution_id

    def __call__(self, step_output):
        """Handle step callback from CrewAI."""
        try:
            execution = CrewExecution.objects.get(id=self.execution_id)
            
            # Extract task ID from the current task context
            crewai_task_id = None
            if hasattr(step_output, 'task'):
                crewai_task_id = str(step_output.task.id)
            elif hasattr(step_output, 'id'):
                crewai_task_id = str(step_output.id)
                
            logger.debug(f"Step callback task ID: {crewai_task_id}")
            
            if isinstance(step_output, AgentAction):
                # Log tool usage
                event = {
                    'type': 'execution_update',
                    'execution_id': self.execution_id,
                    'crewai_task_id': crewai_task_id,
                    'stage': {
                        'stage_type': 'tool_usage',
                        'title': f'Using Tool: {step_output.tool}',
                        'content': f'Tool: {step_output.tool}\nInput: {step_output.tool_input}',
                        'status': 'in_progress',
                        'agent': step_output.thought
                    }
                }
                send_message_to_websocket(event)
                
                log_crew_message(
                    execution=execution,
                    content=f"Using tool: {step_output.tool}\nInput: {step_output.tool_input}",
                    agent=step_output.thought,
                    task_id=crewai_task_id
                )
                
                if step_output.result:
                    # Log tool result
                    event = {
                        'type': 'execution_update',
                        'execution_id': self.execution_id,
                        'crewai_task_id': crewai_task_id,
                        'stage': {
                            'stage_type': 'tool_result',
                            'title': 'Tool Result',
                            'content': step_output.result,
                            'status': 'completed',
                            'agent': 'Tool Output'
                        }
                    }
                    send_message_to_websocket(event)
                    
                    log_crew_message(
                        execution=execution,
                        content=f"Tool result: {step_output.result}",
                        agent="Tool Output",
                        task_id=crewai_task_id
                    )
                    
            elif isinstance(step_output, AgentFinish):
                # Log final answer
                event = {
                    'type': 'execution_update',
                    'execution_id': self.execution_id,
                    'crewai_task_id': crewai_task_id,
                    'stage': {
                        'stage_type': 'task_output',
                        'title': 'Final Answer',
                        'content': step_output.output,
                        'status': 'completed',
                        'agent': step_output.thought
                    }
                }
                send_message_to_websocket(event)
                
                log_crew_message(
                    execution=execution,
                    content=f"Final Answer: {step_output.output}",
                    agent=step_output.thought,
                    task_id=crewai_task_id
                )

        except Exception as e:
            logger.error(f"Error in step callback: {str(e)}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            raise 
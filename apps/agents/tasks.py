from celery import shared_task
from .models import CrewExecution, CrewMessage, Task, Agent as AgentModel, CrewOutput
from crewai import Crew, Agent, Task as CrewAITask, LLM
from django.core.exceptions import ObjectDoesNotExist
import logging
from apps.common.utils import get_llm_openai
from django.conf import settings
import builtins
from django.core.cache import cache
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import time
import json
from io import StringIO
from crewai.tasks.task_output import TaskOutput
from functools import partial
import threading
import sys
from contextlib import contextmanager
    
logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()   

def custom_input_handler(prompt, execution_id):
    logger.info(f"Custom input handler called for execution {execution_id} with prompt: {prompt}")
    execution = CrewExecution.objects.get(id=execution_id)
    update_execution_status(execution, 'WAITING_FOR_HUMAN_INPUT')
    log_crew_message(execution, prompt or "Input required", agent='System', human_input_request=prompt or "Input required")
    
    input_key = f'human_input_request_{execution_id}'
    response_key = f"{input_key}_response"
    cache.set(input_key, prompt or "Input required", timeout=3600)
    
    async_to_sync(channel_layer.group_send)(
        f"crew_execution_{execution_id}",
        {
            "type": "crew_execution_update",
            "status": "WAITING_FOR_HUMAN_INPUT",
            "human_input_request": prompt or "Input required"
        }
    )
    
    # Wait for the input (with a timeout)
    timeout = 300  # 5 minutes timeout
    poll_interval = 1  # Check every second
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        user_input = cache.get(response_key)
        
        if user_input is not None:
            # Clear the cache
            cache.delete(input_key)
            cache.delete(response_key)
            
            log_crew_message(execution, f"Received human input: {user_input}", agent='Human')
            update_execution_status(execution, 'RUNNING')
            
            logger.info(f"Received human input for execution {execution_id}: {user_input}")
            return user_input
       
        time.sleep(poll_interval)
    
    logger.warning(f"Timeout waiting for human input in execution {execution_id}")
    raise TimeoutError("No user input received within the timeout period")

class WebSocketStringIO(StringIO):
    def __init__(self, execution_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.execution_id = execution_id
        self.last_position = 0

    def write(self, s):
        super().write(s)
        self.send_to_websocket()

    def send_to_websocket(self):
        current_position = self.tell()
        if current_position > self.last_position:
            self.seek(self.last_position)
            new_content = self.read(current_position - self.last_position)
            self.seek(current_position)
            self.last_position = current_position

            async_to_sync(channel_layer.group_send)(
                f"crew_execution_{self.execution_id}",
                {
                    "type": "crew_execution_update",
                    "status": "RUNNING",
                    "messages": [{"agent": "System", "content": new_content.strip()}]
                }
            )

@contextmanager
def capture_stdout(execution_id):
    original_stdout = sys.stdout
    custom_stdout = WebSocketStringIO(execution_id)
    sys.stdout = custom_stdout
    try:
        yield custom_stdout
    finally:
        sys.stdout = original_stdout

def stdout_monitor(custom_stdout):
    while True:
        custom_stdout.send_to_websocket()
        time.sleep(0.1)  # Check every 100ms

@shared_task(bind=True)
def execute_crew(self, execution_id):
    logger.info(f"Attempting to start crew execution for id: {execution_id} (task_id: {self.request.id})")
    
    # Try to acquire a lock
    lock_id = f'crew_execution_lock_{execution_id}'
    if not cache.add(lock_id, 'locked', timeout=3600):  # 1 hour timeout
        logger.info(f"Execution {execution_id} is already in progress. Skipping this task.")
        return
    
    try:
        logger.info(f"Starting crew execution for id: {execution_id} (task_id: {self.request.id})")
        execution = CrewExecution.objects.get(id=execution_id)
        
        # Store the original input function
        original_input = builtins.input
        
        def custom_input_wrapper(prompt=''):
            return custom_input_handler(prompt, execution_id)
        
        # Replace the input function with our custom wrapper
        builtins.input = custom_input_wrapper
        
        log_crew_message(execution, f"Starting execution for crew: {execution.crew.name}")
        
        with capture_stdout(execution_id) as custom_stdout:
            # Start the stdout monitor in a separate thread
            monitor_thread = threading.Thread(target=stdout_monitor, args=(custom_stdout,))
            monitor_thread.daemon = True
            monitor_thread.start()

            try:
                crew = initialize_crew(execution)
                result = run_crew(self.request.id, crew, execution)
                if result == "Execution cancelled by user":
                    update_execution_status(execution, 'CANCELLED')
                    return execution.id
                update_execution_status(execution, 'COMPLETED', result)
                
                # Convert UsageMetrics to a dictionary
                token_usage = result.token_usage.dict() if hasattr(result.token_usage, 'dict') else result.token_usage

                CrewOutput.objects.create(
                    execution=execution,
                    raw=str(result),
                    pydantic=result.pydantic.dict() if result.pydantic else None,
                    json_dict=result.json_dict,
                    token_usage=token_usage
                )
                
                log_message = f"Crew execution completed successfully. Output: {result}"
                log_crew_message(execution, log_message)
            except Exception as e:
                handle_execution_error(execution, e)
            finally:
                # Restore the original input function
                builtins.input = original_input
    finally:
        # Release the lock
        cache.delete(lock_id)

    logger.info(f"Execution completed for CrewExecution id: {execution_id}")
    return execution.id

def initialize_crew(execution):
    agents = create_crewai_agents(execution.crew.agents.all(), execution.id)
    tasks = create_crewai_tasks(execution.crew.tasks.all(), agents, execution)
    
    if not tasks:
        raise ValueError("No valid tasks for crew execution")

    crew_params = {
        'agents': agents,
        'tasks': tasks,
        'process': execution.crew.process,
        'verbose': execution.crew.verbose,
        'task_callback': partial(task_callback, execution_id=execution.id),
    }

    optional_params = [
        'memory', 'max_rpm', 'language', 'language_file', 'full_output',
        'share_crew', 'output_log_file', 'planning', 'planning_llm',
        'function_calling_llm', 'manager_llm', 'manager_agent',
        'manager_callbacks', 'prompt_file', 'cache', 'embedder'
    ]

    for param in optional_params:
        value = getattr(execution.crew, param, None)
        if value is not None:
            crew_params[param] = value

    logger.debug(f"Creating Crew with parameters: {crew_params}")

    return Crew(**crew_params)

def run_crew(task_id, crew, execution):
    logger.debug(f"Running crew for execution id: {execution.id}")
    log_crew_message(execution, f"Running crew")
    inputs = execution.inputs or {}
    inputs["execution_id"] = execution.id

    update_execution_status(execution, 'RUNNING')

    try:
        if execution.crew.process == 'sequential':
            result = crew.kickoff(inputs=inputs)
        elif execution.crew.process == 'hierarchical':
            result = crew.kickoff(inputs=inputs)
        elif execution.crew.process == 'for_each':
            inputs_array = inputs.get('inputs_array', [])
            result = crew.kickoff_for_each(inputs=inputs_array)
        elif execution.crew.process == 'async':
            result = crew.kickoff_async(inputs=inputs)
        elif execution.crew.process == 'for_each_async':
            inputs_array = inputs.get('inputs_array', [])
            result = crew.kickoff_for_each_async(inputs=inputs_array)
        else:
            raise ValueError(f"Unknown process type: {execution.crew.process}")

        logger.info(f"Crew kickoff completed for execution id: {execution.id}")
        log_crew_message(execution, f"Crew execution completed with result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error during crew execution: {str(e)}", exc_info=True)
        raise

def create_crewai_agents(agent_models, execution_id):
    agents = []
    for agent_model in agent_models:
        try:
            model_name = agent_model.llm.split('/', 1)[1] if '/' in agent_model.llm else agent_model.llm
            crewai_agent_llm = LLM(
                model=model_name,
                api_key=settings.LITELLM_MASTER_KEY,
                base_url=settings.API_BASE_URL,
            )
            agent_params = {
                'role': agent_model.role,
                'goal': agent_model.goal,
                'backstory': agent_model.backstory,
                'verbose': agent_model.verbose,
                'allow_delegation': agent_model.allow_delegation,
                'llm': crewai_agent_llm,
                'step_callback': partial(step_callback, execution_id=execution_id),
                'human_input_handler': partial(human_input_handler, execution_id=execution_id),
            }
            optional_params = ['max_iter', 'max_rpm', 'function_calling_llm']
            agent_params.update({param: getattr(agent_model, param) for param in optional_params if getattr(agent_model, param) is not None})
            
            agent = Agent(**agent_params)
            agents.append(agent)
            logger.info(f"CrewAI Agent created successfully for agent id: {agent_model.id}")
        except Exception as e:
            logger.error(f"Error creating CrewAI Agent for agent {agent_model.id}: {str(e)}")
    return agents

def human_input_handler(prompt, execution_id):
    logger.info(f"Human input required for execution {execution_id}: {prompt}")
    execution = CrewExecution.objects.get(id=execution_id)
    update_execution_status(execution, 'WAITING_FOR_HUMAN_INPUT')
    log_crew_message(execution, f"Human input required: {prompt}", agent='System', human_input_request=prompt)
    
    input_key = f"human_input_{execution_id}_{prompt[:20]}"
    cache.set(input_key, prompt, timeout=3600)  # 1 hour timeout
    
    async_to_sync(channel_layer.group_send)(
        f"crew_execution_{execution_id}",
        {
            "type": "crew_execution_update",
            "status": "WAITING_FOR_HUMAN_INPUT",
            "human_input_request": prompt
        }
    )
    
    max_wait_time = 3600  # 1 hour
    start_time = time.time()
    while time.time() - start_time < max_wait_time:
        response = cache.get(f"{input_key}_response")
        if response:
            cache.delete(input_key)
            cache.delete(f"{input_key}_response")
            return response
        time.sleep(1)
    
    return "No human input received within the specified time."

def create_crewai_tasks(task_models, agents, execution):
    tasks = []
    for task_model in task_models:
        try:
            crewai_agent = next((agent for agent in agents if agent.role == task_model.agent.role), None)
            if not crewai_agent:
                logger.warning(f"No matching CrewAI agent found for task {task_model.id}")
                continue

            task_dict = {
                'description': task_model.description,
                'agent': crewai_agent,
                'expected_output': task_model.expected_output,
                'async_execution': task_model.async_execution,
                'human_input': task_model.human_input,
                'callback': partial(task_callback, execution_id=execution.id),
            }

            optional_fields = ['output_json', 'output_pydantic', 'output_file', 'converter_cls']
            task_dict.update({field: getattr(task_model, field) for field in optional_fields if getattr(task_model, field) is not None})

            tasks.append(CrewAITask(**task_dict))
            logger.info(f"CrewAITask created successfully for task: {task_model.id}")
        except Exception as e:
            logger.error(f"Error creating CrewAITask for task {task_model.id}: {str(e)}")
    return tasks

def step_callback(step_output, execution_id):
    logger.info(f"Step completed for execution {execution_id}: {step_output}")
    execution = CrewExecution.objects.get(id=execution_id)
    log_crew_message(execution, f"Step completed: {step_output}", agent='System')

def task_callback(task_output: TaskOutput, execution_id):
    logger.info(f"Task completed for execution {execution_id}: {task_output}")
    execution = CrewExecution.objects.get(id=execution_id)
    log_crew_message(execution, f"Task completed: {task_output}", agent='System')

def update_execution_status(execution, status, result=None):
    execution.status = status
    if result:
        if isinstance(result, dict) and 'final_output' in result:
            execution.outputs = {
                'final_output': result['final_output'],
                'tasks_outputs': result.get('tasks_outputs', [])
            }
        else:
            execution.outputs = {'final_output': str(result)}
    execution.save()

    async_to_sync(channel_layer.group_send)(
        f'crew_execution_{execution.id}',
        {
            'type': 'crew_execution_update',
            'status': status,
            'messages': []
        }
    )

def log_crew_message(execution, content, agent=None, human_input_request=None):
    if content:  # Only create a message if there's content
        message = CrewMessage.objects.create(execution=execution, content=content, agent=agent)
        
        async_to_sync(channel_layer.group_send)(
            f'crew_execution_{execution.id}',
            {
                'type': 'crew_execution_update',
                'status': execution.status,
                'messages': [{'agent': message.agent or 'System', 'content': message.content}],
                'human_input_request': human_input_request
            }
        )
        
        logger.info(f"Sent message to WebSocket: {content}")
    else:
        logger.warning("Attempted to log an empty message, skipping.")

def handle_execution_error(execution, exception):
    logger.error(f"Error during crew execution: {str(exception)}", exc_info=True)
    update_execution_status(execution, 'FAILED')
    error_message = f"Crew execution failed: {str(exception)}"
    log_crew_message(execution, error_message, agent=None)
    execution.error_message = error_message
    execution.save()
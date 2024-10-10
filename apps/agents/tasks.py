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

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()

class HumanInputRequired(Exception):
    def __init__(self, request: str):
        self.request = request
        super().__init__(f"Human input required: {request}")

def custom_input_handler(prompt=None, execution_id=None):
    if prompt is None:
        prompt = "Input required:"
    
    if execution_id is None:
        logger.warning("Execution ID not provided for custom input handler")
        return builtins.input(prompt)  # Fall back to standard input

    # Store the prompt in the cache
    cache.set(f'human_input_request_{execution_id}', prompt, timeout=3600)
    
    # Notify the web interface that input is needed
    async_to_sync(channel_layer.group_send)(
        f"execution_{execution_id}",
        {
            "type": "human_input_required",
            "message": prompt
        }
    )
    
    # Wait for the input (with a timeout)
    user_input = None
    timeout = 120  # 2 minutes timeout
    start_time = time.time()
    while user_input is None and time.time() - start_time < timeout:
        user_input = cache.get(f'human_input_response_{execution_id}')
        if user_input is None:
            time.sleep(1)  # Wait for 1 second before checking again
    
    if user_input is None:
        raise TimeoutError("No user input received within the timeout period")
    
    # Clear the cache
    cache.delete(f'human_input_response_{execution_id}')
    
    return user_input

# Replace the built-in input function
#builtins.input = lambda prompt=None: custom_input_handler(prompt, execution.id)

@shared_task
def execute_crew(execution_id):
    logger.info(f"Starting crew execution for id: {execution_id}")
    execution = CrewExecution.objects.get(id=execution_id)
    
    log_crew_message(execution, f"Starting execution for crew: {execution.crew.name}")
    
    try:
        result = run_crew(execution)
        update_execution_status(execution, 'COMPLETED', result)
        
        # Create CrewOutput
        CrewOutput.objects.create(
            execution=execution,
            raw=str(result),
            pydantic=result.pydantic.dict() if result.pydantic else None,
            json_dict=result.json_dict,
            token_usage=result.token_usage
        )
        
        log_message = f"Crew execution completed successfully. Output: {result}"
        log_crew_message(execution, log_message)
    except HumanInputRequired as e:
        handle_human_input_required(execution, e)
    except Exception as e:
        handle_execution_error(execution, e)

    logger.info(f"Execution completed for CrewExecution id: {execution_id}")
    return execution.id

def run_crew(execution):
    logger.debug(f"Setting up crew for execution id: {execution.id}")
    log_crew_message(execution, f"Setting up crew for execution")
    
    agents = create_crewai_agents(execution.crew.agents.all())
    tasks = create_crewai_tasks(execution.crew.tasks.all(), agents, execution)
    
    if not tasks:
        raise ValueError("No valid tasks for crew execution")

    crew = create_crew(agents, tasks, execution)
    
    log_crew_message(execution, f"Crew assembled with {len(agents)} agents and {len(tasks)} tasks")
    
    logger.info(f"Crew instance created for execution id: {execution.id}. Starting kickoff.")
    log_crew_message(execution, "Starting crew execution")
    
    try:
        inputs = execution.inputs or {}
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
        
        log_crew_message(execution, f"Crew execution completed with result: {result}")
    except Exception as e:
        logger.error(f"Error during crew execution: {str(e)}")
        raise
    
    logger.info(f"Crew kickoff completed for execution id: {execution.id}")
    return result

def create_crewai_agents(agent_models):
    agents = []
    for agent_model in agent_models:
        try:
            model_name=agent_model.llm.split('/', 1)[1] if '/' in agent_model.llm else agent_model.llm
            logger.debug(f"agent model_name: {model_name}")
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
            }
            optional_params = ['max_iter', 'max_rpm', 'function_calling_llm', 'step_callback']
            agent_params.update({param: getattr(agent_model, param) for param in optional_params if getattr(agent_model, param) is not None})
            
            agents.append(Agent(**agent_params))
            logger.info(f"CrewAI Agent created successfully for agent id: {agent_model.id}")
        except Exception as e:
            logger.error(f"Error creating CrewAI Agent for agent {agent_model.id}: {str(e)}")
    return agents

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
            }

            if task_model.human_input:
                task_dict['human_input_callback'] = lambda prompt: custom_input_handler(prompt, execution.id)

            optional_fields = ['output_json', 'output_pydantic', 'output_file', 'callback', 'converter_cls']
            task_dict.update({field: getattr(task_model, field) for field in optional_fields if getattr(task_model, field) is not None})

            tasks.append(CrewAITask(**task_dict))
            logger.info(f"CrewAITask created successfully for task: {task_model.id}")
        except Exception as e:
            logger.error(f"Error creating CrewAITask for task {task_model.id}: {str(e)}")
    return tasks

def make_step_callback(execution_id):
    def step_callback(step_output):
        message = f"Step: {step_output.get('step_type')} - {step_output.get('output')}"
        async_to_sync(channel_layer.group_send)(
            f'crew_execution_{execution_id}',
            {
                'type': 'crew_execution_update',
                'status': 'RUNNING',
                'messages': [{'agent': step_output.get('agent_name', 'System'), 'content': message}]
            }
        )
    return step_callback

def make_task_callback(execution_id):
    def task_callback(task_output):
        message = f"Task Completed: {task_output.get('task_name')} - {task_output.get('output')}"
        async_to_sync(channel_layer.group_send)(
            f'crew_execution_{execution_id}',
            {
                'type': 'crew_execution_update',
                'status': 'RUNNING',
                'messages': [{'agent': 'System', 'content': message}]
            }
        )
    return task_callback

def make_human_input_callback(execution_id):
    def human_input_callback(request):
        raise HumanInputRequired(request)
    return human_input_callback

def create_crew(agents, tasks, execution):
    # Base configuration
    crew_params = {
        'agents': agents,
        'tasks': tasks,
        'process': execution.crew.process,
        'verbose': execution.crew.verbose,
    }

    # Add optional parameters if they are set and not None
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

    # Add callbacks with execution_id in their closure
    crew_params['step_callback'] = make_step_callback(execution.id)
    crew_params['task_callback'] = make_task_callback(execution.id)

    logger.debug(f"Creating Crew with parameters: {crew_params}")

    return Crew(**crew_params)

def handle_human_input(execution, request):
    raise HumanInputRequired(request)

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

    # Send status update to WebSocket
    async_to_sync(channel_layer.group_send)(
        f'crew_execution_{execution.id}',
        {
            'type': 'crew_execution_update',
            'status': status,
            'messages': []
        }
    )

def log_crew_message(execution, content, agent=None):
    message = CrewMessage.objects.create(execution=execution, content=content, agent=agent)
    
    # Send message to WebSocket
    async_to_sync(channel_layer.group_send)(
        f'crew_execution_{execution.id}',
        {
            'type': 'crew_execution_update',
            'status': execution.status,
            'messages': [{'agent': message.agent or 'System', 'content': message.content}]
        }
    )
    
    # Log the message for debugging
    logger.info(f"Sent message to WebSocket: {content}")

def handle_human_input_required(execution, exception):
    logger.info(f"Human input required for execution {execution.id}: {str(exception)}")
    update_execution_status(execution, 'WAITING_FOR_HUMAN_INPUT')
    execution.human_input_request = exception.request
    execution.save()
    log_crew_message(execution, f"Human input required: {exception.request}")

def handle_execution_error(execution, exception):
    logger.error(f"Error during crew execution: {str(exception)}", exc_info=True)
    update_execution_status(execution, 'FAILED')
    error_message = f"Crew execution failed: {str(exception)}"
    log_crew_message(execution, error_message, agent=None)
    execution.error_message = error_message
    execution.save()

@shared_task
def resume_crew_execution(execution_id: int) -> int:
    logger.info(f"Resuming execution for CrewExecution id: {execution_id}")
    try:
        execution = CrewExecution.objects.get(id=execution_id)
        if execution.status != 'WAITING_FOR_HUMAN_INPUT':
            logger.error(f"Cannot resume execution {execution_id}: not waiting for human input")
            return execution_id

        update_execution_status(execution, 'RUNNING')
        
        try:
            result = run_crew(execution)
            update_execution_status(execution, 'COMPLETED', result)
            log_message = f"Execution resumed and completed after human input. Output: {result}"
            log_crew_message(execution, log_message)
            logger.info(f"Execution resumed and completed for CrewExecution id: {execution_id}")
        except HumanInputRequired as e:
            handle_human_input_required(execution, e)
        except Exception as e:
            handle_execution_error(execution, e)

    except ObjectDoesNotExist:
        logger.error(f"CrewExecution with id {execution_id} not found")
    except Exception as e:
        logger.error(f"Unexpected error in resume_crew_execution: {str(e)}", exc_info=True)

    return execution_id

class WebSocketHandler(logging.Handler):
    def __init__(self, execution_id):
        super().__init__()
        self.execution_id = execution_id
        self.string_io = StringIO()

    def emit(self, record):
        msg = self.format(record)
        async_to_sync(channel_layer.group_send)(
            f'crew_execution_{self.execution_id}',
            {
                'type': 'crew_execution_update',
                'status': 'RUNNING',
                'messages': [{'agent': 'CrewAI', 'content': msg}]
            }
        )
        self.string_io.write(msg + '\n')

def setup_crewai_logger(execution_id):
    logger = logging.getLogger('crewai')
    logger.setLevel(logging.INFO)
    handler = WebSocketHandler(execution_id)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return handler
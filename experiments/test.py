from celery import shared_task
from .models import CrewExecution, CrewMessage, Task, Agent as AgentModel, CrewOutput
from crewai import Crew, Agent, Task as CrewAITask, LLM
from django.core.exceptions import ObjectDoesNotExist
import logging
from apps.common.utils import get_llm_openai
from django.conf import settings
from django.core.cache import cache
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import time
import json
from io import StringIO
from crewai.tasks.task_output import TaskOutput
from functools import partial

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()

@shared_task(bind=True)
def execute_crew(self, execution_id):
    logger.info(f"Starting crew execution for id: {execution_id}")
    execution = CrewExecution.objects.get(id=execution_id)
    
    log_crew_message(execution, f"Starting execution for crew: {execution.crew.name}")
    
    try:
        crew = initialize_crew(execution)
        result = run_crew(self.request.id, crew, execution)
        if result == "Execution cancelled by user":
            update_execution_status(execution, 'CANCELLED')
            return execution.id
        update_execution_status(execution, 'COMPLETED', result)
        
        CrewOutput.objects.create(
            execution=execution,
            raw=str(result),
            pydantic=result.pydantic.dict() if result.pydantic else None,
            json_dict=result.json_dict,
            token_usage=result.token_usage
        )
        
        log_message = f"Crew execution completed successfully. Output: {result}"
        log_crew_message(execution, log_message)
    except Exception as e:
        handle_execution_error(execution, e)

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
        logger.error(f"Error during crew execution: {str(e)}")
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
                'human_input_handler': partial(human_input_handler, execution_id=execution_id),
                'step_callback': partial(step_callback, execution_id=execution_id),
            }
            optional_params = ['max_iter', 'max_rpm', 'function_calling_llm']
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
                'callback': partial(task_callback, execution_id=execution.id),
            }

            optional_fields = ['output_json', 'output_pydantic', 'output_file', 'converter_cls']
            task_dict.update({field: getattr(task_model, field) for field in optional_fields if getattr(task_model, field) is not None})

            tasks.append(CrewAITask(**task_dict))
            logger.info(f"CrewAITask created successfully for task: {task_model.id}")
        except Exception as e:
            logger.error(f"Error creating CrewAITask for task {task_model.id}: {str(e)}")
    return tasks

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
    
    while True:
        response = cache.get(f"{input_key}_response")
        if response:
            cache.delete(input_key)
            cache.delete(f"{input_key}_response")
            return response
        time.sleep(1)

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

def handle_execution_error(execution, exception):
    logger.error(f"Error during crew execution: {str(exception)}", exc_info=True)
    update_execution_status(execution, 'FAILED')
    error_message = f"Crew execution failed: {str(exception)}"
    log_crew_message(execution, error_message, agent=None)
    execution.error_message = error_message
    execution.save()
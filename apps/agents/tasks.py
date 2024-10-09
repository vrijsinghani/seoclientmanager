from celery import shared_task
from .models import CrewExecution, CrewMessage, Task, Agent as AgentModel
from crewai import Crew, Agent, Task as CrewAITask, LLM
from django.core.exceptions import ObjectDoesNotExist
import logging
from apps.common.utils import get_llm_openai
from django.conf import settings

logger = logging.getLogger(__name__)

class HumanInputRequired(Exception):
    def __init__(self, request: str):
        self.request = request
        super().__init__(f"Human input required: {request}")

@shared_task
def execute_crew(execution_id):
    logger.info(f"Starting crew execution for id: {execution_id}")
    execution = CrewExecution.objects.get(id=execution_id)
    
    try:
        result = run_crew(execution)
        update_execution_status(execution, 'COMPLETED', result)
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
    logger.debug(f"# Create agents\n{execution.crew.agents.all()}")
    logger.debug(f"# Define tasks\n{execution.crew.tasks.all()}")
    agents = create_crewai_agents(execution.crew.agents.all())
    tasks = create_crewai_tasks(execution.crew.tasks.all(), agents, execution)
    
    # Log agents and tasks before crew creation

    if not tasks:
        raise ValueError("No valid tasks for crew execution")

    crew = create_crew(agents, tasks, execution)
    
    # Log the crew configuration
    logger.info(f"# Assemble a crew\n{crew}")
    
    logger.info(f"Crew instance created for execution id: {execution.id}. Starting kickoff.")
    
    result = crew.kickoff(**execution.inputs)
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
                task_dict['human_input_callback'] = lambda request: handle_human_input(execution, request)

            optional_fields = ['output_json', 'output_pydantic', 'output_file', 'callback', 'converter_cls']
            task_dict.update({field: getattr(task_model, field) for field in optional_fields if getattr(task_model, field) is not None})

            tasks.append(CrewAITask(**task_dict))
            logger.info(f"CrewAITask created successfully for task: {task_model.id}")
        except Exception as e:
            logger.error(f"Error creating CrewAITask for task {task_model.id}: {str(e)}")
    return tasks

def create_crew(agents, tasks, execution):
    crew_config = execution.crew.config or {}
    return Crew(
        agents=agents,
        tasks=tasks,
        process=execution.crew.process,
        verbose=execution.crew.verbose,
        **crew_config
    )

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

def log_crew_message(execution, content):
    CrewMessage.objects.create(execution=execution, content=content)

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
    log_crew_message(execution, error_message)
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
        result = run_crew(execution)
        update_execution_status(execution, 'COMPLETED', result)
        log_message = f"Execution resumed and completed after human input. Output: {result}"
        log_crew_message(execution, log_message)
        logger.info(f"Execution resumed and completed for CrewExecution id: {execution_id}")
    except HumanInputRequired as e:
        handle_human_input_required(execution, e)
    except Exception as e:
        handle_execution_error(execution, e)

    return execution.id
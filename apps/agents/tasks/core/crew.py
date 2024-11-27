import logging
import traceback
from datetime import datetime
import os
from functools import partial
from celery import shared_task
from django.conf import settings
from crewai import Crew
from apps.agents.models import CrewExecution, ExecutionStage, CrewOutput, Task
from ..utils.logging import log_crew_message, update_execution_status
from .agents import create_crewai_agents
from .tasks import create_crewai_tasks
from ..callbacks.execution import StepCallback, TaskCallback
from apps.common.utils import get_llm

logger = logging.getLogger(__name__)

def initialize_crew(execution):
    """Initialize a CrewAI crew instance from a CrewExecution object"""
    try:
        # Create regular agents (excluding manager)
        regular_agents = list(execution.crew.agents.all())
        
        # Create CrewAI agents for regular agents
        agents = create_crewai_agents(regular_agents, execution.id)
        if not agents:
            raise ValueError("No valid agents created")
            
        # Create manager agent separately if it exists
        manager_agent = None
        if execution.crew.manager_agent:
            manager_agents = create_crewai_agents([execution.crew.manager_agent], execution.id)
            if manager_agents:
                manager_agent = manager_agents[0]
        
        # Fetch and order the tasks
        ordered_tasks = Task.objects.filter(
            crewtask__crew=execution.crew
        ).order_by('crewtask__order')
        
        tasks = create_crewai_tasks(ordered_tasks, agents, execution)
        if not tasks:
            raise ValueError("No valid tasks for crew execution")

        # Handle LLM fields first
        llm_fields = ['manager_llm', 'function_calling_llm', 'planning_llm']
        llm_params = {}
        for field in llm_fields:
            value = getattr(execution.crew, field)
            if value:
                logger.debug(f"Using LLM: {value}")
                crew_llm, _ = get_llm(value)
                llm_params[field] = crew_llm

        # Build crew parameters
        crew_params = {
            'agents': agents,
            'tasks': tasks,
            'step_callback': StepCallback(execution.id),
            'task_callback': TaskCallback(execution.id),
            'process': execution.crew.process,
            'verbose': execution.crew.verbose,
            'execution_id': str(execution.id),
            **llm_params  # Add LLM parameters
        }

        # Add manager agent if it exists
        if manager_agent:
            crew_params['manager_agent'] = manager_agent

        # Add optional parameters if they exist
        optional_params = [
            'memory', 'max_rpm', 'language', 'language_file', 'full_output',
            'share_crew', 'output_log_file', 'planning', 'manager_callbacks', 
            'prompt_file', 'cache', 'embedder'
        ]

        for param in optional_params:
            value = getattr(execution.crew, param, None)
            if value is not None:
                crew_params[param] = value

        # Create and return the crew instance
        logger.debug(f"Creating Crew with parameters: {crew_params}")
        crew = Crew(**crew_params)
        
        if not crew:
            raise ValueError("Failed to create Crew instance")
            
        return crew
        
    except Exception as e:
        logger.error(f"Error in initialize_crew: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise

def run_crew(task_id, crew, execution):
    """Run a crew and handle execution stages and status updates"""
    try:
        # Update to running status
        update_execution_status(execution, 'RUNNING', task_id=task_id)
        
        # Create execution stage for running
        ExecutionStage.objects.create(
            execution=execution,
            stage_type='task_running',
            title='Running Crew',
            content=f'Executing crew tasks for: {execution.crew.name}',
            status='running'
        )
        
        # Get crew inputs
        inputs = {
            'client_id': execution.client_id,
            'execution_id': execution.id,
            'current_date': datetime.now().strftime("%Y-%m-%d"),
            'client_name': execution.client.name,
            'client_website_url': execution.client.website_url,
            'client_business_objectives': execution.client.business_objectives,
            'client_target_audience': execution.client.target_audience,
            'client_profile': execution.client.client_profile,
        }
        
        logger.info(f"Crew inputs: {inputs}")
        logger.info(f"Crew process type: {execution.crew.process}")
        
        # Set up callbacks for task ID tracking
        crew.step_callback = StepCallback(execution.id)
        crew.task_callback = TaskCallback(execution.id)
        
        # Run the crew based on process type
        if execution.crew.process == 'sequential':
            logger.debug("Starting sequential crew execution")
            result = crew.kickoff(inputs=inputs)
        elif execution.crew.process == 'hierarchical':
            logger.debug("Starting hierarchical crew execution")
            result = crew.kickoff(inputs=inputs)
        elif execution.crew.process == 'for_each':
            logger.debug("Starting for_each crew execution")
            inputs_array = inputs.get('inputs_array', [])
            result = crew.kickoff_for_each(inputs=inputs_array)
        elif execution.crew.process == 'async':
            logger.debug("Starting async crew execution")
            result = crew.kickoff_async(inputs=inputs)
        elif execution.crew.process == 'for_each_async':
            logger.debug("Starting for_each_async crew execution")
            inputs_array = inputs.get('inputs_array', [])
            result = crew.kickoff_for_each_async(inputs=inputs_array)
        else:
            raise ValueError(f"Unknown process type: {execution.crew.process}")
            
        # Create completion stage
        ExecutionStage.objects.create(
            execution=execution,
            stage_type='task_complete',
            title='Execution Complete',
            content=str(result),
            status='completed'
        )
        
        # Create CrewOutput
        crew_output = CrewOutput.objects.create(
            raw=str(result),
            json_dict=result if isinstance(result, dict) else None
        )
        
        # Update execution with output
        execution.crew_output = crew_output
        execution.save()
        
        return result
        
    except Exception as e:
        # Create error stage
        ExecutionStage.objects.create(
            execution=execution,
            stage_type='task_error',
            title='Execution Error',
            content=str(e),
            status='error'
        )
        raise 


def handle_execution_error(execution, exception, task_id=None):
    logger.error(f"Error during crew execution: {str(exception)}", exc_info=True)
    update_execution_status(execution, 'FAILED', task_id=task_id)
    error_message = f"Crew execution failed: {str(exception)}"
    log_crew_message(execution, error_message, agent=None, task_id=task_id)
    execution.error_message = error_message
    execution.save()

    # Print the full traceback to stdout
    print("Full traceback:")
    traceback.print_exc()

def save_result_to_file(execution, result):
    timestamp = datetime.now().strftime("%y-%m-%d-%H-%M")
    crew_name = execution.crew.name.replace(' ', '_')
    client = get_object_or_404(Client, id=execution.client_id)
    # Directly create flattened client inputs
    
    client_name = client.name.replace(' ', '_')
    file_name = f"{client_name}-finaloutput_{timestamp}.txt"
    
    # Create the directory path
    dir_path = os.path.join(settings.MEDIA_ROOT, str(execution.user.id), 'crew_runs', crew_name)
    os.makedirs(dir_path, exist_ok=True)
    
    # Create the full file path
    file_path = os.path.join(dir_path, file_name)
    
    # Write the result to the file
    with open(file_path, 'w') as f:
        f.write(str(result))
    
    # Log the file creation
    relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
    log_message = f"Final output saved to: {relative_path}"
    log_crew_message(execution, log_message, agent="System")
    logger.info(log_message)

@shared_task(bind=True)
def execute_crew(self, execution_id):
    """Execute a crew with the given execution ID"""
    try:
        execution = CrewExecution.objects.get(id=execution_id)
        logger.debug(f"Attempting to start crew execution for id: {execution_id} (task_id: {self.request.id})")
        
        # Create initial stage
        ExecutionStage.objects.create(
            execution=execution,
            stage_type='task_start',
            title='Starting Execution',
            content=f'Starting execution for crew: {execution.crew.name}',
            status='completed'
        )
        
        # Update execution status to PENDING
        update_execution_status(execution, 'PENDING', task_id=self.request.id)
        
        logger.debug(f"Starting crew execution for id: {execution_id} (task_id: {self.request.id})")
        
        # Initialize crew
        crew = initialize_crew(execution)
        if not crew:
            raise ValueError("Failed to initialize crew")
            
        # Run crew
        result = run_crew(self.request.id, crew, execution)
        
        # Save the result and update execution status to COMPLETED
        if result:
            log_crew_message(execution, str(result), agent='System', task_id=self.request.id)
        update_execution_status(execution, 'COMPLETED', task_id=self.request.id)
        
        return execution.id
        
    except Exception as e:
        logger.error(f"Error during crew execution: {str(e)}")
        if 'execution' in locals():
            handle_execution_error(execution, e, task_id=getattr(self, 'request', None) and self.request.id)
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise 
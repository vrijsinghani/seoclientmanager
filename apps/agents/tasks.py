from celery import shared_task
import json
from .models import CrewExecution, Tool, CrewMessage, Task, Agent as AgentModel, CrewOutput, CrewTask, ExecutionStage
from apps.seo_manager.models import Client, GoogleAnalyticsCredentials, SearchConsoleCredentials
from crewai import Crew, Agent, Task as CrewAITask
from langchain.tools import BaseTool
from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist
import logging
from apps.common.utils import get_llm
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
import importlib
from crewai_tools import BaseTool as CrewAIBaseTool
from langchain.tools import BaseTool as LangChainBaseTool
from django.shortcuts import get_object_or_404
#from langchain.tools import tool as langchain_tool
import os
from apps.agents.utils import get_tool_info
from django.forms.models import model_to_dict
from datetime import datetime
from crewai.agents.parser import AgentAction, AgentFinish
from crewai.project import callback
from typing import Union
import traceback

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()   

def load_tool_in_task(tool_model):
    tool_info = get_tool_info(tool_model)
    
    try:
        print(f"Attempting to load tool: {tool_model.tool_class}.{tool_model.tool_subclass}", file=sys.stderr)
        logger.info(f"Attempting to load tool: {tool_model.tool_class}.{tool_model.tool_subclass}")
        
        module = importlib.import_module(tool_info['module_path'])
        tool_class = getattr(module, tool_info['class_name'])
        
        if issubclass(tool_class, (CrewAIBaseTool, LangChainBaseTool)):
            tool_instance = tool_class()
            print(f"Tool loaded successfully: {tool_class.__name__}", file=sys.stderr)
            logger.info(f"Tool loaded successfully: {tool_class.__name__}")
            return tool_instance
        else:
            logger.error(f"Unsupported tool class: {tool_class}")
            return None
    except Exception as e:
        logger.error(f"Error loading tool {tool_model.tool_class}.{tool_model.tool_subclass}: {str(e)}", exc_info=True)
        print(f"Error loading tool {tool_model.tool_class}.{tool_model.tool_subclass}: {str(e)}", file=sys.stderr)
        return None

def custom_input_handler(prompt, execution_id):
    logger.debug(f"Custom input handler called for execution {execution_id} with prompt: {prompt}")
    execution = CrewExecution.objects.get(id=execution_id)
    update_execution_status(execution, 'WAITING_FOR_HUMAN_INPUT', task_id=None)
    log_crew_message(execution, prompt or "Input required", agent='Human Input Requested', human_input_request=prompt or "Input required")
    
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
            update_execution_status(execution, 'RUNNING', task_id=None)
            
            return user_input
       
        time.sleep(poll_interval)
    
    logger.warning(f"Timeout waiting for human input in execution {execution_id}")
    raise TimeoutError("No user input received within the timeout period")

class WebSocketStringIO(StringIO):
    def __init__(self, execution_id, send_to_original_stdout=True, send_to_websocket=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.execution_id = execution_id
        self.last_position = 0
        self.send_to_original_stdout = send_to_original_stdout
        self.should_send_to_websocket = send_to_websocket  
        self.original_stdout = sys.stdout

    def write(self, s):
        super().write(s)
        if self.send_to_original_stdout:
            self.original_stdout.write(s)
            self.original_stdout.flush()  # Ensure immediate output
        if self.should_send_to_websocket:  
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
def capture_stdout(execution_id, send_to_original_stdout=True, send_to_websocket=True):
    original_stdout = sys.stdout
    custom_stdout = WebSocketStringIO(execution_id, send_to_original_stdout, send_to_websocket)
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

def initialize_crew(execution):
    # Create regular agents (excluding manager)
    regular_agents = list(execution.crew.agents.all())
    
    # Create CrewAI agents for regular agents
    agents = create_crewai_agents(regular_agents, execution.id)
    
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

    crew_params = {
        'agents': agents,
        'tasks': tasks,
        'process': execution.crew.process,
        'verbose': execution.crew.verbose,
        'step_callback': partial(step_callback, execution_id=execution.id),
        'task_callback': partial(task_callback, execution_id=execution.id),
        'execution_id': execution.id,
    }

    # Add manager agent if it exists
    if manager_agent:
        crew_params['manager_agent'] = manager_agent

    # Handle additional LLM fields for Crew
    llm_fields = ['manager_llm', 'function_calling_llm', 'planning_llm']
    for field in llm_fields:
        value = getattr(execution.crew, field)
        if value:
            logger.debug(f"Using LLM: {value}")
            crew_llm, _ = get_llm(value)
            crew_params[field] = crew_llm

    optional_params = [
        'memory', 'max_rpm', 'language', 'language_file', 'full_output',
        'share_crew', 'output_log_file', 'planning', 'manager_callbacks', 
        'prompt_file', 'cache', 'embedder'
    ]

    for param in optional_params:
        value = getattr(execution.crew, param, None)
        if value is not None:
            crew_params[param] = value

    return Crew(**crew_params)


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

def create_crewai_agents(agent_models, execution_id):
    agents = []
    for agent_model in agent_models:
        try:
            agent_params = {
                'role': agent_model.role,
                'goal': agent_model.goal,
                'backstory': agent_model.backstory,
                'verbose': agent_model.verbose,
                'allow_delegation': agent_model.allow_delegation,
                'step_callback': partial(detailed_step_callback, execution_id=execution_id),
                'human_input_handler': partial(human_input_handler, execution_id=execution_id),
                'tools': [],
                'execution_id': execution_id
            }

            # Handle LLM fields for Agent
            llm_fields = ['llm', 'function_calling_llm']
            for field in llm_fields:
                value = getattr(agent_model, field)
                if value:
                    logger.debug(f"Using LLM: {value}")
                    agent_llm, _ = get_llm(value)
                    agent_params[field] = agent_llm

            # Load tools with their settings
            for tool in agent_model.tools.all():
                loaded_tool = load_tool_in_task(tool)
                if loaded_tool:
                    # Get tool settings
                    tool_settings = agent_model.get_tool_settings(tool)
                    if tool_settings and tool_settings.force_output_as_result:
                        # Apply the force output setting
                        loaded_tool = type(loaded_tool)(
                            result_as_answer=True,
                            **{k: v for k, v in loaded_tool.__dict__.items() if k != 'result_as_answer'}
                        )
                    agent_params['tools'].append(loaded_tool)
                    logger.debug(f"Added tool {tool.name} to agent {agent_model.name}")
                else:
                    logger.warning(f"Failed to load tool {tool.name} for agent {agent_model.name}")

            optional_params = ['max_iter', 'max_rpm', 'system_template', 'prompt_template', 'response_template']
            agent_params.update({param: getattr(agent_model, param) for param in optional_params if getattr(agent_model, param) is not None})
            
            agent = Agent(**agent_params)
            logger.debug(f"CrewAI Agent created successfully for agent id: {agent_model.id} with {len(agent_params['tools'])} tools")
            agents.append(agent)
        except Exception as e:
            logger.error(f"Error creating CrewAI Agent for agent {agent_model.id}: {str(e)}")
    return agents

def human_input_handler(prompt, execution_id):
    execution = CrewExecution.objects.get(id=execution_id)
    update_execution_status(execution, 'WAITING_FOR_HUMAN_INPUT', task_id=None)
    log_crew_message(execution, f"Human input required: {prompt}", agent='Human Input Requested', human_input_request=prompt)
    
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
        logger.debug(f"Creating CrewAITask for task: {task_model.id}-{task_model.description}-{task_model.agent_id}-{agents}")
        try:
            # Associate the Task with the CrewExecution
            task_model.crew_execution = execution
            task_model.save()

            crewai_agent = next((agent for agent in agents if agent.role == AgentModel.objects.get(id=task_model.agent_id).role), None)
            if not crewai_agent:
                logger.warning(f"No matching CrewAI agent found for task {task_model.id}")
                continue

            task_tools = []
            for tool_model in task_model.tools.all():
                tool = load_tool_in_task(tool_model)
                if tool:
                    task_tools.append(tool)

            task_dict = {
                'description': task_model.description,
                'agent': crewai_agent,
                'expected_output': task_model.expected_output,
                'async_execution': task_model.async_execution,
                'human_input': task_model.human_input,
                'tools': task_tools,
                'execution_id': execution.id,
                'crewai_task_id': task_model.id  # Use this for kanban board placement
            }
            logger.info(f"Task dict: {task_dict}")
            optional_fields = ['output_json', 'output_pydantic', 'converter_cls']
            task_dict.update({field: getattr(task_model, field) for field in optional_fields if getattr(task_model, field) is not None})

            # Handle output_file separately
            if task_model.output_file:
                description_part = task_model.description[:20]  # Adjust the slice as needed
                
                # Generate a pithy timestamp
                timestamp = datetime.now().strftime("%y-%m-%d-%H-%M")
                
                # Get the file name and extension
                file_name, file_extension = os.path.splitext(task_model.output_file)
                
                # Append the timestamp to the file name
                new_file_name = f"{file_name}_{timestamp}{file_extension}"

                # Construct the full path using MEDIA_ROOT
                full_path = os.path.join(settings.MEDIA_URL, str(execution.user.id), description_part, new_file_name)
                logger.debug(f"Full path for output_file: {full_path}")
                log_crew_message(execution, f"Task output will be saved to: {full_path}", agent='System')

                task_dict['output_file'] = full_path

            tasks.append(CrewAITask(**task_dict))
            logger.debug(f"CrewAITask created successfully for task: {task_model.id}")
        except Exception as e:
            logger.error(f"Error creating CrewAITask for task {task_model.id}: {str(e)}", exc_info=True)
    return tasks

def task_callback(task_output: TaskOutput, execution_id):
    """Handle task output callbacks"""
    try:
        execution = CrewExecution.objects.get(id=execution_id)
        agent = task_output.agent
        
        # Get the CrewAI task ID from the task description
        task = Task.objects.filter(
            crew_execution=execution,
            description=task_output.description
        ).first()
        
        crewai_task_id = task.id if task else None
        logger.info(f"Task output: {task_output}, CrewAI Task ID: {crewai_task_id}")
        
        if task_output.raw:
            # Format as a proper execution update
            message = {
                'type': 'execution_update',
                'execution_id': execution_id,
                'status': execution.status,
                'crewai_task_id': crewai_task_id,  # Use this for kanban board placement
                'stage': {
                    'stage_type': 'task_output',
                    'title': f'Output from {agent or "System"}',
                    'content': str(task_output.raw),
                    'status': 'completed',
                    'agent': agent
                }
            }
            send_message_to_websocket(message)
            
            # Also log to database with CrewAI task ID
            log_crew_message(execution, str(task_output.raw), agent=agent, task_id=crewai_task_id)
            
            # Create execution stage with CrewAI task ID
            ExecutionStage.objects.create(
                execution=execution,
                stage_type='task_output',
                title=f'Output from {agent or "System"}',
                content=str(task_output.raw),
                status='completed',
                agent=AgentModel.objects.filter(role=agent).first() if agent else None,
                crewai_task_id=crewai_task_id
            )
    except Exception as e:
        logger.error(f"Error in task callback: {str(e)}")

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
        'crewai_task_id': crewai_task_id,  # Use this for kanban board placement
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

def handle_execution_error(execution, exception, task_id=None):
    logger.error(f"Error during crew execution: {str(exception)}", exc_info=True)
    update_execution_status(execution, 'FAILED', task_id=task_id)
    error_message = f"Crew execution failed: {str(exception)}"
    log_crew_message(execution, error_message, agent=None, task_id=task_id)
    execution.error_message = error_message
    execution.save()

    # Print the full traceback to stdout
    import traceback
    print("Full traceback:")
    traceback.print_exc()

def detailed_step_callback(event, execution_id):
    logger.info(f"Received event: {event}")
    
    # Extract event type
    if isinstance(event, dict):
        event_type = event.get('type')
        logger.info(f"Event type from dict: {event_type}")
    else:
        event_type = getattr(event, 'type', None)
        logger.info(f"Event type from object: {event_type}")

    # Default values
    stage_type = 'thinking'
    title = 'Processing'
    status = 'in_progress'
    
    # Extract content for logging
    content = None
    if isinstance(event, dict):
        content = event.get('content', '')
    else:
        content = getattr(event, 'content', '')
    
    # Ensure content is never None and has meaningful information
    if not content:
        if isinstance(event, dict):
            tool_name = event.get('tool', 'Unknown Tool')
            tool_input = event.get('tool_input', '')
            content = f"Tool: {tool_name}\nInput: {tool_input}"
        else:
            tool_name = getattr(event, 'tool', 'Unknown Tool')
            tool_input = getattr(event, 'tool_input', '')
            content = f"Tool: {tool_name}\nInput: {tool_input}"
            
    logger.info(f"Event content: {content}")
        
    # Detect tool usage from both dict and object formats
    if isinstance(event, dict):
        if event.get('tool'):
            event_type = 'AgentAction'
            logger.info("Detected tool usage from dict, setting event_type to AgentAction")
    else:
        if getattr(event, 'tool', None):
            event_type = 'AgentAction'
            logger.info("Detected tool usage from object, setting event_type to AgentAction")
            
    logger.info(f"Final event type after detection: {event_type}")
        
    # Map event types to stage types
    if event_type == 'AgentStart':
        stage_type = 'task_start'
        title = 'Starting Task'
        logger.info("Mapped event to task_start stage")
        
    elif event_type == 'AgentAction':
        stage_type = 'tool_usage'
        title = f'Using Tool: {event.get("tool", "Unknown Tool") if isinstance(event, dict) else getattr(event, "tool", "Unknown Tool")}'
        logger.info("Mapped event to tool_usage stage")
        
    elif event_type == 'AgentToolResult':
        stage_type = 'tool_results'
        title = 'Tool Results'
        logger.info("Mapped event to tool_results stage")
        
    elif event_type == 'HumanInputRequest':
        stage_type = 'human_input'
        title = 'Waiting for Human Input'
        status = 'pending'
        logger.info("Mapped event to human_input stage")
        
    elif event_type == 'AgentFinish':
        stage_type = 'completion'
        title = 'Task Complete'
        status = 'completed'
        logger.info("Mapped event to completion stage")
    else:
        logger.info(f"Using default thinking stage for event type: {event_type}")
        
    logger.info(f"Final stage mapping - Type: {stage_type}, Title: {title}, Status: {status}")
    
    try:
        # Create or update stage
        stage = ExecutionStage.objects.create(
            execution_id=execution_id,
            stage_type=stage_type,
            title=title,
            status=status,
            content=content if content else f"Processing {stage_type} stage - {title}"  # Enhanced default content
        )
        logger.info(f"Successfully created stage: {stage.id} - {stage.stage_type}")
        
        # Send WebSocket message
        message = {
            'type': 'execution_update',  # Changed from 'stage_update' to 'execution_update'
            'execution_id': execution_id,
            'stage': {
                'id': stage.id,
                'stage_type': stage_type,
                'title': title,
                'status': status,
                'content': content if content else f"Processing {stage_type} stage - {title}",
                'agent': getattr(event, 'agent', None) if not isinstance(event, dict) else event.get('agent', None)
            }
        }
        send_message_to_websocket(message)
        logger.info(f"Sent WebSocket message for stage: {stage.id}")
        
    except Exception as e:
        logger.error(f"Error creating/updating stage: {str(e)}", exc_info=True)

def send_message_to_websocket(message):
    """Send message to websocket"""
    try:
        # Get execution ID from message
        execution_id = message.get('execution_id')
        if not execution_id:
            logger.error("No execution_id in message")
            return

        # Get crew ID from execution
        try:
            execution = CrewExecution.objects.get(id=execution_id)
            crew_id = execution.crew.id
        except CrewExecution.DoesNotExist:
            logger.error(f"No execution found for ID {execution_id}")
            return

        # Add status if not present
        if 'status' not in message:
            message['status'] = execution.status

        # Send message to websocket group
        group_name = f'crew_{crew_id}_kanban'
        async_to_sync(channel_layer.group_send)(
            group_name,
            message
        )
        logger.debug(f"Sent WebSocket message to group {group_name}: {message}")
    except Exception as e:
        logger.error(f"Error sending WebSocket message: {str(e)}")

from crewai.tools.tool_usage_events import ToolUsageError
from crewai.utilities.events import on

@on(ToolUsageError)
def tool_error_callback(source, event: ToolUsageError):
    """
    This callback is triggered whenever a tool encounters an error during execution.

    Args:
        source: The source of the event (likely the ToolUsage instance).
        event (ToolUsageError): The ToolUsageError event containing error details.
    """
    execution_id = source.task.execution_id  # Assuming you've stored execution_id in the Task
    execution = CrewExecution.objects.get(id=execution_id)
    agent_role = event.agent_role

    error_message = f"Tool '{event.tool_name}' failed for agent '{agent_role}'."
    error_message += f"\n Error: {event.error}"
    error_message += f"\n Tool Arguments: {event.tool_args}"
    error_message += f"\n Run Attempts: {event.run_attempts}"
    error_message += f"\n Delegations: {event.delegations}"
    
    log_crew_message(execution, error_message, agent='Tool Error Callback')
    logger.error(error_message)
    error_message = f"Tool '{event.tool_name}' failed for agent '{agent_role}'."
    error_message += f"\n Error: {event.error}"
    error_message += f"\n Tool Arguments: {event.tool_args}"
    error_message += f"\n Run Attempts: {event.run_attempts}"
    error_message += f"\n Delegations: {event.delegations}"
    
    log_crew_message(execution, error_message, agent='Tool Error Callback')
    logger.error(error_message)

def step_callback(step_output, execution_id):
    """Callback for each step of the execution"""
    # Create event dictionary with proper structure
    event = {
        'type': 'execution_update',
        'execution_id': execution_id,
        'stage': {
            'stage_type': step_output.get('type', 'processing'),
            'title': step_output.get('title', 'Processing...'),
            'content': step_output.get('content', ''),
            'status': step_output.get('status', 'in_progress'),
            'agent': step_output.get('agent', 'System')
        }
    }
    
    # Call detailed callback with properly formatted event
    detailed_step_callback(event, execution_id)

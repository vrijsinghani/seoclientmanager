from celery import shared_task
from .models import CrewExecution, Tool, CrewMessage, Task, Agent as AgentModel, CrewOutput, CrewTask
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
    update_execution_status(execution, 'WAITING_FOR_HUMAN_INPUT')
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
            update_execution_status(execution, 'RUNNING')
            
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
    logger.debug(f"Attempting to start crew execution for id: {execution_id} (task_id: {self.request.id})")
    
    # Try to acquire a lock
    lock_id = f'crew_execution_lock_{execution_id}'
    if not cache.add(lock_id, 'locked', timeout=3600):  # 1 hour timeout
        logger.warning(f"Execution {execution_id} is already in progress. Skipping this task.")
        return
    
    try:
        logger.debug(f"Starting crew execution for id: {execution_id} (task_id: {self.request.id})")
        execution = CrewExecution.objects.get(id=execution_id)
        
        # Store the original input function
        original_input = builtins.input
        
        def custom_input_wrapper(prompt=''):
            return custom_input_handler(prompt, execution_id)
        
        # Replace the input function with our custom wrapper
        builtins.input = custom_input_wrapper
        
        log_crew_message(execution, f"Starting execution for crew: {execution.crew.name}")
        
        with capture_stdout(execution_id, send_to_original_stdout=True, send_to_websocket=True) as custom_stdout:
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
                
                # Save the result to a file
                save_result_to_file(execution, result)
                
                log_message = f"Crew execution completed successfully. Output: {result}"
                
                log_crew_message(execution, log_message, agent="System")
                log_message = f"Token Usage: {token_usage}"
                log_crew_message(execution, log_message, agent="System")
            except Exception as e:
                handle_execution_error(execution, e)
            finally:
                # Restore the original input function
                builtins.input = original_input
    finally:
        # Release the lock
        cache.delete(lock_id)

    logger.debug(f"Execution completed for CrewExecution id: {execution_id}")
    return execution.id

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
    log_crew_message(execution, f"Running crew")
    inputs = execution.inputs or {}
    inputs["execution_id"] = execution.id
    inputs["current_date"] = datetime.now().strftime("%Y-%m-%d")
    client = get_object_or_404(Client, id=execution.client_id)
    # Directly create flattened client inputs
    inputs["client_id"] = client.id
    inputs["client_name"] = client.name
    inputs["client_website_url"] = client.website_url
    inputs["client_business_objectives"] = client.business_objectives
    inputs["client_target_audience"] = client.target_audience
    inputs["client_profile"] = client.client_profile

    logger.info(f"Crew inputs: {inputs}")
    logger.info(f"Crew process type: {execution.crew.process}")
    update_execution_status(execution, 'RUNNING')

    try:
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

        return result
    except Exception as e:
        logger.error(f"Error during crew execution: {str(e)}", exc_info=True)
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
    update_execution_status(execution, 'WAITING_FOR_HUMAN_INPUT')
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
                'execution_id': execution.id  # Add this line
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

def step_callback(step_output, execution_id):
    logger.info(f"Step callback: {step_output}")
    execution = CrewExecution.objects.get(id=execution_id)
    log_crew_message(execution, f"Step callback: {step_output}", agent='Interim Step')

def task_callback(task_output: TaskOutput, execution_id):
    execution = CrewExecution.objects.get(id=execution_id)
    log_message = f"Task callback:\n{task_output.raw}"
    agent = task_output.agent
    if task_output.raw:
        log_crew_message(execution, log_message, agent=agent)

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
        
        logger.debug(f"Sent message to WebSocket: {content[:100]}")
    else:
        logger.warning("Attempted to log an empty message, skipping.")

def handle_execution_error(execution, exception):
    logger.error(f"Error during crew execution: {str(exception)}", exc_info=True)
    update_execution_status(execution, 'FAILED')
    error_message = f"Crew execution failed: {str(exception)}"
    log_crew_message(execution, error_message, agent=None)
    execution.error_message = error_message
    execution.save()

    # Print the full traceback to stdout
    import traceback
    print("Full traceback:")
    traceback.print_exc()

def detailed_step_callback(event: Union[AgentAction, AgentFinish], execution_id):
    """
    This callback is triggered after each step in an agent's execution.

    Args:
        event (Union[AgentAction, AgentFinish]):  Either an AgentAction (if a tool was used) or an AgentFinish (if the agent completed its task).
        execution_id (int): ID of the crew execution
    """
    try:
        execution = CrewExecution.objects.get(id=execution_id)
        
        # Log based on event type
        if isinstance(event, AgentAction):
            logger.info(f"Detailed step callback: Action - {event.tool}, Input - {event.tool_input}, Thought - {event.thought}")
        elif isinstance(event, AgentFinish):
            logger.info(f"Detailed step callback: Final Answer - {event.output}, Reasoning - {event.reasoning}")
        else:
            logger.info(f"Detailed step callback: Unknown event type - {type(event)}")

        # Default agent role
        agent_role = "Agent"
        
        # Try to extract agent role from event attributes
        try:
            if hasattr(event, 'text'):
                text = str(event.text) if event.text is not None else ""
                if "Role:" in text:
                    role_parts = text.split("Role:")
                    if len(role_parts) > 1:
                        agent_role = role_parts[1].split("\n")[0].strip()
        except Exception as e:
            logger.debug(f"Could not extract role from event: {e}")

        # Build content based on event type
        content = f"Agent '{agent_role}' step callback triggered."

        if isinstance(event, AgentAction):
            content += f"\n Thought: {getattr(event, 'thought', 'No thought provided')}"
            content += f"\n Action: {getattr(event, 'tool', 'No tool specified')}"
            content += f"\n Action Input: {getattr(event, 'tool_input', 'No input provided')}"
            content += f"\n Tool Output: {getattr(event, 'result', 'No result available')}"
        elif isinstance(event, AgentFinish):
            content += f"\n Final Answer: {getattr(event, 'output', 'No output provided')}"

        log_crew_message(execution, content, agent='Step Callback')
    except Exception as e:
        logger.error(f"Error in detailed_step_callback: {e}", exc_info=True)

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

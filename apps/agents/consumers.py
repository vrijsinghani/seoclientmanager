import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import CrewExecution, CrewMessage, ChatMessage, Agent
from django.core.cache import cache
from apps.common.utils import format_message, get_llm
from .utils import get_tool_classes
import logging
import uuid
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, FunctionMessage, BaseMessage, messages_from_dict, messages_to_dict
import asyncio
import tiktoken
from langchain_community.chat_models import ChatLiteLLM
from langchain_core.tools import Tool
from django.utils import timezone
from apps.seo_manager.models import Client
from langchain.prompts import ChatPromptTemplate
from langchain.agents import initialize_agent, AgentType
from langchain_core.callbacks import BaseCallbackHandler
import datetime
from langchain.tools import StructuredTool
from typing import Dict, Any, List
from pydantic import create_model
from langchain.memory import ConversationBufferMemory
from langchain_core.chat_history import BaseChatMessageHistory
import re
import time

logger = logging.getLogger(__name__)


def count_tokens(text):
    """Count tokens in text using tiktoken"""
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    return len(encoding.encode(text))

class ConnectionTestConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send(text_data=json.dumps({
            'message': 'Connected to server'
        }))

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json['message']

            # Echo the received message back to the client
            await self.send(text_data=json.dumps({
                'message': f'Server received: {message}'
            }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON format'
            }))
        except KeyError:
            await self.send(text_data=json.dumps({
                'error': 'Missing "message" key in JSON'
            }))

class CrewExecutionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.execution_id = self.scope['url_route']['kwargs']['execution_id']
        self.execution_group_name = f'crew_execution_{self.execution_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.execution_group_name,
            self.channel_name
        )

        await self.accept()

        # Send initial status
        await self.send_execution_status()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.execution_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')

        if message_type == 'human_input':
            input_key = text_data_json.get('input_key')
            user_input = text_data_json.get('input')
            await self.handle_human_input(input_key, user_input)

    async def crew_execution_update(self, event):
        status = event.get('status', '')  # No formatting applied
        formatted_messages = [
            {
                'agent': msg.get('agent', 'System'),
                'content': format_message(msg.get('content', ''))
            } for msg in event.get('messages', []) if msg.get('content')
        ]
        # logger.info(f"Sending status: {status}")
        # logger.info(f"Sending formatted messages: {formatted_messages}")
        await self.send(text_data=json.dumps({
            'status': status,
            'messages': formatted_messages,
            'human_input_request': event.get('human_input_request')
        }))

    @database_sync_to_async
    def handle_human_input(self, input_key, user_input):
        cache.set(f"{input_key}_response", user_input, timeout=3600)
        execution = CrewExecution.objects.get(id=self.execution_id)
        CrewMessage.objects.create(
            execution=execution,
            agent='Human',
            content=f"Human input received: {user_input}"
        )

    @database_sync_to_async
    def get_execution_status(self):
        execution = CrewExecution.objects.get(id=self.execution_id)
        messages = CrewMessage.objects.filter(execution=execution).order_by('-timestamp')[:10]
        return {
            'status': execution.status,
            'messages': [{'agent': msg.agent, 'content': msg.content} for msg in messages],
        }

    async def send_execution_status(self):
        status_data = await self.get_execution_status()
        status = status_data['status']  # No formatting applied
        formatted_messages = [
            {
                'agent': msg['agent'],
                'content': format_message(msg['content'])
            } for msg in status_data['messages'] if msg.get('content')
        ]
        
        # logger.info(f"Sending status: {status}")
        # logger.info(f"Sending formatted messages: {formatted_messages}")
        
        await self.send(text_data=json.dumps({
            'status': status,
            'messages': formatted_messages,
        }))

class AgentToolManager:
  def __init__(self):
      pass

  async def load_tools(self, agent):
      """Load and initialize agent tools"""
      tools = []
      for tool_model in agent.tools.all():
          try:
              tool_classes = get_tool_classes(tool_model.tool_class)
              tool_class = next((cls for cls in tool_classes 
                               if cls.__name__ == tool_model.tool_subclass), None)
              
              if tool_class:
                  logger.info(f"Initializing tool: {tool_class.__name__}")
                  tool_instance = tool_class()
                  tools.append(tool_instance)
              else:
                  logger.error(f"Tool class not found: {tool_model.tool_subclass}")
          except Exception as e:
              logger.error(f"Error loading tool {tool_model.name}: {str(e)}")
      return tools

  def convert_to_langchain_tools(self, tools):
      """Convert custom tools to Langchain format"""
      return [self._create_langchain_tool(tool) for tool in tools]

  def _create_langchain_tool(self, tool):
      """Create individual Langchain tool"""
      formatted_name = ''.join(c for c in tool.name if c.isalnum() or c in '_-')[:64]
      
      async def tool_func(query: str, tool=tool):
          try:
              result = await self.execute_tool(tool, {"query": query})
              return result
          except Exception as e:
              logger.error(f"Tool execution error: {str(e)}")
              return f"Error: {str(e)}"

      return Tool(
          name=formatted_name,
          description=self._create_tool_description(tool),
          func=tool_func,
          coroutine=tool_func
      )

  def _create_tool_description(self, tool):
      """Create descriptive help text for tool"""
      return f"""
{tool.description}

Use natural language to describe what data you need. The tool will extract parameters from your request and the client context.

Examples:
- "Get analytics data for the last 30 days"
- "Show me search performance since January 1st"
- "Generate a report for Q1"
"""

class ClientDataManager:
  def __init__(self):
      pass

  @database_sync_to_async
  def get_client_data(self, client_id):
      """Get and format client data"""
      try:
          client = Client.objects.get(id=client_id)
          current_date = timezone.now().date()
          
          return {
              'client_id': client.id,
              'current_date': current_date.isoformat(),
              #'name': getattr(client, 'name', 'Not provided'),
              #'website': getattr(client, 'website', 'Not provided'),
              #'profile': getattr(client, 'client_profile', ''),
              #'target_audience': getattr(client, 'target_audience', ''),
              #'business_objectives': self._get_business_objectives(client),
              #'service_area': getattr(client, 'service_area', 'Not provided'),
             # 'industry': getattr(client, 'industry', 'Not provided')
          }
      except Exception as e:
          logger.error(f"Error getting client data: {str(e)}", exc_info=True)
          return None

  def _get_business_objectives(self, client):
      """Extract business objectives from client"""
      try:
          if hasattr(client, 'business_objectives'):
              if isinstance(client.business_objectives, list):
                  return self._process_objectives_list(client.business_objectives)
              return self._process_objectives_queryset(client.business_objectives.all())
          elif hasattr(client, 'businessobjective_set'):
              return self._process_objectives_queryset(client.businessobjective_set.all())
          return []
      except Exception as e:
          logger.error(f"Error processing objectives: {str(e)}")
          return []

  def _process_objectives_list(self, objectives_data):
      """Process list of objectives"""
      return [
          {
              'goal': obj.get('goal', 'N/A'),
              'metric': obj.get('metric', 'N/A'),
              'target_date': obj.get('target_date', 'N/A'),
              'status': obj.get('status', 'Inactive')
          }
          for obj in objectives_data if isinstance(obj, dict)
      ]

class DjangoCacheMessageHistory(BaseChatMessageHistory):
    """Message history that uses Django's cache backend"""
    
    def __init__(self, session_id: str, ttl: int = 3600):
        self.session_id = session_id
        self.ttl = ttl
        self.key = f"chat_history_{session_id}"

    def add_message(self, message: BaseMessage) -> None:
        """Append the message to the history in cache"""
        messages = self.messages
        messages.append(message)
        cache.set(
            self.key,
            messages_to_dict(messages),
            timeout=self.ttl
        )

    @property
    def messages(self) -> List[BaseMessage]:
        """Retrieve the messages from cache"""
        messages_dict = cache.get(self.key, [])
        return messages_from_dict(messages_dict) if messages_dict else []

    def clear(self) -> None:
        """Clear message history from cache"""
        cache.delete(self.key)

class ChatConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tool_manager = AgentToolManager()
        self.client_manager = ClientDataManager()
        self.session_id = str(uuid.uuid4())
        self.group_name = f"chat_{self.session_id}"
        self._agent_executor = None
        self._callback_handler = None
        self.is_connected = False  # Add connection state tracking

    async def _get_or_create_agent_executor(self, agent, model_name, client_data):
        """Get existing agent executor or create a new one"""
        if self._agent_executor is None:
            self._agent_executor = await database_sync_to_async(self._initialize_agent)(
                agent, model_name, client_data
            )
        return self._agent_executor

    async def connect(self):
        try:
            # Add connection lock
            if self.is_connected:
                return
            
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            self.is_connected = True  # Mark as connected
            
            # Send initial connection message
            await self.send(text_data=json.dumps({
                'message': 'Connected to chat server',
                'is_system': True,
                'connection_status': 'connected'
            }))
            
            # Set up periodic connection check
            self.connection_check_task = asyncio.create_task(self._check_connection())
            
        except Exception as e:
            logger.error(f"Connection error: {str(e)}", exc_info=True)
            self.is_connected = False
            raise

    async def disconnect(self, close_code):
        """Handle disconnect properly"""
        try:
            self.is_connected = False
            
            # Cancel connection check task
            if hasattr(self, 'connection_check_task'):
                self.connection_check_task.cancel()
                
            # Clean up agent executor
            if self._agent_executor:
                await self._cleanup_agent_executor()
                
            # Remove from channel layer group
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            
            logger.info(f"WebSocket disconnected with code: {close_code}")
            
        except Exception as e:
            logger.error(f"Error in disconnect: {str(e)}", exc_info=True)

    async def _check_connection(self):
        """Periodic connection health check"""
        while self.is_connected:
            try:
                # Send ping frame
                await self.send(bytes_data=b'ping')
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Connection check failed: {str(e)}")
                self.is_connected = False
                break

    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming messages with better error handling"""
        try:
            # Handle ping/pong
            if bytes_data == b'ping':
                await self.send(bytes_data=b'pong')
                return
            elif bytes_data == b'pong':
                return

            # Process text messages
            if not text_data:
                return

            # Verify connection state
            if not self.is_connected:
                await self.close()
                return

            data = json.loads(text_data)
            message = data['message']
            agent_id = data['agent_id']
            model_name = data['model']
            client_id = data.get('client_id')

            # Get agent and client data
            agent = await self.get_agent(agent_id)
            client_data = await self.client_manager.get_client_data(client_id) if client_id else None

            # Get or create agent executor
            agent_executor = await self._get_or_create_agent_executor(agent, model_name, client_data)
            
            # Execute agent with proper error handling
            response = await self._execute_agent_with_retry(
                agent_executor,
                message,
                max_retries=3
            )
            
            # Save and send response
            await self._handle_response(response, agent_id, model_name)
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            await self._handle_error("Invalid message format")
        except Exception as e:
            logger.error(f"Error in receive: {str(e)}", exc_info=True)
            await self._handle_error(str(e))

    async def _execute_agent_with_retry(self, agent_executor, message, max_retries=3):
        """Execute agent with retry logic and proper response formatting"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Add input validation
                if not message or not message.strip():
                    raise ValueError("Empty or invalid input message")

                # Execute the agent asynchronously with timeout
                response = await asyncio.wait_for(
                    database_sync_to_async(agent_executor.run)(  # Changed to run instead of arun
                        input=message,
                        callbacks=[self._create_callback_handler()]
                    ),
                    timeout=30
                )
                
                # Log the raw response for debugging
                logger.debug(f"Raw agent response: {response}")
                
                # Process the response
                formatted_response = await self._process_agent_response(response)
                if formatted_response:
                    return formatted_response
                
                raise ValueError("Invalid or empty response from agent")
                
            except asyncio.TimeoutError:
                logger.error(f"Agent execution timed out on attempt {attempt + 1}")
                await asyncio.sleep(1)  # Brief pause before retry
                if attempt == max_retries - 1:
                    return "I apologize, but the request timed out. Please try again with a simpler query."
                
            except Exception as e:
                last_error = e
                logger.error(f"Agent execution attempt {attempt + 1} failed: {str(e)}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause before retry
                
                if attempt == max_retries - 1:
                    return f"I apologize, but I encountered an error: {str(last_error)}"
        
        return f"I apologize, but I encountered an error: {str(last_error)}"

    async def _process_agent_response(self, response):
        """Process and validate agent response"""
        try:
            # Handle dict responses (direct tool output)
            if isinstance(response, dict):
                if response.get('success') is True:
                    formatted = self._format_analytics_response(response)
                    return {
                        "action": "Final Answer",
                        "action_input": formatted
                    }
                return str(response)
            
            # Handle string responses
            if isinstance(response, str):
                # Check for Final Answer format
                if '"action": "Final Answer"' in response:
                    try:
                        # Extract the action_input from Final Answer
                        match = re.search(r'"action_input":\s*"([^"]+)"', response)
                        if match:
                            return match.group(1)
                    except Exception:
                        pass
                
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        if data.get('success') is True:
                            formatted = self._format_analytics_response(data)
                            return {
                                "action": "Final Answer",
                                "action_input": formatted
                            }
                    except json.JSONDecodeError:
                        pass
                
                # Return non-empty string responses
                if response.strip():
                    return response.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing agent response: {str(e)}", exc_info=True)
            return None

    def _initialize_agent(self, agent, model_name, client_data):
        """Initialize the agent with tools and memory"""
        try:
            # Load tools only once
            tools = self._load_tools_sync(agent)
            
            # Get LLM instance
            llm, _ = get_llm(model_name)
            
            # Initialize memory
            message_history = DjangoCacheMessageHistory(
                session_id=self.session_id,
                ttl=3600
            )

            memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                chat_memory=message_history,
                output_key="output"
            )
            
            # Create agent executor with specific configuration
            return initialize_agent(
                tools=tools,
                llm=llm,
                agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True,
                memory=memory,
                agent_kwargs={
                    "prefix": self._create_agent_prompt(agent, client_data),
                    "format_instructions": self._get_format_instructions(),
                    "input_variables": ["input", "agent_scratchpad", "chat_history"],
                    "output_variables": ["output"],
                    "handle_parsing_errors": True,
                    # Add these to help agent understand when to stop
                    "max_iterations": 3,  # Limit number of iterations
                    "early_stopping_method": "generate",
                    "return_intermediate_steps": True
                },
                handle_parsing_errors=True
            )
            
        except Exception as e:
            logger.error(f"Error initializing agent: {str(e)}", exc_info=True)
            raise

    def _load_tools_sync(self, agent):
        """Synchronously load and initialize agent tools"""
        try:
            tools = []
            seen_tools = set()  # Track which tools we've already initialized
            
            for tool_model in agent.tools.all():
                try:
                    # Skip if we've already initialized this tool
                    tool_key = f"{tool_model.tool_class}_{tool_model.tool_subclass}"
                    if tool_key in seen_tools:
                        continue
                    seen_tools.add(tool_key)

                    tool_classes = get_tool_classes(tool_model.tool_class)
                    tool_class = next((cls for cls in tool_classes 
                                   if cls.__name__ == tool_model.tool_subclass), None)
                    
                    if tool_class:
                        logger.info(f"Initializing tool: {tool_class.__name__}")
                        tool_instance = tool_class()
                        
                        # Ensure tool has required attributes
                        if not hasattr(tool_instance, 'args_schema'):
                            logger.error(f"Tool {tool_class.__name__} missing args_schema")
                            continue
                        
                        # Create tool description
                        tool_description = self._create_tool_description(tool_instance, tool_model)
                        
                        # Create Langchain tool with direct reference to tool instance methods
                        langchain_tool = StructuredTool(
                            name=tool_model.name,
                            description=tool_description,
                            func=tool_instance._run,  # Direct reference to method
                            coroutine=tool_instance.arun if hasattr(tool_instance, 'arun') else None,
                            args_schema=tool_instance.args_schema
                        )
                        
                        tools.append(langchain_tool)
                        logger.info(f"Successfully loaded tool: {tool_model.name}")
                    else:
                        logger.error(f"Tool class not found: {tool_model.tool_subclass}")
                except Exception as e:
                    logger.error(f"Error loading tool {tool_model.name}: {str(e)}", exc_info=True)
            
            return tools
            
        except Exception as e:
            logger.error(f"Error loading tools: {str(e)}", exc_info=True)
            return []

    def _create_tool_description(self, tool_instance, tool_model):
        """Create a detailed description for the tool"""
        try:
            base_description = tool_instance.description or tool_model.description
            schema = tool_instance.args_schema

            if schema:
                field_descriptions = []
                for field_name, field in schema.model_fields.items():
                    field_type = str(field.annotation).replace('typing.', '')
                    if hasattr(field.annotation, '__name__'):
                        field_type = field.annotation.__name__
                    
                    field_desc = field.description or ''
                    default = field.default
                    if default is Ellipsis:
                        default = "Required"
                    elif default is None:
                        default = "Optional"
                    
                    field_descriptions.append(
                        f"- {field_name} ({field_type}): {field_desc} Default: {default}"
                    )

                tool_description = f"""{base_description}

Required Parameters:
{chr(10).join(field_descriptions)}"""
                
                return tool_description
            
            return base_description

        except Exception as e:
            logger.error(f"Error creating tool description: {str(e)}")
            return base_description or "Tool description unavailable"

    def _get_format_instructions(self):
        """Get format instructions for the agent"""
        # Use raw string and double curly braces to escape them
        return """RESPONSE FORMAT INSTRUCTIONS
----------------------------

When you have a final response to say to the Human, you MUST use the format:

{{{{
    "action": "Final Answer",
    "action_input": "your response here"
}}}}

When using tools, you MUST use the format:

{{{{
    "action": "{tool_names}",
    "action_input": {{{{
        "param1": "value1",
        "param2": "value2"
    }}}}
}}}}

For analytics data:
1. After receiving data, format it into a clear, readable response
2. Use the Final Answer format to return the formatted data
3. Do not make additional tool calls after getting successful data

Remember:
- Always use exact parameter names from tool descriptions
- All dates should be in YYYY-MM-DD format
- Get client_id from context
- Include all required parameters
"""

    async def _handle_error(self, error_message):
        """Handle errors during execution"""
        logger.error(error_message)
        await self.send(text_data=json.dumps({
            'message': f"Error: {error_message}",
            'is_agent': True,
            'error': True
        }))

    @database_sync_to_async
    def get_agent(self, agent_id):
        """Get agent from database"""
        try:
            return Agent.objects.get(id=agent_id)
        except Agent.DoesNotExist:
            logger.error(f"Agent with id {agent_id} not found")
            raise
        except Exception as e:
            logger.error(f"Error getting agent: {str(e)}")
            raise

    async def save_message(self, content, agent_id, is_agent, model):
        """Save chat message to database - async wrapper"""
        try:
            await database_sync_to_async(self._save_message_sync)(
                content, agent_id, is_agent, model
            )
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            raise

    def _save_message_sync(self, content, agent_id, is_agent, model):
        """Synchronous method to save chat message to database"""
        return ChatMessage.objects.create(
            session_id=self.session_id,
            agent_id=agent_id,
            user_id=self.scope["user"].id,
            content=content,
            is_agent=is_agent,
            model=model
        )

    def _format_client_context(self, client_data):
        """Format client context for prompt template"""
        if not client_data:
            return ""
            
        # Format business objectives as a bulleted list
        objectives_text = ""
        if client_data.get('business_objectives'):
            objectives_text = "\nBusiness Objectives:"
            if isinstance(client_data['business_objectives'], list):
                for obj in client_data['business_objectives']:
                    objectives_text += f"""
• Goal: {obj.get('goal', 'Not set')}
  Metric: {obj.get('metric', 'Not set')}
  Target Date: {obj.get('target_date', 'Not set')}
  Status: {'Active' if obj.get('status') else 'Inactive'}"""
        
        return f"""
Client Context:
Client ID: {client_data.get('client_id', 'Not provided')}
Current Date: {client_data.get('current_date', timezone.now().date().isoformat())}
Name: {client_data.get('name', 'Not provided')}
Website: {client_data.get('website', 'Not provided')}
Industry: {client_data.get('industry', 'Not provided')}
Service Area: {client_data.get('service_area', 'Not provided')}
Client Profile: {client_data.get('profile', 'Not provided')}
Target Audience: {client_data.get('target_audience', 'Not provided')}
{objectives_text}
"""

    def _get_system_prompt_template(self):
        """Get the system prompt template"""
        return """
Role: {role}
Backstory: {backstory}
Goal: {goal}
{client_context}

You have access to the client's data above. When using tools:
1. Extract all required parameters from the client context
2. Use proper date formats (YYYY-MM-DD)
3. Include the client_id from context when needed
4. Follow each tool's specific requirements

Respond to the user's message while staying in character and using the client context.
"""

    def _create_callback_handler(self):
        """Create a callback handler for logging"""
        # Return cached handler if it exists
        if self._callback_handler is not None:
            return self._callback_handler

        class WebSocketCallbackHandler(BaseCallbackHandler):
            def __init__(self, logger):
                logger = logger
                self.run_inline = True

            def on_llm_start(self, serialized, prompts, **kwargs):
                try:
                    # Log only first 100 chars of first prompt
                    prompt_preview = str(prompts[0])[:100] if prompts else "No prompt"
                    logger.debug(f"LLM starting with prompt: {prompt_preview}...")
                except Exception as e:
                    logger.error(f"Error in on_llm_start: {str(e)}")

            def on_llm_end(self, response, **kwargs):
                try:
                    generations = getattr(response, 'generations', [])
                    if generations and generations[0]:
                        output = str(generations[0][0].text)[:100]
                        logger.debug(f"LLM completed with output: {output}...")
                except Exception as e:
                    logger.error(f"Error in on_llm_end: {str(e)}")

            def on_tool_start(self, serialized, input_str, **kwargs):
                try:
                    tool_name = serialized.get('name', 'unknown')
                    logger.info(f"Starting tool execution: {tool_name}")
                except Exception as e:
                    logger.error(f"Error in on_tool_start: {str(e)}")

            def on_tool_end(self, output, **kwargs):
                try:
                    output_preview = str(output)[:100] if output else "No output"
                    logger.info(f"Tool execution completed: {output_preview}...")
                except Exception as e:
                    logger.error(f"Error in on_tool_end: {str(e)}")

            def on_chain_start(self, serialized, inputs, **kwargs):
                try:
                    input_preview = str(inputs)[:100] if inputs else "No input"
                    logger.debug(f"Chain starting with inputs: {input_preview}...")
                except Exception as e:
                    logger.error(f"Error in on_chain_start: {str(e)}")

            def on_chain_end(self, outputs, **kwargs):
                try:
                    if isinstance(outputs, dict):
                        output_preview = str(outputs.get('output', ''))[:100]
                    else:
                        output_preview = str(outputs)[:100]
                    logger.debug(f"Chain completed with outputs: {output_preview}...")
                except Exception as e:
                    logger.error(f"Error in on_chain_end: {str(e)}")

            def on_chain_error(self, error, **kwargs):
                logger.error(f"Chain error: {str(error)}")

            def on_tool_error(self, error, **kwargs):
                logger.error(f"Tool execution error: {str(error)}")

            def on_llm_error(self, error, **kwargs):
                logger.error(f"LLM error: {str(error)}")

            def on_text(self, text, **kwargs):
                try:
                    text_preview = str(text)[:100] if text else "No text"
                    logger.debug(f"Text received: {text_preview}...")
                except Exception as e:
                    logger.error(f"Error in on_text: {str(e)}")

        # Create and cache the handler
        self._callback_handler = WebSocketCallbackHandler(logger)
        return self._callback_handler

    def _create_agent_prompt(self, agent, client_data):
        """Create the agent's prompt template with client context"""
        try:
            system_template = self._get_system_prompt_template()
            
            # Format the client context
            client_context = self._format_client_context(client_data) if client_data else ""
            
            # Create the complete prompt
            prompt = system_template.format(
                role=str(getattr(agent, 'role', 'AI Assistant')),
                backstory=str(getattr(agent, 'backstory', '')),
                goal=str(getattr(agent, 'goal', 'Help the user')),
                client_context=str(client_context)
            )
            
            return prompt
            
        except Exception as e:
            logger.error(f"Error creating agent prompt: {str(e)}", exc_info=True)
            # Provide a fallback prompt in case of error
            return r"""
You are an AI assistant. Your goal is to help the user while being clear and concise.
If you encounter any issues, please let the user know and ask for clarification.

Example tool call (format your calls like this):
START_JSON
{
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "client_id": 123
}
END_JSON
"""

    async def _handle_response(self, response, agent_id, model_name):
        """Handle the agent's response"""
        try:
            # Ensure response is properly formatted
            if not isinstance(response, str):
                response = str(response)
            
            response = response.strip()
            
            # Save message to database
            await self.save_message(response, agent_id, True, model_name)
            
            # Send response to websocket
            await self.send(text_data=json.dumps({
                'message': response,
                'is_agent': True,
                'timestamp': datetime.datetime.now().isoformat()
            }))
            
        except Exception as e:
            error_msg = f"Error handling response: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self.send(text_data=json.dumps({
                'message': error_msg,
                'is_agent': True,
                'error': True
            }))
    async def _cleanup_agent_executor(self):
        """Clean up agent executor resources"""
        try:
            if self._agent_executor:
                # Clean up any resources
                if hasattr(self._agent_executor, 'aclose'):
                    await self._agent_executor.aclose()
                self._agent_executor = None
        except Exception as e:
            logger.error(f"Error cleaning up agent executor: {str(e)}")

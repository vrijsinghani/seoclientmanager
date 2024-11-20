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
      self.logger = logging.getLogger(__name__)

  async def load_tools(self, agent):
      """Load and initialize agent tools"""
      tools = []
      for tool_model in agent.tools.all():
          try:
              tool_classes = get_tool_classes(tool_model.tool_class)
              tool_class = next((cls for cls in tool_classes 
                               if cls.__name__ == tool_model.tool_subclass), None)
              
              if tool_class:
                  self.logger.info(f"Initializing tool: {tool_class.__name__}")
                  tool_instance = tool_class()
                  tools.append(tool_instance)
              else:
                  self.logger.error(f"Tool class not found: {tool_model.tool_subclass}")
          except Exception as e:
              self.logger.error(f"Error loading tool {tool_model.name}: {str(e)}")
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
              self.logger.error(f"Tool execution error: {str(e)}")
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
      self.logger = logging.getLogger(__name__)

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
          self.logger.error(f"Error getting client data: {str(e)}", exc_info=True)
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
          self.logger.error(f"Error processing objectives: {str(e)}")
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
        self.logger = logging.getLogger(__name__)
        self.session_id = str(uuid.uuid4())
        self.group_name = f"chat_{self.session_id}"
    
    async def connect(self):
        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            await self.send(text_data=json.dumps({
                'message': 'Connected to chat server',
                'is_system': True
            }))
        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}", exc_info=True)
            raise

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message = data['message']
            agent_id = data['agent_id']
            model_name = data['model']
            client_id = data.get('client_id')

            # Get agent and client data
            agent = await self.get_agent(agent_id)
            client_data = await self.client_manager.get_client_data(client_id) if client_id else None

            # Initialize agent
            agent_executor = await database_sync_to_async(self._initialize_agent)(agent, model_name, client_data)
            
            # Execute agent with proper error handling
            try:
                response = await database_sync_to_async(self._execute_agent_with_retry)(
                    agent_executor,
                    message,
                    max_retries=3
                )
            except Exception as e:
                response = f"I apologize, but I encountered an error: {str(e)}"
            
            # Save and send response
            await self._handle_response(response, agent_id, model_name)
            
        except Exception as e:
            await self._handle_error(str(e))

    def _execute_agent_with_retry(self, agent_executor, message, max_retries=3):
        """Execute agent with retry logic and proper response formatting"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Execute the agent
                response = agent_executor.run(
                    input=message,
                    callbacks=[self._create_callback_handler()]
                )
                
                # Check for successful analytics response
                if isinstance(response, str):
                    try:
                        # Try to parse as JSON
                        parsed_response = json.loads(response)
                        if isinstance(parsed_response, dict):
                            if parsed_response.get('success') is True:
                                formatted = self._format_analytics_response(parsed_response)
                                # Force agent to stop by returning final response
                                agent_executor.agent.return_values = {"output": formatted}
                                return formatted
                    except json.JSONDecodeError:
                        pass

                # Check if response contains analytics data in string form
                if isinstance(response, str) and ('analytics_data' in response or 'success' in response):
                    try:
                        # Try to extract and parse JSON from the string
                        start_idx = response.find('{')
                        end_idx = response.rfind('}') + 1
                        if start_idx >= 0 and end_idx > start_idx:
                            json_str = response[start_idx:end_idx]
                            data = json.loads(json_str)
                            if data.get('success') is True:
                                formatted = self._format_analytics_response(data)
                                # Force agent to stop by returning final response
                                agent_executor.agent.return_values = {"output": formatted}
                                return formatted
                    except (json.JSONDecodeError, ValueError):
                        pass

                # If we got any valid response, return it
                if response and str(response).strip():
                    return str(response).strip()
                
                raise Exception("Invalid or empty response from agent")
                
            except Exception as e:
                last_error = e
                self.logger.error(f"Agent execution attempt {attempt + 1} failed: {str(e)}")
                
                # Try to parse error message for success response
                error_str = str(e)
                if 'success' in error_str.lower():
                    try:
                        start_idx = error_str.find('{')
                        end_idx = error_str.rfind('}') + 1
                        if start_idx >= 0 and end_idx > start_idx:
                            error_data = json.loads(error_str[start_idx:end_idx])
                            if error_data.get('success') is True:
                                formatted = self._format_analytics_response(error_data)
                                # Force agent to stop
                                agent_executor.agent.return_values = {"output": formatted}
                                return formatted
                    except (json.JSONDecodeError, ValueError):
                        pass
                
                if attempt == max_retries - 1:
                    raise last_error
        
        raise last_error if last_error else Exception("Agent execution failed")

    def _format_analytics_response(self, response_data):
        """Format analytics data into a readable response"""
        try:
            if not response_data.get('analytics_data'):
                return "No analytics data available for the specified period."
            
            # Format the analytics data into a readable message
            data_points = response_data['analytics_data']
            formatted_response = "Here's the analytics data:\n\n"
            
            for point in data_points:
                formatted_response += "Date: {}\n".format(point.get('date', 'N/A'))
                for key, value in point.items():
                    if key != 'date':
                        formatted_response += "{}: {}\n".format(key, value)
                formatted_response += "\n"
            
            return formatted_response.strip()
            
        except Exception as e:
            self.logger.error(f"Error formatting analytics response: {str(e)}")
            return str(response_data)  # Return raw response if formatting fails

    async def _handle_response(self, response, agent_id, model_name):
        """Handle the agent's response with better error handling"""
        try:
            # Ensure response is properly formatted
            if not isinstance(response, str):
                response = str(response)
            
            response = response.strip()
            
            # Save message using sync_to_async correctly
            await self.save_message(response, agent_id, True, model_name)
            
            # Send response
            await self.send(text_data=json.dumps({
                'message': response,
                'is_agent': True,
                'timestamp': datetime.datetime.now().isoformat()
            }))
            
        except Exception as e:
            error_msg = f"Error handling response: {str(e)}"
            self.logger.error(error_msg)
            await self.send(text_data=json.dumps({
                'message': error_msg,
                'is_agent': True,
                'error': True
            }))

    def _initialize_agent(self, agent, model_name, client_data):
        """Initialize the agent with tools and memory"""
        try:
            tools = self._load_tools_sync(agent)
            llm, _ = get_llm(model_name)
            
            # Initialize memory with Django's cache backend
            message_history = DjangoCacheMessageHistory(
                session_id=self.session_id,
                ttl=3600  # 1 hour expiry
            )

            # Use ConversationBufferMemory instead of ConversationSummaryBufferMemory
            memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                chat_memory=message_history,
                output_key="output"
            )
            
            return initialize_agent(
                tools=tools,
                llm=llm,
                agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True,
                memory=memory,
                agent_kwargs={
                    "prefix": self._create_agent_prompt(agent, client_data),
                    "format_instructions": self._get_format_instructions()
                }
            )
        except Exception as e:
            self.logger.error(f"Error initializing agent: {str(e)}")
            raise

    def _load_tools_sync(self, agent):
        """Synchronously load and initialize agent tools"""
        try:
            tools = []
            for tool_model in agent.tools.all():
                try:
                    tool_classes = get_tool_classes(tool_model.tool_class)
                    tool_class = next((cls for cls in tool_classes 
                                   if cls.__name__ == tool_model.tool_subclass), None)
                    
                    if tool_class:
                        self.logger.info(f"Initializing tool: {tool_class.__name__}")
                        tool_instance = tool_class()
                        
                        # Ensure tool has required attributes
                        if not hasattr(tool_instance, 'args_schema'):
                            self.logger.error(f"Tool {tool_class.__name__} missing args_schema")
                            continue
                        
                        # Create tool description
                        tool_description = self._create_tool_description(tool_instance, tool_model)
                        
                        # Create wrapper functions
                        def create_tool_func(tool=tool_instance):
                            def tool_func(**kwargs):
                                try:
                                    self.logger.info(f"Tool input parameters: {kwargs}")
                                    return tool._run(**kwargs)
                                except Exception as e:
                                    self.logger.error(f"Tool execution error: {str(e)}")
                                    return str(e)
                            return tool_func

                        def create_async_func(tool=tool_instance):
                            async def async_func(**kwargs):
                                try:
                                    self.logger.info(f"Async tool input parameters: {kwargs}")
                                    if hasattr(tool, 'arun'):
                                        return await tool.arun(**kwargs)
                                    return await database_sync_to_async(tool._run)(**kwargs)
                                except Exception as e:
                                    self.logger.error(f"Async tool execution error: {str(e)}")
                                    return str(e)
                            return async_func

                        # Create Langchain tool
                        langchain_tool = StructuredTool(
                            name=tool_model.name,
                            description=tool_description,
                            func=create_tool_func(),
                            coroutine=create_async_func(),
                            args_schema=tool_instance.args_schema
                        )
                        
                        tools.append(langchain_tool)
                        self.logger.info(f"Successfully loaded tool: {tool_model.name}")
                    else:
                        self.logger.error(f"Tool class not found: {tool_model.tool_subclass}")
                except Exception as e:
                    self.logger.error(f"Error loading tool {tool_model.name}: {str(e)}", exc_info=True)
                    
            return tools
        except Exception as e:
            self.logger.error(f"Error loading tools: {str(e)}", exc_info=True)
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
            self.logger.error(f"Error creating tool description: {str(e)}")
            return base_description or "Tool description unavailable"

    def _get_format_instructions(self):
        """Get format instructions for the agent"""
        return """
When using tools:
1. Always use the exact parameter names as specified in the tool's description
2. All dates should be in YYYY-MM-DD format unless otherwise specified
3. Get the client_id from the client context
4. Make sure all required parameters are included

Always check the tool's description for specific parameter requirements.
"""

    async def _handle_error(self, error_message):
        """Handle errors during execution"""
        self.logger.error(error_message)
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
            self.logger.error(f"Agent with id {agent_id} not found")
            raise
        except Exception as e:
            self.logger.error(f"Error getting agent: {str(e)}")
            raise

    async def save_message(self, content, agent_id, is_agent, model):
        """Save chat message to database - async wrapper"""
        try:
            await database_sync_to_async(self._save_message_sync)(
                content, agent_id, is_agent, model
            )
        except Exception as e:
            self.logger.error(f"Error saving message: {str(e)}")
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
        class WebSocketCallbackHandler(BaseCallbackHandler):
            def __init__(self, logger):
                self.logger = logger
                self.run_inline = True

            def on_llm_start(self, serialized, prompts, **kwargs):
                try:
                    # Safely log only the first part of prompts
                    prompt_preview = str(prompts[0])[:100] if prompts else "No prompt"
                    self.logger.info(f"LLM starting with prompt: {prompt_preview}...")
                except Exception as e:
                    self.logger.error(f"Error in on_llm_start: {str(e)}")

            def on_llm_end(self, response, **kwargs):
                try:
                    # Safely handle LLMResult object
                    generations = getattr(response, 'generations', [])
                    if generations and generations[0]:
                        output = str(generations[0][0].text)[:100]
                        self.logger.info(f"LLM completed with output: {output}...")
                except Exception as e:
                    self.logger.error(f"Error in on_llm_end: {str(e)}")

            def on_tool_start(self, serialized, input_str, **kwargs):
                try:
                    tool_name = serialized.get('name', 'unknown')
                    self.logger.info(f"Starting tool execution: {tool_name}")
                except Exception as e:
                    self.logger.error(f"Error in on_tool_start: {str(e)}")

            def on_tool_end(self, output, **kwargs):
                try:
                    # Safely log tool output
                    output_preview = str(output)[:100] if output else "No output"
                    self.logger.info(f"Tool execution completed: {output_preview}...")
                except Exception as e:
                    self.logger.error(f"Error in on_tool_end: {str(e)}")

            def on_chain_start(self, serialized, inputs, **kwargs):
                try:
                    # Safely log chain inputs
                    input_preview = str(inputs)[:100] if inputs else "No input"
                    self.logger.info(f"Chain starting with inputs: {input_preview}...")
                except Exception as e:
                    self.logger.error(f"Error in on_chain_start: {str(e)}")

            def on_chain_end(self, outputs, **kwargs):
                try:
                    # Safely log chain outputs
                    if isinstance(outputs, dict):
                        output_preview = str(outputs.get('output', ''))[:100]
                    else:
                        output_preview = str(outputs)[:100]
                    self.logger.info(f"Chain completed with outputs: {output_preview}...")
                except Exception as e:
                    self.logger.error(f"Error in on_chain_end: {str(e)}")

            def on_chain_error(self, error, **kwargs):
                self.logger.error(f"Chain error: {str(error)}")

            def on_tool_error(self, error, **kwargs):
                self.logger.error(f"Tool execution error: {str(error)}")

            def on_llm_error(self, error, **kwargs):
                self.logger.error(f"LLM error: {str(error)}")

            def on_text(self, text, **kwargs):
                try:
                    # Safely log text
                    text_preview = str(text)[:100] if text else "No text"
                    self.logger.info(f"Text received: {text_preview}...")
                except Exception as e:
                    self.logger.error(f"Error in on_text: {str(e)}")

        return WebSocketCallbackHandler(self.logger)

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
            
            #self.logger.debug(f"Created agent prompt: {prompt}")
            return prompt
            
        except Exception as e:
            self.logger.error(f"Error creating agent prompt: {str(e)}", exc_info=True)
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
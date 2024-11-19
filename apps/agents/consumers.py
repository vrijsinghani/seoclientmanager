import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import CrewExecution, CrewMessage, ChatMessage, Agent
from django.core.cache import cache
from apps.common.utils import format_message, get_llm
import logging
import uuid

logger = logging.getLogger(__name__)

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

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = str(uuid.uuid4())
        await self.channel_layer.group_add(
            f"chat_{self.session_id}",
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            f"chat_{self.session_id}",
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        agent_id = data['agent_id']
        model_name = data['model']
        
        # Save user message
        await self.save_message(message, agent_id, False, model_name)
        
        # Get agent response
        agent = await self.get_agent(agent_id)
        llm, _ = get_llm(model_name)
        
        system_prompt = f"""Role: {agent.role}
        Backstory: {agent.backstory}
        Goal: {agent.goal}
        
        Respond to the user's message while staying in character."""
        
        response = await self.get_llm_response(llm, system_prompt, message)
        
        # Save agent response
        await self.save_message(response, agent_id, True, model_name)
        
        # Send response back to WebSocket
        await self.send(text_data=json.dumps({
            'message': response,
            'is_agent': True
        }))

    @database_sync_to_async
    def save_message(self, content, agent_id, is_agent, model):
        ChatMessage.objects.create(
            session_id=self.session_id,
            agent_id=agent_id,
            user_id=self.scope["user"].id,
            content=content,
            is_agent=is_agent,
            model=model
        )

    @database_sync_to_async
    def get_agent(self, agent_id):
        return Agent.objects.get(id=agent_id)

    async def get_llm_response(self, llm, system_prompt, user_message):
        # This is a simplified example - you might want to use async LLM calls
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        response = await llm.achat(messages)
        return response.content

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import CrewExecution, CrewMessage

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
            user_input = text_data_json.get('input')
            await self.handle_human_input(user_input)

    async def crew_execution_update(self, event):
        await self.send(text_data=json.dumps({
            'status': event['status'],
            'messages': event['messages']
        }))

    @database_sync_to_async
    def handle_human_input(self, user_input):
        execution = CrewExecution.objects.get(id=self.execution_id)
        CrewMessage.objects.create(
            execution=execution,
            agent='Human',
            content=f"Human input received: {user_input}"
        )
        # Add logic to handle the human input in your execution process

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
        await self.send(text_data=json.dumps(status_data))
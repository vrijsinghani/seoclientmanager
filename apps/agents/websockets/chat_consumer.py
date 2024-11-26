from .base import BaseWebSocketConsumer
from .handlers.message_handler import MessageHandler
from .handlers.agent_handler import AgentHandler
from ..tools.manager import AgentToolManager
from ..clients.manager import ClientDataManager
from ..chat.history import DjangoCacheMessageHistory
import logging
import uuid
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class ChatConsumer(BaseWebSocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tool_manager = AgentToolManager()
        self.client_manager = ClientDataManager()
        self.session_id = str(uuid.uuid4())
        self.group_name = f"chat_{self.session_id}"
        self.message_handler = MessageHandler(self)
        self.agent_handler = AgentHandler(self)
        self.is_connected = False

    async def connect(self):
        if self.is_connected:
            return
            
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        self.is_connected = True
        
        await self.send_json({
            'message': 'Connected to chat server',
            'is_system': True,
            'connection_status': 'connected'
        })

    async def receive(self, text_data=None, bytes_data=None):
        try:
            # Handle binary data if present
            if bytes_data:
                data = await self.handle_binary_message(bytes_data)
            else:
                data = json.loads(text_data)
                if data.get('type') != 'keep_alive':
                    logger.debug(f"📥 Received: {text_data}")

            if data.get('type') == 'keep_alive':
                await self.message_handler.handle_keep_alive()
                return

            await self.process_message(data)

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {str(e)}")
            await self.message_handler.handle_message(
                'Invalid message format', is_agent=True, error=True
            )
        except Exception as e:
            logger.error(f"❌ Error: {str(e)}")
            await self.message_handler.handle_message(
                'Internal server error', is_agent=True, error=True) 

    async def process_message(self, data):
        """Process incoming message data"""
        try:
            message = data.get('message', '').strip()
            agent_id = data.get('agent_id')
            model_name = data.get('model')
            client_id = data.get('client_id')

            if not message or not agent_id:
                await self.message_handler.handle_message(
                    'Missing required fields (message or agent_id)',
                    is_agent=True,
                    error=True
                )
                return

            # Echo user's message back with proper type
            logger.debug("📤 Sending user message")
            await self.send_json({
                'type': 'user_message',
                'message': message,
                'timestamp': datetime.now().isoformat()
            })

            # Process with agent
            logger.debug("🤖 Processing with agent")
            response = await self.agent_handler.process_response(
                message,
                agent_id,
                model_name,
                client_id
            )

            logger.debug("📤 Sending agent response")
            await self.send_json({
                'type': 'agent_message',
                'message': response,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"❌ Error: {str(e)}")
            await self.send_json({
                'type': 'error',
                'message': f"Error processing message: {str(e)}",
                'error': True
            }) 
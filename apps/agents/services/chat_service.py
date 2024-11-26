from ..utils.error_handling import handle_chat_errors, ChatError

class ChatService:
    def __init__(self, config: ChatConfig):
        self.config = config
        self.tool_manager = AgentToolManager()
        self.client_manager = ClientDataManager()
        
    @handle_chat_errors
    async def initialize_chat(self):
        """Initialize chat session with selected agent and model"""
        if not self.config.agent_id:
            raise ChatError("No agent selected", code="no_agent")
            
        agent = await self.get_agent(self.config.agent_id)
        if not agent:
            raise ChatError("Agent not found", code="agent_not_found")
            
        client_data = await self.client_manager.get_client_data(self.config.client_id)
        return await self._get_or_create_agent_executor(agent, self.config.model_name, client_data)

    @handle_chat_errors
    async def process_message(self, message: str) -> str:
        """Process a user message and return the response"""
        if not message.strip():
            raise ChatError("Empty message", code="empty_message")
            
        try:
            response = await self._agent_executor.arun(message)
            return response
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            raise ChatError("Failed to process message", code="processing_error") 
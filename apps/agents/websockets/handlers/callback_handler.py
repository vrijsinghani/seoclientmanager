from langchain_core.callbacks import BaseCallbackHandler
import logging

class WebSocketCallbackHandler(BaseCallbackHandler):
    def __init__(self, consumer):
        self.consumer = consumer
        self.logger = logging.getLogger(__name__)

    async def on_llm_start(self, serialized, prompts, **kwargs):
        self.logger.debug("LLM Start callback triggered")
        await self.consumer.message_handler.handle_message(
            "Processing your request...", 
            is_agent=True
        )

    async def on_llm_new_token(self, token: str, **kwargs):
        """Handle streaming tokens"""
        self.logger.debug(f"New token received: {token[:50]}...")
        if token and token.strip():  # Only send non-empty tokens
            await self.consumer.message_handler.handle_message(
                token,
                is_agent=True,
                is_stream=True
            )

    async def on_llm_error(self, error: str, **kwargs):
        """Handle errors"""
        self.logger.debug(f"LLM Error callback triggered: {error}")
        await self.consumer.message_handler.handle_message(
            f"Error: {error}",
            is_agent=True,
            error=True
        )

    async def on_tool_start(self, tool_name: str, tool_input: str, **kwargs):
        """Handle tool usage"""
        self.logger.debug(f"Tool start callback triggered: {tool_name}")
        await self.consumer.message_handler.handle_message(
            f"Using tool: {tool_name}\nInput: {tool_input}",
            is_agent=True
        )

    async def on_llm_end(self, response, **kwargs):
        self.logger.debug("LLM End callback triggered")
        try:
            output = response.generations[0][0].text if response.generations else ""
            if output.strip():  # Only send non-empty output
                await self.consumer.message_handler.handle_message(
                    output, 
                    is_agent=True
                )
        except Exception as e:
            self.logger.error(f"Error in on_llm_end: {str(e)}", exc_info=True)

    async def on_chain_error(self, error, **kwargs):
        self.logger.error(f"Chain error: {str(error)}")
        await self.consumer.message_handler.handle_message(
            f"Error: {str(error)}", 
            is_agent=True, 
            error=True
        )
 
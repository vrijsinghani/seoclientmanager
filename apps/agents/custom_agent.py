from crewai import Agent
from pydantic import Field, PrivateAttr

class CustomAgent(Agent):
    _custom_input_handler: callable = PrivateAttr(default=None)

    def __init__(self, *args, **kwargs):
        custom_input_handler = kwargs.pop('custom_input_handler', None)
        super().__init__(*args, **kwargs)
        self._custom_input_handler = custom_input_handler

    def set_custom_input_handler(self, handler: callable):
        self._custom_input_handler = handler

    def _ask_human_input(self, final_answer: dict) -> str:
        if self._custom_input_handler:
            return self._custom_input_handler(f"Please provide feedback on the Final Result and the Agent's actions:\n{final_answer}")
        return super()._ask_human_input(final_answer)

# Do not modify the CrewAgentExecutorMixin directly
# CrewAgentExecutorMixin._ask_human_input = CustomAgent._ask_human_input
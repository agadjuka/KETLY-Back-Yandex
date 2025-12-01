"""
Агент для вечернего приветствия
"""
from .base_agent import BaseAgent
from ..services.langgraph_service import LangGraphService
from .tools.call_manager_tools import CallManager


class EveningAgent(BaseAgent):
    """Агент для вечернего приветствия"""
    
    def __init__(self, langgraph_service: LangGraphService):
        instruction = """скажи добрый вечер"""
        
        super().__init__(
            langgraph_service=langgraph_service,
            instruction=instruction,
            tools=[CallManager],
            agent_name="Вечерний агент"
        )




"""
Агент для утреннего приветствия
"""
from .base_agent import BaseAgent
from ..services.langgraph_service import LangGraphService
from .tools.call_manager_tools import CallManager


class MorningAgent(BaseAgent):
    """Агент для утреннего приветствия"""
    
    def __init__(self, langgraph_service: LangGraphService):
        instruction = """скажи доброе утро"""
        
        super().__init__(
            langgraph_service=langgraph_service,
            instruction=instruction,
            tools=[CallManager],
            agent_name="Утренний агент"
        )




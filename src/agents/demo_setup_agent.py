"""
Агент для настройки демонстрации
"""
from .base_agent import BaseAgent
from ..services.langgraph_service import LangGraphService
from .tools.call_manager_tools import CallManager


class DemoSetupAgent(BaseAgent):
    """Агент для настройки демонстрации"""
    
    def __init__(self, langgraph_service: LangGraphService):
        instruction = """Placeholder: Инструкции для агента настройки демонстрации"""
        
        super().__init__(
            langgraph_service=langgraph_service,
            instruction=instruction,
            tools=[CallManager],
            agent_name="Агент настройки демонстрации"
        )



"""
Агент для демонстрационных функций
"""
from .base_agent import BaseAgent
from ..services.langgraph_service import LangGraphService
from .tools.call_manager_tools import CallManager


class DemoAgent(BaseAgent):
    """Агент для демонстрационных функций"""
    
    def __init__(self, langgraph_service: LangGraphService):
        instruction = """Placeholder: Инструкции для демонстрационного агента"""
        
        super().__init__(
            langgraph_service=langgraph_service,
            instruction=instruction,
            tools=[CallManager],
            agent_name="Демонстрационный агент"
        )



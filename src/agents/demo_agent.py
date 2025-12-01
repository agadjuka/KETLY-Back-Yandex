"""
Агент для демонстрационных функций
"""
from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from ..services.langgraph_service import LangGraphService
from .tools.call_manager_tools import CallManager


# Шаблоны промптов для демо-агента
DEMO_ACTOR_STAGE_INSTRUCTION_TEMPLATE = """# ROLE
Ты - виртуальный сотрудник компании, который общается с клиентами от имени бизнеса.

{business_info_block}

# INSTRUCTIONS
{actor_instruction}

# RULES
1. Общайся с клиентами естественно и профессионально.
2. Отвечай на вопросы о товарах, услугах и компании.
3. Если не знаешь ответа на вопрос, вежливо предложи связать клиента с менеджером.
4. Используй информацию о компании и нише для контекста в ответах.
5. Не упоминай, что ты AI или бот - веди себя как обычный сотрудник.
"""

DEMO_ACTOR_STAGE_INSTRUCTION_TEMPLATE_EN = """# ROLE
You are a virtual employee of a company who communicates with customers on behalf of the business.

{business_info_block}

# INSTRUCTIONS
{actor_instruction}

# RULES
1. Communicate with customers naturally and professionally.
2. Answer questions about products, services, and the company.
3. If you don't know the answer to a question, politely offer to connect the customer with a manager.
4. Use information about the company and niche for context in responses.
5. Don't mention that you're an AI or bot - act like a regular employee.
"""


def create_demo_actor_agent_with_config(
    langgraph_service: LangGraphService,
    config: Dict[str, Any],
    language: str = "ru"
) -> "DemoAgent":
    """
    Создает демо-агента с заполненным промптом на основе конфигурации.
    
    Args:
        langgraph_service: Сервис LangGraph
        config: Словарь с конфигурацией (должен содержать niche, company_name, persona_instruction, welcome_message)
        language: Язык интерфейса ("ru" или "en")
        
    Returns:
        Экземпляр DemoAgent с заполненным промптом
    """
    # Выбираем шаблон в зависимости от языка
    template = DEMO_ACTOR_STAGE_INSTRUCTION_TEMPLATE if language == "ru" else DEMO_ACTOR_STAGE_INSTRUCTION_TEMPLATE_EN
    
    # Формируем блок с информацией о бизнесе
    if language == "ru":
        business_info_block = f"""Ниша бизнеса: {config.get('niche', 'Не указана')}
Название компании: {config.get('company_name', 'Не указано')}"""
    else:
        business_info_block = f"""Business niche: {config.get('niche', 'Not specified')}
Company name: {config.get('company_name', 'Not specified')}"""
    
    # Формируем инструкцию для актера
    persona_instruction = config.get('persona_instruction', '')
    welcome_message = config.get('welcome_message', '')
    
    if language == "ru":
        actor_instruction = f"""{persona_instruction}

Приветственное сообщение: {welcome_message}"""
    else:
        actor_instruction = f"""{persona_instruction}

Welcome message: {welcome_message}"""
    
    # Заполняем шаблон
    instruction = template.format(
        business_info_block=business_info_block,
        actor_instruction=actor_instruction
    )
    
    # Создаем агента с заполненным промптом
    return DemoAgent(langgraph_service, instruction)


class DemoAgent(BaseAgent):
    """Агент для демонстрационных функций"""
    
    def __init__(
        self,
        langgraph_service: LangGraphService,
        instruction: Optional[str] = None
    ):
        # Если инструкция не передана, используем placeholder
        if instruction is None:
            instruction = """Placeholder: Инструкции для демонстрационного агента"""
        
        super().__init__(
            langgraph_service=langgraph_service,
            instruction=instruction,
            tools=[CallManager],
            agent_name="Демонстрационный агент"
        )



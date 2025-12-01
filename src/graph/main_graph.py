"""
Основной граф состояний для обработки всех стадий диалога (Responses API)
"""
from typing import Literal
from langgraph.graph import StateGraph, START, END
from .conversation_state import ConversationState
from ..agents.stage_detector_agent import StageDetectorAgent
from ..agents.morning_agent import MorningAgent
from ..agents.evening_agent import EveningAgent

from ..services.langgraph_service import LangGraphService
from ..services.logger_service import logger


class MainGraph:
    """Основной граф состояний для обработки всех стадий диалога"""
    
    # Кэш для агентов (чтобы не создавать их заново при каждом создании графа)
    _agents_cache = {}
    
    @classmethod
    def clear_cache(cls):
        """Очистить кэш агентов"""
        cls._agents_cache.clear()
    
    def __init__(self, langgraph_service: LangGraphService):
        self.langgraph_service = langgraph_service
        
        # Используем кэш для агентов
        cache_key = id(langgraph_service)
        
        if cache_key not in MainGraph._agents_cache:
            # Создаём агентов только если их ещё нет в кэше
            MainGraph._agents_cache[cache_key] = {
                'stage_detector': StageDetectorAgent(langgraph_service),
                'morning': MorningAgent(langgraph_service),
                'evening': EveningAgent(langgraph_service),
            }
        
        # Используем агентов из кэша
        agents = MainGraph._agents_cache[cache_key]
        self.stage_detector = agents['stage_detector']
        self.morning_agent = agents['morning']
        self.evening_agent = agents['evening']
        
        # Создаём граф
        self.graph = self._create_graph()
        self.compiled_graph = self.graph.compile()
    
    def _create_graph(self) -> StateGraph:
        """Создание графа состояний"""
        graph = StateGraph(ConversationState)
        
        # Добавляем узлы
        graph.add_node("detect_stage", self._detect_stage)
        graph.add_node("handle_morning", self._handle_morning)
        graph.add_node("handle_evening", self._handle_evening)
        
        # Добавляем рёбра
        graph.add_edge(START, "detect_stage")
        graph.add_conditional_edges(
            "detect_stage",
            self._route_after_detect,
            {
                "morning": "handle_morning",
                "evening": "handle_evening",
                "end": END
            }
        )
        graph.add_edge("handle_morning", END)
        graph.add_edge("handle_evening", END)
        return graph
    
    def _detect_stage(self, state: ConversationState) -> ConversationState:
        """Узел определения стадии"""
        logger.info("Определение стадии диалога")
        
        message = state["message"]
        previous_response_id = state.get("previous_response_id")
        chat_id = state.get("chat_id")
        
        # Определяем стадию
        stage_detection = self.stage_detector.detect_stage(message, previous_response_id, chat_id=chat_id)
        
        # Проверяем, был ли вызван CallManager в StageDetectorAgent
        if hasattr(self.stage_detector, '_call_manager_result') and self.stage_detector._call_manager_result:
            escalation_result = self.stage_detector._call_manager_result
            logger.info(f"CallManager был вызван в StageDetectorAgent, chat_id: {chat_id}")
            
            return {
                "answer": escalation_result.get("user_message"),
                "manager_alert": escalation_result.get("manager_alert"),
                "agent_name": "StageDetectorAgent",
                "used_tools": ["CallManager"],
                "response_id": None  # CallManager не возвращает response_id
            }
        
        return {
            "stage": stage_detection.stage
        }
    
    def _route_after_detect(self, state: ConversationState) -> Literal[
        "morning", "evening", "end"
    ]:
        """Маршрутизация после определения стадии"""
        # Если CallManager был вызван, завершаем граф
        if state.get("answer") and state.get("manager_alert"):
            logger.info("CallManager был вызван в StageDetectorAgent, завершаем граф")
            return "end"
        
        # Иначе маршрутизируем по стадии
        stage = state.get("stage", "morning")
        logger.info(f"Маршрутизация на стадию: {stage}")
        
        # Валидация стадии
        valid_stages = [
            "morning", "evening"
        ]
        
        if stage not in valid_stages:
            logger.warning(f"⚠️ Неизвестная стадия: {stage}, устанавливаю morning")
            return "morning"
        
        return stage
    
    def _process_agent_result(self, agent, answer: str, state: ConversationState, agent_name: str) -> ConversationState:
        """
        Обработка результата агента с проверкой на CallManager
        
        Args:
            agent: Экземпляр агента
            answer: Ответ агента
            state: Текущее состояние графа
            agent_name: Имя агента
            
        Returns:
            Обновленное состояние графа
        """
        used_tools = [tool["name"] for tool in agent._last_tool_calls] if hasattr(agent, '_last_tool_calls') and agent._last_tool_calls else []
        
        # Агент всегда возвращает кортеж (answer, response_id)
        # Извлекаем ответ и response_id
        if isinstance(answer, tuple) and len(answer) == 2:
            answer_text, response_id = answer
        else:
            # Если по какой-то причине не кортеж, response_id остается None
            answer_text = answer
            response_id = None
        
        # Проверяем, был ли вызван CallManager через инструмент
        if answer_text == "[CALL_MANAGER_RESULT]" and hasattr(agent, '_call_manager_result') and agent._call_manager_result:
            escalation_result = agent._call_manager_result
            chat_id = state.get("chat_id", "unknown")
            
            logger.info(f"CallManager был вызван через инструмент в агенте {agent_name}, chat_id: {chat_id}")
            
            return {
                "answer": escalation_result.get("user_message"),
                "manager_alert": escalation_result.get("manager_alert"),
                "agent_name": agent_name,
                "used_tools": used_tools,
                "response_id": response_id
            }
        
        # Обычный ответ агента
        answer = answer_text
        
        return {
            "answer": answer,
            "agent_name": agent_name,
            "used_tools": used_tools,
            "response_id": response_id
        }
    
    def _handle_morning(self, state: ConversationState) -> ConversationState:
        """Обработка утреннего приветствия"""
        logger.info("Обработка утреннего приветствия")
        message = state["message"]
        previous_response_id = state.get("previous_response_id")
        chat_id = state.get("chat_id")
        
        agent_result = self.morning_agent(message, previous_response_id, chat_id=chat_id)
        return self._process_agent_result(self.morning_agent, agent_result, state, "MorningAgent")
    
    def _handle_evening(self, state: ConversationState) -> ConversationState:
        """Обработка вечернего приветствия"""
        logger.info("Обработка вечернего приветствия")
        message = state["message"]
        previous_response_id = state.get("previous_response_id")
        chat_id = state.get("chat_id")
        
        agent_result = self.evening_agent(message, previous_response_id, chat_id=chat_id)
        return self._process_agent_result(self.evening_agent, agent_result, state, "EveningAgent")


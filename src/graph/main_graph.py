"""
Основной граф состояний для обработки всех стадий диалога (Responses API)
"""
from typing import Literal
from langgraph.graph import StateGraph, START, END
from .conversation_state import ConversationState
from ..agents.stage_detector_agent import StageDetectorAgent
from ..agents.admin_agent import AdminAgent
from ..agents.demo_agent import DemoAgent
from ..agents.demo_setup_agent import DemoSetupAgent

from ..services.langgraph_service import LangGraphService
from ..services.logger_service import logger
from ..services.session_config_service import get_session_config_service
from ..agents.demo_agent import create_demo_actor_agent_with_config
from ..storage.dialog_state_storage_factory import get_dialog_state_storage


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
        
        # Инициализация хранилища состояний диалогов
        self.dialog_state_storage = get_dialog_state_storage()
        
        # Используем кэш для агентов
        cache_key = id(langgraph_service)
        
        if cache_key not in MainGraph._agents_cache:
            # Создаём агентов только если их ещё нет в кэше
            MainGraph._agents_cache[cache_key] = {
                'stage_detector': StageDetectorAgent(langgraph_service),
                'admin': AdminAgent(langgraph_service),
                'demo': DemoAgent(langgraph_service),
                'demo_setup': DemoSetupAgent(langgraph_service),
            }
        
        # Используем агентов из кэша
        agents = MainGraph._agents_cache[cache_key]
        self.stage_detector = agents['stage_detector']
        self.admin_agent = agents['admin']
        self.demo_agent = agents['demo']
        self.demo_setup_agent = agents['demo_setup']
        
        # Создаём граф
        self.graph = self._create_graph()
        self.compiled_graph = self.graph.compile()
    
    def _create_graph(self) -> StateGraph:
        """Создание графа состояний"""
        graph = StateGraph(ConversationState)
        
        # Добавляем узлы
        graph.add_node("detect_stage", self._detect_stage)
        graph.add_node("handle_admin", self._handle_admin)
        graph.add_node("handle_demo", self._handle_demo)
        graph.add_node("handle_demo_setup", self._handle_demo_setup)
        
        # Добавляем рёбра
        graph.add_edge(START, "detect_stage")
        graph.add_conditional_edges(
            "detect_stage",
            self._route_after_detect,
            {
                "admin": "handle_admin",
                "demo": "handle_demo",
                "demo_setup": "handle_demo_setup",
                "end": END
            }
        )
        graph.add_edge("handle_admin", END)
        graph.add_edge("handle_demo", END)
        graph.add_edge("handle_demo_setup", END)
        return graph
    
    def _detect_stage(self, state: ConversationState) -> ConversationState:
        """Узел определения стадии"""
        logger.info("Определение стадии диалога")
        
        message = state["message"]
        previous_response_id = state.get("previous_response_id")
        chat_id = state.get("chat_id")
        
        # Проверяем сохраненную стадию в YDB
        saved_stage = None
        if chat_id:
            saved_stage = self.dialog_state_storage.get_stage(chat_id)
            if saved_stage:
                logger.info(f"Найдена сохраненная стадия для chat_id={chat_id}: {saved_stage}")
        
        # Если стадия найдена, используем её
        # Иначе определяем через агента
        if saved_stage:
            stage = saved_stage
            logger.info(f"Используется сохраненная стадия: {stage}")
        else:
            # Определяем стадию через агента
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
            
            stage = stage_detection.stage
            
            # Сохраняем определенную стадию в YDB
            if chat_id:
                try:
                    self.dialog_state_storage.set_stage(chat_id, stage)
                    logger.info(f"Сохранена стадия для chat_id={chat_id}: {stage}")
                except Exception as e:
                    logger.error(f"Ошибка при сохранении стадии для chat_id={chat_id}: {e}")
        
        return {
            "stage": stage
        }
    
    def _route_after_detect(self, state: ConversationState) -> Literal[
        "admin", "demo", "demo_setup", "end"
    ]:
        """Маршрутизация после определения стадии"""
        # Если CallManager был вызван, завершаем граф
        if state.get("answer") and state.get("manager_alert"):
            logger.info("CallManager был вызван в StageDetectorAgent, завершаем граф")
            return "end"
        
        # Иначе маршрутизируем по стадии
        stage = state.get("stage", "admin")
        logger.info(f"Маршрутизация на стадию: {stage}")
        
        # Валидация стадии
        valid_stages = [
            "admin", "demo", "demo_setup"
        ]
        
        if stage not in valid_stages:
            logger.warning(f"⚠️ Неизвестная стадия: {stage}, устанавливаю admin")
            return "admin"
        
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
    
    def _handle_admin(self, state: ConversationState) -> ConversationState:
        """Обработка административных функций"""
        logger.info("Обработка административных функций")
        message = state["message"]
        previous_response_id = state.get("previous_response_id")
        chat_id = state.get("chat_id")
        
        agent_result = self.admin_agent(message, previous_response_id, chat_id=chat_id)
        result = self._process_agent_result(self.admin_agent, agent_result, state, "AdminAgent")
        
        # Сохраняем стадию в YDB
        if chat_id:
            try:
                self.dialog_state_storage.set_stage(chat_id, "admin")
            except Exception as e:
                logger.error(f"Ошибка при сохранении стадии admin для chat_id={chat_id}: {e}")
        
        return result
    
    def _handle_demo(self, state: ConversationState) -> ConversationState:
        """Обработка демонстрационных функций"""
        message = state["message"]
        previous_response_id = state.get("previous_response_id")
        chat_id = state.get("chat_id")
        
        logger.info(f"🎯 [DEMO] Роутер отправил на стадию DEMO. chat_id={chat_id}, message={message[:100]}")
        
        # Получаем сервис для работы с конфигурациями сессий
        session_config_service = get_session_config_service()
        
        # Используем chat_id как thread_id
        thread_id = chat_id if chat_id else "unknown"
        
        logger.info(f"🔍 [DEMO] Проверка наличия конфигурации в базе данных для thread_id={thread_id}")
        
        # Проверяем наличие конфигурации
        config = session_config_service.load_demo_config(thread_id)
        
        # Если конфигурации нет, вызываем demo-setup агента
        if not config:
            logger.info(f"❌ [DEMO] Запись в базе данных НЕ найдена для thread_id={thread_id}")
            logger.info(f"📞 [DEMO] Обращаемся к demo-setup агенту для получения конфигурации")
            
            # Вызываем demo-setup агента
            setup_result = self.demo_setup_agent(message, previous_response_id, chat_id=chat_id)
            
            # Извлекаем ответ от demo-setup агента
            if isinstance(setup_result, tuple) and len(setup_result) == 2:
                setup_answer, setup_response_id = setup_result
            else:
                setup_answer = setup_result
                setup_response_id = None
            
            logger.info(f"📥 [DEMO] Demo-setup агент прислал ответ (длина: {len(setup_answer)} символов)")
            logger.debug(f"📥 [DEMO] Ответ demo-setup агента: {setup_answer[:500]}")
            
            # Обрабатываем ответ demo-setup агента и сохраняем конфигурацию
            # Извлекаем user_id из chat_id (если возможно)
            user_id = chat_id  # Используем chat_id как user_id
            
            logger.info(f"💾 [DEMO] Обрабатываю ответ demo-setup агента и сохраняю в базу данных для thread_id={thread_id}")
            
            saved_config = session_config_service.process_setup_response(
                thread_id=thread_id,
                user_id=user_id,
                response_text=setup_answer
            )
            
            if saved_config:
                config = saved_config
                logger.info(f"✅ [DEMO] Конфигурация успешно сохранена и загружена для thread_id={thread_id}")
                logger.info(f"📋 [DEMO] Конфигурация: niche={config.get('niche')}, company_name={config.get('company_name')}")
            else:
                # Если не удалось сохранить, пробуем загрузить еще раз
                logger.warning(f"⚠️ [DEMO] Не удалось сохранить конфигурацию, пробую загрузить еще раз для thread_id={thread_id}")
                config = session_config_service.load_demo_config(thread_id)
                if not config:
                    logger.error(f"❌ [DEMO] КРИТИЧЕСКАЯ ОШИБКА: Не удалось сохранить или загрузить конфигурацию для thread_id={thread_id}")
                    logger.error(f"❌ [DEMO] Использую базовый demo агент без конфигурации")
                    # В случае ошибки используем базовый demo агент
                    agent_result = self.demo_agent(message, previous_response_id, chat_id=chat_id)
                    return self._process_agent_result(self.demo_agent, agent_result, state, "DemoAgent")
            
            # Ответ от demo-setup агента НЕ отправляется клиенту
            logger.info(f"ℹ️ [DEMO] Ответ от demo-setup агента НЕ отправляется клиенту, продолжаю с созданием demo-агента с конфигурацией")
        else:
            logger.info(f"✅ [DEMO] Запись в базе данных НАЙДЕНА для thread_id={thread_id}")
            logger.info(f"📋 [DEMO] Загруженная конфигурация: niche={config.get('niche')}, company_name={config.get('company_name')}")
        
        # Определяем язык (пока используем "ru" по умолчанию)
        language = "ru"
        
        logger.info(f"🤖 [DEMO] Создаю demo-агента с заполненным промптом на основе конфигурации (язык: {language})")
        
        # Создаем demo-агента с заполненным промптом на основе конфигурации
        demo_agent_with_config = create_demo_actor_agent_with_config(
            langgraph_service=self.langgraph_service,
            config=config,
            language=language
        )
        
        logger.info(f"💬 [DEMO] Вызываю demo-агента с сообщением пользователя")
        
        # Вызываем demo-агента с сообщениями пользователя
        agent_result = demo_agent_with_config(message, previous_response_id, chat_id=chat_id)
        
        # Обрабатываем результат
        result = self._process_agent_result(demo_agent_with_config, agent_result, state, "DemoAgent")
        
        # Добавляем префикс "[Демонстрация] " к ответу
        if result.get("answer"):
            answer = result["answer"]
            prefix = "[Демонстрация] "
            # Проверяем, не добавлен ли уже префикс
            if not answer.startswith(prefix):
                result["answer"] = prefix + answer
            logger.info(f"📤 [DEMO] Ответ demo-агента готов (длина: {len(result['answer'])} символов), добавлен префикс '[Демонстрация]'")
        
        # Сохраняем стадию в YDB
        if chat_id:
            try:
                self.dialog_state_storage.set_stage(chat_id, "demo")
            except Exception as e:
                logger.error(f"Ошибка при сохранении стадии demo для chat_id={chat_id}: {e}")
        
        return result
    
    def _handle_demo_setup(self, state: ConversationState) -> ConversationState:
        """Обработка настройки демонстрации"""
        logger.info("Обработка настройки демонстрации")
        message = state["message"]
        previous_response_id = state.get("previous_response_id")
        chat_id = state.get("chat_id")
        
        agent_result = self.demo_setup_agent(message, previous_response_id, chat_id=chat_id)
        result = self._process_agent_result(self.demo_setup_agent, agent_result, state, "DemoSetupAgent")
        
        # Сохраняем стадию в YDB
        if chat_id:
            try:
                self.dialog_state_storage.set_stage(chat_id, "demo_setup")
            except Exception as e:
                logger.error(f"Ошибка при сохранении стадии demo_setup для chat_id={chat_id}: {e}")
        
        return result


# Архитектура LangGraph: Схема взаимодействия агентов

## Общая схема потока запроса

```
Telegram Webhook → Telegram Handler → YandexAgentService → MainGraph (State Machine) → Специализированный агент → Ответ
```

## Детальная схема обработки

### 1. Точка входа: Webhook
**Файл:** `src/api/webhook.py`
- Получает POST запрос от Telegram
- Парсит Update объект
- Вызывает `process_telegram_update(update)`

### 2. Telegram обработчик
**Файл:** `src/handlers/telegram_handlers.py`
- `handle_message()` - основной обработчик текстовых сообщений
- Вызывает `send_to_agent(user_message, chat_id)`
- Обрабатывает ответ: нормализация дат/времени, форматирование
- Отправляет ответ пользователю и в админ-панель

### 3. YandexAgentService
**Файл:** `src/services/yandex_agent_service.py`
- `send_to_agent_langgraph(chat_id, user_text)` - основной метод
- Получает `last_response_id` из YDB для продолжения диалога
- Добавляет московское время в начало сообщения
- Создает начальное состояние `ConversationState`
- Вызывает `main_graph.compiled_graph.invoke(initial_state)`
- Сохраняет `response_id` в YDB для следующего запроса
- Возвращает `{"user_message": str, "manager_alert": Optional[str]}`

### 4. MainGraph (Роутер)
**Файл:** `src/graph/main_graph.py`

#### Структура графа:
```
START → detect_stage → [conditional_edges] → handle_admin/handle_demo/handle_demo_setup → END
                    ↓
            handle_admin → [conditional_edges] → handle_demo/END
```

#### Узлы графа:
1. **detect_stage** - State Machine: проверяет команду "стоп" или читает стадию из DialogStateStorage (YDB)
2. **handle_admin** - вызывает `AdminAgent()`
3. **handle_demo** - вызывает `DemoAgent()` (с конфигурацией из БД)
4. **handle_demo_setup** - вызывает `DemoSetupAgent()`

#### Маршрутизация:
**Метод:** `_route_after_detect(state)`
- Возвращает стадию из state: "admin", "demo", "demo_setup"

**Метод:** `_route_after_admin(state)`
- Проверяет использование инструмента `SwitchToDemoTool` или маркер `[SWITCH_TO_DEMO_RESULT]`
- Если обнаружено → возвращает "demo" для переключения на демо-режим
- Иначе → возвращает "end"

#### Особенности handle_demo:
- Проверяет наличие конфигурации в БД для `thread_id=chat_id`
- Если конфигурации нет → вызывает `DemoSetupAgent`
- Обрабатывает ответ demo-setup (JSON) → сохраняет в БД
- Создает `DemoAgent` с заполненным промптом из конфигурации
- Добавляет префикс "[Демонстрация] " к ответу

### 5. DialogStateStorage (State Machine)
**Файл:** `src/storage/dialog_state_storage.py`
- Хранилище состояний диалогов в YDB
- Таблица: `dialog_states` (chat_id, current_stage)
- Методы:
  - `get_stage(chat_id)` - получает текущую стадию ("admin", "demo", "demo_setup" или None)
  - `set_stage(chat_id, stage)` - устанавливает стадию

**Логика определения стадии в `detect_stage`:**
1. Проверка команды "стоп" → устанавливает стадию "admin"
2. Иначе читает стадию из DialogStateStorage
3. Если стадия не найдена → использует "admin" по умолчанию

### 6. BaseAgent (Базовый класс всех агентов)
**Файл:** `src/agents/base_agent.py`

#### Компоненты:
- `LangGraphService` - сервис для работы с Responses API
- `ResponsesOrchestrator` - оркестратор для выполнения запросов
- `ResponsesToolsRegistry` - регистрация инструментов

#### Метод `__call__(message, previous_response_id, chat_id)`:
1. Очищает `_last_tool_calls` и `_call_manager_result`
2. Логирует запрос через `llm_request_logger`
3. Вызывает `orchestrator.run_turn(message, previous_response_id, chat_id)`
4. Сохраняет `tool_calls` в `_last_tool_calls`
5. Проверяет `call_manager` → возвращает `"[CALL_MANAGER_RESULT]", response_id`
6. Возвращает `(reply, response_id)`

### 7. ResponsesOrchestrator
**Файл:** `src/services/responses_api/orchestrator.py`

#### Метод `run_turn(user_message, previous_response_id, chat_id)`:
- Цикл до 10 итераций для обработки множественных tool_calls
- На первой итерации: передает `user_message` в API
- На последующих: передает результаты инструментов через `_build_tool_results_input()`
- Вызывает `client.create_response()` с:
  - `instructions` - системные инструкции агента
  - `input_messages` - сообщения пользователя или результаты инструментов
  - `tools` - схемы инструментов из registry
  - `previous_response_id` - для продолжения диалога
- Обрабатывает ответ:
  - Если есть `output_text` → возвращает ответ
  - Если есть `tool_calls` → выполняет инструменты → передает результаты в следующую итерацию
- Обрабатывает `CallManagerException` → возвращает специальный результат с `call_manager: True`

### 8. ResponsesAPIClient
**Файл:** `src/services/responses_api/client.py`
- Обертка над Yandex Responses API
- Метод `create_response()` - отправляет запрос к API
- Возвращает объект с `id`, `output_text`, `output` (tool_calls)

### 9. Специализированные агенты

#### AdminAgent
**Файл:** `src/agents/admin_agent.py`
- Инструкция: роль AI-администратора Ketly
- Инструменты: `CallManager`
- Обрабатывает вопросы об услугах, ценах, сроках

#### DemoAgent
**Файл:** `src/agents/demo_agent.py`
- Базовый класс для демо-агента
- `create_demo_actor_agent_with_config()` - создает агента с заполненным промптом
- Промпт формируется из конфигурации: `niche`, `company_name`, `persona_instruction`, `welcome_message`
- Инструменты: `CallManager`

#### DemoSetupAgent
**Файл:** `src/agents/demo_setup_agent.py`
- Инструкция: извлечь нишу и сгенерировать JSON конфигурации
- Возвращает JSON: `{niche, company_name, persona_instruction, welcome_message}`
- Инструменты: `CallManager`

### 10. ConversationState
**Файл:** `src/graph/conversation_state.py`
```python
{
    "message": str,                    # Исходное сообщение пользователя
    "previous_response_id": Optional[str], # ID предыдущего ответа
    "chat_id": Optional[str],          # ID чата в Telegram
    "stage": Optional[str],            # Определённая стадия ("admin", "demo", "demo_setup")
    "extracted_info": Optional[dict],  # Извлечённая информация
    "answer": str,                     # Финальный ответ пользователю
    "manager_alert": Optional[str],    # Сообщение для менеджера
    "agent_name": Optional[str],       # Имя агента, который дал ответ
    "used_tools": Optional[list],     # Список использованных инструментов
    "response_id": Optional[str]       # ID ответа для сохранения
}
```

## Обработка CallManager

### Механизм:
1. Инструмент `CallManager` вызывается в любом агенте
2. Выбрасывает `CallManagerException` с `escalation_result`
3. `ResponsesOrchestrator` ловит исключение → возвращает `{call_manager: True, manager_alert: str}`
4. `BaseAgent` проверяет `call_manager` → возвращает `"[CALL_MANAGER_RESULT]", response_id`
5. `MainGraph._process_agent_result()` проверяет `"[CALL_MANAGER_RESULT]"` → возвращает состояние с `manager_alert`
6. `MainGraph._route_after_detect()` проверяет `manager_alert` → возвращает "end"
7. `YandexAgentService` возвращает `{"user_message": str, "manager_alert": str}`
8. `telegram_handlers` отправляет уведомление в админ-панель

## Файловая структура

### Основные файлы:
- `src/api/webhook.py` - точка входа webhook
- `src/telegram_app.py` - настройка Telegram приложения
- `src/handlers/telegram_handlers.py` - обработчики сообщений
- `src/services/yandex_agent_service.py` - сервис для работы с графом
- `src/graph/main_graph.py` - основной граф LangGraph
- `src/graph/conversation_state.py` - состояние графа
- `src/agents/base_agent.py` - базовый класс агентов
- `src/agents/stage_detector_agent.py` - роутер агент
- `src/agents/admin_agent.py` - административный агент
- `src/agents/demo_agent.py` - демонстрационный агент
- `src/agents/demo_setup_agent.py` - агент настройки демо
- `src/services/responses_api/orchestrator.py` - оркестратор запросов
- `src/services/responses_api/client.py` - клиент Responses API
- `src/services/langgraph_service.py` - сервис LangGraph (конфигурация)

### Вспомогательные файлы:
- `src/services/session_config_service.py` - работа с конфигурациями сессий (БД)
- `src/storage/ydb_topic_storage.py` - хранение response_id в YDB
- `service_factory.py` - фабрика сервисов

## Поток данных

1. **Входящий запрос:**
   - Telegram Update → `webhook.py` → `telegram_handlers.handle_message()`

2. **Обработка:**
   - `handle_message()` → `send_to_agent()` → `YandexAgentService.send_to_agent_langgraph()`

3. **Граф:**
   - Создает `ConversationState` с `message`, `previous_response_id`, `chat_id`
   - Вызывает `main_graph.compiled_graph.invoke(initial_state)`

4. **Роутинг:**
   - `detect_stage` → `StageDetectorAgent.detect_stage()` → возвращает стадию
   - `_route_after_detect()` → выбирает узел: `handle_admin`, `handle_demo`, `handle_demo_setup`

5. **Выполнение агента:**
   - Выбранный агент вызывает `BaseAgent.__call__()`
   - `BaseAgent` → `ResponsesOrchestrator.run_turn()`
   - `Orchestrator` → `ResponsesAPIClient.create_response()`
   - Если нужны инструменты → выполняет их → повторяет запрос с результатами
   - Возвращает `(reply, response_id)`

6. **Обработка результата:**
   - `MainGraph._process_agent_result()` → формирует финальное состояние
   - Проверяет CallManager → добавляет `manager_alert` если нужно
   - Возвращает состояние с `answer`, `response_id`, `manager_alert`

7. **Возврат:**
   - `YandexAgentService` сохраняет `response_id` в YDB
   - Возвращает `{"user_message": answer, "manager_alert": ...}`
   - `telegram_handlers` нормализует текст → отправляет пользователю и в админ-панель

## Особенности

1. **Продолжение диалога:** `previous_response_id` передается через все уровни для поддержания контекста
2. **Кэширование агентов:** `MainGraph._agents_cache` хранит экземпляры агентов
3. **Множественные tool_calls:** `Orchestrator` обрабатывает до 10 итераций вызовов инструментов
4. **Демо-конфигурация:** Сохраняется в БД при первом вызове `DemoSetupAgent`, загружается для последующих запросов
5. **CallManager:** Специальная обработка через исключения и проверки на всех уровнях


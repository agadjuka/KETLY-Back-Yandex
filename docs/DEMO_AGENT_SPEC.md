# Спецификация агента Demosetup и Demo-актера

## 1. Префикс после сообщений Demo-актера

После всех сообщений от Demo-актера автоматически добавляется префикс "[Демонстрация] " к тексту ответа. Реализовано через функцию `prepend_prefix_to_ai_messages` в `app/app_utils/message_utils.py`. Префикс добавляется только к AIMessage со строковым контентом, дублирование предотвращается проверкой `startswith(prefix)`.

## 2. Извлечение и сохранение конфигурации от Demosetup

Функция `process_setup_response` в `app/utils/config_manager.py`:
- Принимает `thread_id` (ThreadId) и `response_text` (ответ от Demosetup агента)
- Пытается распарсить JSON напрямую через `json.loads(response_text)`
- Если не удалось - извлекает JSON из текста через `_extract_json_from_text` (ищет первую `{` и последнюю `}`)
- Проверяет наличие обязательного ключа `niche` в распарсенном словаре
- Сохраняет в Firestore через `save_demo_config(thread_id, config_data)`

Структура таблицы Firestore:
- Коллекция: `session_configs`
- Документ ID: `thread_id` (ThreadId)
- Поля документа:
  - `niche` (строка) - ниша бизнеса
  - `company_name` (строка) - название компании
  - `persona_instruction` (строка) - инструкция для актера
  - `welcome_message` (строка) - приветственное сообщение

## 3. Динамический промпт для Demo-актера

Шаблон промпта находится в `app/agents/demo_actor_stage.py`:
- `DEMO_ACTOR_STAGE_INSTRUCTION_TEMPLATE` (RU) или `DEMO_ACTOR_STAGE_INSTRUCTION_TEMPLATE_EN` (EN)
- Плейсхолдеры:
  - `{business_info_block}` - блок с информацией о бизнесе
  - `{actor_instruction}` - инструкция для актера

Функция `create_demo_actor_agent_with_config`:
- Принимает `config` (словарь из Firestore) и `language` ("ru"/"en")
- Формирует `business_info_block`:
  - RU: `"Ниша бизнеса: {niche}\nНазвание компании: {company_name}"`
  - EN: `"Business niche: {niche}\nCompany name: {company_name}"`
- Формирует `actor_instruction`:
  - RU: `"{persona_instruction}\n\nПриветственное сообщение: {welcome_message}"`
  - EN: `"{persona_instruction}\n\nWelcome message: {welcome_message}"`
- Заполняет шаблон через `.format(business_info_block=..., actor_instruction=...)`
- Создает агента через `create_react_agent` с заполненным промптом

## 4. Первое обращение к Demo-актеру (ThreadId)

При первом обращении к Demo-актеру (маршрут `demo_actor`) в функции `_handle_demo_actor_route`:
1. Проверка наличия конфигурации: `load_demo_config(thread_id)` - запрос в Firestore коллекцию `session_configs`, документ с ID = `thread_id` (ThreadId)
2. Если конфигурации нет:
   - Вызывается `demo_setup_agent` (выбор RU/EN на основе `language`)
   - Ответ обрабатывается через `process_setup_response(thread_id, msg.content)` - извлекается JSON и сохраняется в Firestore
   - Если сохранение успешно, конфигурация загружается из `saved_config`, иначе повторный запрос `load_demo_config(thread_id)`
   - Ответ от `demo_setup_agent` НЕ отправляется клиенту
3. Создается Demo-актер с заполненным промптом: `create_demo_actor_agent_with_config(config, language)`
4. Вызывается Demo-актер с сообщениями пользователя
5. К ответам добавляется префикс "[Демонстрация] " через `prepend_prefix_to_ai_messages`

Если конфигурация уже есть в Firestore - сразу создается Demo-актер с заполненным промптом, пропуская вызов `demo_setup_agent`.


"""Скрипт для создания таблицы session_configs в YDB"""
import sys
import os

# Загружаем переменные окружения из .env файла
from dotenv import load_dotenv
load_dotenv()

from src.ydb_client import YDBClient


def create_session_configs_table(client: YDBClient):
    """Создание таблицы session_configs для хранения конфигураций демо-агента"""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS session_configs (
        id String,
        user_id String,
        company_name String,
        niche String,
        persona_instruction String,
        welcome_message String,
        updated_at Timestamp,
        PRIMARY KEY (id)
    );
    """
    def _tx(session):
        return session.execute_scheme(create_table_query)
    client.pool.retry_operation_sync(_tx)


def main():
    """Создание таблицы session_configs в базе данных YDB"""
    try:
        print("🔌 Подключение к YDB...")
        client = YDBClient()
        
        print("📊 Создание таблицы session_configs...")
        create_session_configs_table(client)
        print("✅ Таблица session_configs успешно создана!")
        print("\nСтруктура таблицы session_configs:")
        print("  - id (String) - ID сессии/thread_id (PRIMARY KEY)")
        print("  - user_id (String) - ID пользователя")
        print("  - company_name (String) - Название компании")
        print("  - niche (String) - Ниша бизнеса")
        print("  - persona_instruction (String) - Персональная инструкция")
        print("  - welcome_message (String) - Приветственное сообщение")
        print("  - updated_at (Timestamp) - Время последнего обновления")
        
        client.close()
        print("\n🎉 Таблица успешно создана!")
        
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
        print("\nУбедитесь, что в переменных окружения заданы:")
        print("  - YDB_ENDPOINT")
        print("  - YDB_DATABASE")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка при создании таблицы: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()







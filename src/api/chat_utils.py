"""
Утилиты для работы с /chat endpoint
"""
from types import SimpleNamespace
from typing import Any


def create_virtual_user(thread_id: str) -> Any:
    """
    Создает виртуальный User объект из thread_id для совместимости с админ-панелью.
    
    Args:
        thread_id: UUID сессии с фронтенда
        
    Returns:
        Виртуальный User объект (SimpleNamespace с атрибутами User)
    """
    # Преобразуем thread_id в числовой ID для совместимости
    # Используем хэш от thread_id, чтобы получить стабильный числовой ID
    user_id = abs(hash(thread_id)) % (10 ** 9)  # Ограничиваем до 9 цифр
    
    # Создаем виртуальный User объект с необходимыми атрибутами
    user = SimpleNamespace(
        id=user_id,
        is_bot=False,
        first_name=f"Web User {thread_id[:8]}",
        last_name=None,
        username=None,
        full_name=f"Web User {thread_id[:8]}",
    )
    
    return user


def create_virtual_message(text: str, user: Any) -> Any:
    """
    Создает виртуальное Message объект для отправки в админ-панель.
    
    Args:
        text: Текст сообщения
        user: Виртуальный User объект
        
    Returns:
        Виртуальный Message объект (SimpleNamespace с атрибутами Message)
    """
    # Создаем виртуальный Message объект с необходимыми атрибутами
    message = SimpleNamespace(
        message_id=0,
        date=None,
        chat=SimpleNamespace(id=0),  # Фиктивный chat объект
        from_user=user,
        text=text,
        caption=None,
    )
    
    return message


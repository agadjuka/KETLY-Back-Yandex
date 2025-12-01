"""
Инструменты для работы с каталогом услуг и бронированием
"""
from .service_tools import GetServices
from .call_manager_tools import CallManager

__all__ = [
    # Инструмент получения услуг
    "GetServices",
    # Инструмент передачи менеджеру
    "CallManager",
]



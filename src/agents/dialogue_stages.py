"""
Определение стадий диалога
Соответствует стадиям из dialogue_patterns.json
"""
from enum import Enum


class DialogueStage(str, Enum):
    """Стадии диалога"""
    MORNING = "morning"                        # Утреннее приветствие
    EVENING = "evening"                        # Вечернее приветствие
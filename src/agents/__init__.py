"""
Пакет агентов для LangGraph
"""
from .base_agent import BaseAgent
from .dialogue_stages import DialogueStage
from .stage_detector_agent import StageDetectorAgent, StageDetection
from .morning_agent import MorningAgent
from .evening_agent import EveningAgent

__all__ = [
    "BaseAgent",
    "DialogueStage",
    "StageDetectorAgent",
    "StageDetection",
    "MorningAgent",
    "EveningAgent",
]


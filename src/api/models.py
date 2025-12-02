"""
Модели для API endpoints
"""
from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """Модель запроса для /chat endpoint"""
    message: str = Field(..., description="Текст сообщения пользователя")
    thread_id: str = Field(..., description="UUID сессии с фронтенда")


class WebChatResponse(BaseModel):
    """Модель ответа для /chat endpoint"""
    response: str = Field(..., description="Текст ответа от AI-агента")




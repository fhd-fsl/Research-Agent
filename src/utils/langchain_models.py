"""Utility to get LangChain Chat Models mapped to our configuration."""

import logging
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from src.config.settings import get_settings
from src.config.models import MODEL_FOR_TASK

logger = logging.getLogger(__name__)

def get_chat_model(task: str, temperature: float = 0.0) -> BaseChatModel:
    """Get a LangChain BaseChatModel for the given task, loaded from config."""
    settings = get_settings()
    
    if task not in MODEL_FOR_TASK:
        raise ValueError(f"Task '{task}' not found in MODEL_FOR_TASK config.")
        
    config = MODEL_FOR_TASK[task]
    provider = config.provider
    model_name = config.model
    
    if provider == "groq":
        return ChatOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key or "DUMMY",
            model=model_name,
            temperature=temperature,
            max_retries=3,
            timeout=settings.http_timeout,
        )
    elif provider == "openrouter":
        keys = [k.strip() for k in (settings.openrouter_api_key or "DUMMY").split(",") if k.strip()]
        
        models = [
            ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=key,
                model=model_name,
                temperature=temperature,
                max_retries=1 if i < len(keys) - 1 else 3, # Fast failover for early keys
                timeout=settings.http_timeout,
            )
            for i, key in enumerate(keys)
        ]
        
        if len(models) == 1:
            return models[0]
            
        return models[0].with_fallbacks(models[1:])
    else:
        raise ValueError(f"Unknown provider: {provider}")

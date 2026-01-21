"""Utility to provide LLM models.
TODO: support more providers and models.
TODO: add caching support.
"""

from typing import Literal

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.settings import ModelSettings

from hireme.config import cfg

SUPPORTED_MODELS = Literal[
    "llama3.1:8b",
    "qwen2.5:7b-instruct",
    "mistral:7b",
    "mistral-nemo:12b",
]


def get_llm_model(
    model: SUPPORTED_MODELS = "mistral-nemo:12b",
    model_settings: ModelSettings | None = ModelSettings(temperature=0.1),
) -> OpenAIChatModel:
    """Helpers providing LLM model from a string identifier.
    Args:
        model: Model identifier
    Returns:
        Configured LLM model
    """
    model_provider = OllamaProvider(base_url=cfg.ollama.base_url)
    custom_model = OpenAIChatModel(
        model_name=model, provider=model_provider, settings=model_settings
    )
    return custom_model

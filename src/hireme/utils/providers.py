from typing import Any, cast

from pydantic_ai.models import Model
from pydantic_ai.models.mistral import MistralModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.mistral import MistralProvider
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from hireme.config import cfg


class LLMConfigurationError(ValueError):
    """Raised when an AI command has no usable model configuration."""


def get_llm_model(model_settings: ModelSettings | None = None) -> Model:
    """Build the explicitly configured PydanticAI model."""
    if not cfg.llm_provider or not cfg.llm_model:
        raise LLMConfigurationError(
            "Set HIREME_LLM_PROVIDER and HIREME_LLM_MODEL before running AI commands."
        )

    model_name = cast(Any, cfg.llm_model)
    if cfg.llm_provider == "ollama":
        return OpenAIChatModel(
            model_name,
            provider=OllamaProvider(base_url=cfg.ollama_base_url),
            settings=model_settings,
        )

    if cfg.llm_provider == "mistral":
        if cfg.mistral_api_key is None or not cfg.mistral_api_key.get_secret_value():
            raise LLMConfigurationError(
                "Set MISTRAL_API_KEY when HIREME_LLM_PROVIDER=mistral."
            )
        return MistralModel(
            model_name,
            provider=MistralProvider(api_key=cfg.mistral_api_key.get_secret_value()),
            settings=model_settings,
        )

    if cfg.openai_api_key is None or not cfg.openai_api_key.get_secret_value():
        raise LLMConfigurationError(
            "Set OPENAI_API_KEY when HIREME_LLM_PROVIDER=openai."
        )
    return OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(api_key=cfg.openai_api_key.get_secret_value()),
        settings=model_settings,
    )

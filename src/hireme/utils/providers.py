"""Utility to provide LLM models.
TODO: support more providers and models.
TODO: refactor to a more generic provider module.
TODO: add caching support.

"""

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.settings import ModelSettings

from hireme.config import cfg

ollama_provider = OllamaProvider(base_url=cfg.ollama.base_url)
ollama_model = OpenAIChatModel(
    model_name=cfg.ollama.model,
    provider=ollama_provider,
    settings=ModelSettings(
        temperature=0.1,
    ),
)
mistral_provider = OllamaProvider(base_url=cfg.ollama.base_url)
mistral_model = OpenAIChatModel(
    model_name="mistral:7b",
    provider=mistral_provider,
    settings=ModelSettings(
        temperature=0.1,
    ),
)

# mistral_provider = MistralProvider(base_u)


def get_llm_model(model="ollama") -> OpenAIChatModel:
    """Get the configured LLM model."""
    if model == "mistral":
        return mistral_model
    elif model == "ollama":
        return ollama_model
    else:
        model_provider = OllamaProvider(base_url=cfg.ollama.base_url)
        custom_model = OpenAIChatModel(
            model_name=model,
            provider=model_provider,
            settings=ModelSettings(
                temperature=0.1,
            ),
        )
        return custom_model
        # raise ValueError(f"Unknown model: {model}")

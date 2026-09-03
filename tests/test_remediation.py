from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr
from pydantic_ai import ModelRetry
from pydantic_ai.models.mistral import MistralModel
from pydantic_ai.models.openai import OpenAIChatModel

from hireme.agents.resume_agent import _validate_resume
from hireme.cli.commands.profile.common import validate_profile_name
from hireme.config import Config, cfg
from hireme.utils.common import load_user_context_from_directory
from hireme.utils.models.models import CandidateProfile, FileContent, UserContext
from hireme.utils.models.resume_models import TailoredResume
from hireme.utils.providers import LLMConfigurationError, get_llm_model


def test_runtime_directories_are_created_only_on_request(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    config = Config(hireme_dir=runtime)

    assert not runtime.exists()
    config.ensure_directories()
    assert (runtime / "job_offers" / "processed").is_dir()
    assert (runtime / "profiles").is_dir()


def test_ai_commands_require_an_explicit_model(monkeypatch) -> None:
    monkeypatch.setattr(cfg, "llm_provider", None)
    monkeypatch.setattr(cfg, "llm_model", None)

    with pytest.raises(LLMConfigurationError, match="HIREME_LLM_PROVIDER"):
        get_llm_model()


@pytest.mark.parametrize(
    ("provider", "expected_type"),
    [
        ("ollama", OpenAIChatModel),
        ("mistral", MistralModel),
        ("openai", OpenAIChatModel),
    ],
)
def test_supported_providers_build_without_network(
    monkeypatch, provider, expected_type
) -> None:
    monkeypatch.setattr(cfg, "llm_provider", provider)
    monkeypatch.setattr(cfg, "llm_model", "test-model")
    monkeypatch.setattr(cfg, "mistral_api_key", SecretStr("test-key"))
    monkeypatch.setattr(cfg, "openai_api_key", SecretStr("test-key"))

    assert isinstance(get_llm_model(), expected_type)


def test_profile_loading_is_recursive_and_rejects_traversal(tmp_path) -> None:
    (tmp_path / "profile.yaml").write_text(
        "profile:\n  name: Ada Lovelace\n  email: ada@example.com\n  location: Paris\n",
        encoding="utf-8",
    )
    nested = tmp_path / "experience"
    nested.mkdir()
    (nested / "analytical-engine.md").write_text(
        "Analytical Engine project, 1843", encoding="utf-8"
    )

    context = load_user_context_from_directory(tmp_path)

    assert {file.filename for file in context.files} == {
        "experience/analytical-engine.md",
        "profile.yaml",
    }
    assert context.model_dump_json().count("Analytical Engine project") == 1
    with pytest.raises(ValueError):
        validate_profile_name("../escape")


def test_resume_validator_rejects_invented_numbers() -> None:
    context = UserContext(
        profile=CandidateProfile(
            name="Ada Lovelace", email="ada@example.com", location="Paris"
        ),
        files=[
            FileContent(
                filename="profile.yaml",
                file_type="yaml",
                content="Ada Lovelace, ada@example.com, Paris",
            )
        ],
    )
    resume = TailoredResume(
        name="Ada Lovelace",
        email="ada@example.com",
        location="Paris",
        education=[],
        experience=[],
        projects=[],
        skills=[],
        professional_summary="Improved performance by 42%.",
    )

    with pytest.raises(ModelRetry, match="numbers absent"):
        _validate_resume(MagicMock(deps=context), resume)


def test_resume_validator_rejects_blank_required_identity() -> None:
    context = UserContext(
        profile=CandidateProfile(
            name="Ada Lovelace", email="ada@example.com", location="Paris"
        ),
        files=[],
    )
    resume = TailoredResume(
        name="",
        email="ada@example.com",
        location="Paris",
        education=[],
        experience=[],
        projects=[],
        skills=[],
    )

    with pytest.raises(ModelRetry, match="name"):
        _validate_resume(MagicMock(deps=context), resume)

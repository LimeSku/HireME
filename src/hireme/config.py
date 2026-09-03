from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """HireME configuration loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="HIREME_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        populate_by_name=True,
    )

    llm_provider: Literal["ollama", "mistral", "openai"] | None = None
    llm_model: str | None = None
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        validation_alias="OLLAMA_BASE_URL",
    )
    mistral_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="MISTRAL_API_KEY",
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )

    logfire_enabled: bool = False
    logfire_include_content: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    hireme_dir: Path = Field(
        default_factory=lambda: Path.cwd() / ".hireme",
        validation_alias="HIREME_HOME",
    )
    configured_default_profile: Path | None = Field(
        default=None,
        validation_alias="HIREME_DEFAULT_PROFILE_PATH",
        exclude=True,
    )

    @property
    def assets_dir(self) -> Path:
        return Path(__file__).resolve().parent / "assets"

    @property
    def prompts_dir(self) -> Path:
        return self.assets_dir / "prompts"

    @property
    def job_offers_dir(self) -> Path:
        return self.hireme_dir / "job_offers"

    @property
    def profiles_dir(self) -> Path:
        return self.hireme_dir / "profiles"

    @property
    def default_profile_dir(self) -> Path:
        return self.configured_default_profile or self.profiles_dir / "default"

    def ensure_directories(self) -> None:
        """Create runtime data directories when a command needs them."""
        for directory in (
            self.hireme_dir,
            self.job_offers_dir / "raw",
            self.job_offers_dir / "processed",
            self.profiles_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


cfg = Config()

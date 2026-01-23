import structlog

from hireme.config import cfg

logger = structlog.get_logger(__name__)


class SystemPrompts:
    @staticmethod
    def resume_agent_system_prompt() -> str:
        with open(cfg.prompts_dir / "resume_agent_system_prompt.md", "r") as f:
            prompt = f.read()
        logger.debug("Loaded custom resume agent system prompt")
        return prompt

    @staticmethod
    def job_agent_system_prompt() -> str:
        with open(cfg.prompts_dir / "job_agent_system_prompt.md", "r") as f:
            prompt = f.read()
        logger.debug("Loaded custom job agent system prompt")
        return prompt

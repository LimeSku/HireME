from textwrap import dedent

from hireme.config import cfg

# Lazy-loaded langfuse client
_langfuse = None


def get_langfuse():
    """Get or create the Langfuse client lazily."""
    global _langfuse
    if _langfuse is None:
        from langfuse import get_client

        _langfuse = get_client()
    return _langfuse


# example config with a model and temperature
# config = {"model": get_llm_model(), "temperature": 0.1}

"""

{
            "role": "user",
            "content": "UserContext (as json):\n\n```{{user_context}}```",
        },
        {
            "role": "user",
            "content": "JobDescription (as json):\n\n```{{job_description}}```",
        },
        {
            "role": "user",
            "content": "Generate a tailored resume based on the job description.",
        },
"""


def setup_lgfuse_prompts(prompt_name, prompt_file, prompt_role: str = "system"):
    langfuse = get_langfuse()
    system_prompt = cfg.prompts_dir / f"{prompt_file}.md"

    # Example prompt registration
    langfuse.create_prompt(
        name=prompt_name,
        type="text",
        prompt=system_prompt.read_text(),
        labels=["dev"],  # directly promote to production
    )


def setup_all_prompts():
    """Setup all Langfuse prompts. Call this explicitly when needed."""
    langfuse = get_langfuse()
    setup_lgfuse_prompts("system_resume_agent", "resume_agent_system_prompt")
    langfuse.create_prompt(
        name="resume_agent_text",
        type="text",
        prompt=dedent(
            """
        UserContext (as json):
        ```
        {{user_context}}
        ```

        JobDescription (as json):
        ```
        {{job_description}}
        ```
        Generate a tailored resume based on the job description.
        """
        ),
        labels=["dev"],  # directly promote to production
    )


# Only run setup when this module is executed directly
if __name__ == "__main__":
    setup_all_prompts()

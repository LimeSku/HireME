from textwrap import dedent

from langfuse import get_client

from hireme.config import cfg

langfuse = get_client()

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
    system_prompt = cfg.prompts_dir / f"{prompt_file}.md"

    # Example prompt registration
    langfuse.create_prompt(
        name=prompt_name,
        type="text",
        prompt=system_prompt.read_text(),
        labels=["dev"],  # directly promote to production
    )


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

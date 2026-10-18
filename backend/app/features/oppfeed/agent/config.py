"""Agent-specific configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    """Agent pipeline configuration."""

    model_config = SettingsConfigDict(env_prefix="AGENT_", extra="ignore")

    # Pipeline
    max_pages_per_run: int = 120
    max_llm_calls_per_run: int = 200
    max_tokens_per_run: int = 200000

    # Search targets
    target_opportunities: int = 70
    max_results_per_run: int = 100

    # Search
    searxng_url: str = "http://localhost:8080"
    searxng_timeout: int = 10
    ddg_max_results: int = 15

    # Fetching
    fetch_timeout: int = 30
    user_agent: str = "OppFeedAgent/1.0 (Educational Project; +https://oppfeed.local/bot)"
    respect_robots_txt: bool = True

    # Verification
    scam_keywords: list[str] = [
        "registration fee",
        "refundable deposit",
        "pay to apply",
        "processing fee",
        "money guaranteed",
    ]
    min_confidence_threshold: float = 0.5

    # Prompts
    prompts_dir: str = "agent/prompts"


config = AgentConfig()

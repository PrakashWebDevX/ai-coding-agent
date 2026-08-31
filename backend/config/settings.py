"""
Centralized application configuration.
All environment variables are loaded and validated here using pydantic-settings.
No other module should call os.environ directly.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM providers (free tier only) ---
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    primary_model: str = "groq/openai/gpt-oss-120b"
    fallback_model: str = "openrouter/meta-llama/llama-3.3-70b-instruct:free"

    # --- Browser automation ---
    chrome_remote_debug_port: int = 9222
    browser_headless: bool = False
    browser_timeout_ms: int = 30000

    # --- Agent behavior ---
    default_language: str = "python"
    max_retry_count: int = 5
    retry_backoff_seconds: int = 2

    # --- Database ---
    sqlite_db_path: str = "./database/app.db"
    chroma_persist_dir: str = "./database/chroma"
    redis_url: str = "redis://localhost:6379/0"
    use_redis_cache: bool = False

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # --- Logging ---
    log_level: str = "INFO"

    @property
    def sqlite_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.sqlite_db_path}"


@lru_cache
def get_settings() -> Settings:
    """Settings are cached as a singleton for the process lifetime."""
    return Settings()

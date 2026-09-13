from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DIRECT_URL: str = Field("", env="DIRECT_URL")
    DEBUG: bool = Field(False, env="DEBUG")
    SECRET_KEY: str = Field(..., env="BETTER_AUTH_SECRET")
    BETTER_AUTH_URL: str = Field("", env="BETTER_AUTH_URL")
    API_URL: str = Field("http://localhost:3001", env="API_URL")
    APP_URL: str = Field("http://localhost:3000", env="APP_URL")
    REDIS_URL: Optional[str] = Field(None, env="REDIS_URL")
    BLOB_READ_WRITE_TOKEN: Optional[str] = Field(None, env="BLOB_READ_WRITE_TOKEN")
    AGENT_BRIDGE_SECRET: Optional[str] = Field(None, env="AGENT_BRIDGE_SECRET")
    ALLOWED_SIGN_IN: str = Field("", env="ALLOWED_SIGN_IN")
    CRON_SECRET: str = Field("", env="CRON_SECRET")
    CONTEXT_DEV_API_KEY: Optional[str] = Field(None, env="CONTEXT_DEV_API_KEY")
    PERPLEXITY_API_KEY: Optional[str] = Field(None, env="PERPLEXITY_API_KEY")
    AI_GATEWAY_API_KEY: Optional[str] = Field(None, env="AI_GATEWAY_API_KEY")
    GOOGLE_CLIENT_ID: Optional[str] = Field(None, env="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(None, env="GOOGLE_CLIENT_SECRET")
    MICROSOFT_CLIENT_ID: Optional[str] = Field(None, env="MICROSOFT_CLIENT_ID")
    MICROSOFT_CLIENT_SECRET: Optional[str] = Field(None, env="MICROSOFT_CLIENT_SECRET")
    MICROSOFT_TENANT_ID: str = Field("common", env="MICROSOFT_TENANT_ID")
    IS_MARKETING: str = Field("", env="IS_MARKETING")
    AGENT_MODEL_ID: Optional[str] = Field(None, env="AGENT_MODEL_ID")
    OLLAMA_BASE_URL: str = Field("http://localhost:11434", env="OLLAMA_BASE_URL")
    OLLAMA_MODEL: str = Field("llama3.1", env="OLLAMA_MODEL")
    GROQ_API_KEY: Optional[str] = Field(None, env="GROQ_API_KEY")
    GROQ_MODEL: str = Field("llama-3.1-70b-versatile", env="GROQ_MODEL")
    REPORTING_CURRENCY: str = Field("USD", env="REPORTING_CURRENCY")
    ARCHIVE_RETENTION_DAYS: int = Field(180, env="ARCHIVE_RETENTION_DAYS")
    CACHE_TTL_MS: int = Field(60000, env="CACHE_TTL_MS")
    ENRICHMENT_POLL_MS: int = Field(30000, env="ENRICHMENT_POLL_MS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

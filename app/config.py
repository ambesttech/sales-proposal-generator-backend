from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/proposals"
    )
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-70b-versatile"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Groq on-demand tiers enforce low TPM; large prompts + high max_tokens exceed per-request limits.
    groq_max_tokens_intake: int = 1024
    groq_max_tokens_requirements: int = 1200
    groq_max_tokens_writer: int = 2048
    groq_max_tokens_review: int = 1200
    groq_max_tokens_retrieval: int = 384
    groq_clip_raw_requirements_chars: int = 5000
    groq_clip_brief_chars: int = 3500
    groq_clip_requirements_json_chars: int = 4000
    groq_clip_proposal_review_chars: int = 7000
    groq_clip_retrieval_brief_chars: int = 2000
    groq_clip_retrieval_req_chars: int = 2500
    groq_clip_retrieval_context_chars: int = 4500


settings = Settings()

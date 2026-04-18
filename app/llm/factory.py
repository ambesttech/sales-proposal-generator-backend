from langchain_groq import ChatGroq

from app.config import settings


def get_chat_model() -> ChatGroq:
    """Plain text completion (e.g. intake)."""
    return ChatGroq(
        model=settings.groq_model,
        temperature=0.25,
        api_key=settings.groq_api_key or None,
        max_tokens=settings.groq_max_tokens_intake,
    )


def get_chat_model_json(*, max_tokens: int | None = None) -> ChatGroq:
    """
    JSON-only responses for Groq. Avoids LangChain tool-calling / function-call
    paths that often fail on Groq with ``tool_use_failed``.
    """
    return ChatGroq(
        model=settings.groq_model,
        temperature=0.25,
        api_key=settings.groq_api_key or None,
        max_tokens=max_tokens if max_tokens is not None else settings.groq_max_tokens_writer,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

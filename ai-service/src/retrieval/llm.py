# Third-party
from langchain_openai import ChatOpenAI

# Local
from src.shared.settings import settings

def _make_llm(temperature: float) -> ChatOpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=temperature,
        request_timeout=60,
        api_key=settings.openai_api_key,
    )


class _LazyChatOpenAI:
    def __init__(self, temperature: float):
        self._temperature = temperature
        self._instance: ChatOpenAI | None = None

    def _get(self) -> ChatOpenAI:
        if self._instance is None:
            self._instance = _make_llm(self._temperature)
        return self._instance

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._get(), name)


SUPERVISOR_LLM = _LazyChatOpenAI(temperature=0.1)
REWRITER_LLM = _LazyChatOpenAI(temperature=0.3)
DECOMPOSER_LLM = _LazyChatOpenAI(temperature=0.2)
CRAG_EVALUATOR_LLM = _LazyChatOpenAI(temperature=0.0)
GENERATOR_LLM = _LazyChatOpenAI(temperature=0.2)
HALLUCINATION_CHECKER_LLM = _LazyChatOpenAI(temperature=0.0)

__all__ = [
    "SUPERVISOR_LLM",
    "REWRITER_LLM",
    "DECOMPOSER_LLM",
    "CRAG_EVALUATOR_LLM",
    "GENERATOR_LLM",
    "HALLUCINATION_CHECKER_LLM",
]

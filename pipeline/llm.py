from functools import lru_cache

from langchain_anthropic import ChatAnthropic


@lru_cache
def get_llm() -> ChatAnthropic:
    return ChatAnthropic(model="claude-sonnet-4-6", temperature=0.3)

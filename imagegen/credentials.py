import os

# Maps internal provider IDs (imagegen.config.PROVIDERS values) to the env var
# that should supply their API key.
_PROVIDER_ENV_VAR = {
    "gpt-image-2": "OPENAI_API_KEY",
    "gpt-image-1": "OPENAI_API_KEY",
    "imagen-3": "GEMINI_API_KEY",
    "nano-banana": "GEMINI_API_KEY",
}


def resolve_api_key(provider_id: str) -> tuple[str, str]:
    """Returns (api_key, source) where source is "env" or "manual".

    Prefers the environment variable for the given provider; callers should
    fall back to (or offer an override via) a manual UI text input only when
    source == "manual" (no env value was found). A manually-entered key is
    never written back to the environment or persisted to disk — it lives
    only in the caller's session state, matching the existing "keys never
    stored" guarantee.
    """
    env_var = _PROVIDER_ENV_VAR.get(provider_id)
    env_value = os.getenv(env_var, "") if env_var else ""
    return (env_value, "env") if env_value else ("", "manual")

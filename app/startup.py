from collections.abc import Mapping
import os
from os import environ


def _value(env: Mapping[str, str], key: str) -> str:
    return env.get(key, "").strip()


def _parse_allowed_namespaces() -> set[str]:
    return {
        item.strip()
        for item in os.getenv("WRITE_ALLOWED_NAMESPACES", "").split(",")
        if item.strip()
    }


def validate_startup_config(env: Mapping[str, str] | None = None) -> None:
    config = env if env is not None else environ
    errors: list[str] = []

    model_name = _value(config, "MODEL_NAME")
    model_api_key = _value(config, "MODEL_API_KEY")
    portkey_api_key = _value(config, "PORTKEY_API_KEY")
    telegram_bot_token = _value(config, "TELEGRAM_BOT_TOKEN")
    telegram_chat_id = _value(config, "TELEGRAM_CHAT_ID")
    telegram_allowed_chat_ids = _value(config, "TELEGRAM_ALLOWED_CHAT_IDS")

    if not model_name:
        errors.append("MODEL_NAME is required.")
    if not model_api_key and not portkey_api_key:
        errors.append("One of MODEL_API_KEY or PORTKEY_API_KEY is required.")

    if telegram_bot_token and not telegram_chat_id:
        errors.append("TELEGRAM_CHAT_ID must be set when TELEGRAM_BOT_TOKEN is configured.")
    if telegram_chat_id and not telegram_bot_token:
        errors.append("TELEGRAM_BOT_TOKEN must be set when TELEGRAM_CHAT_ID is configured.")
    if telegram_allowed_chat_ids and not telegram_bot_token:
        errors.append("TELEGRAM_BOT_TOKEN must be set when TELEGRAM_ALLOWED_CHAT_IDS is configured.")

    if errors:
        message = "Startup configuration invalid:\n- " + "\n- ".join(errors)
        raise ValueError(message)


def validate_startup_environment() -> None:
    allowed_namespaces = _parse_allowed_namespaces()
    if allowed_namespaces:
        return
    raise RuntimeError(
        "Invalid startup configuration: WRITE_ALLOWED_NAMESPACES must be set to at least one namespace."
    )

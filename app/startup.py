import os


def _parse_allowed_namespaces() -> set[str]:
    return {
        item.strip()
        for item in os.getenv("WRITE_ALLOWED_NAMESPACES", "").split(",")
        if item.strip()
    }


def validate_startup_environment() -> None:
    allowed_namespaces = _parse_allowed_namespaces()
    if allowed_namespaces:
        return
    raise RuntimeError(
        "Invalid startup configuration: WRITE_ALLOWED_NAMESPACES must be set to at least one namespace."
    )

from fastapi import HTTPException


def raise_http_error(status_code: int, code: str, message: str) -> None:
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def telegram_error_message(code: str, message: str) -> str:
    return f"[{code}] {message}"

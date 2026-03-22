# app/utils/api_config.py
import os
from pathlib import Path
from dotenv import dotenv_values

_ENV_PATH = Path(".env")

def _get_api_base() -> str:
    env  = dotenv_values(_ENV_PATH) if _ENV_PATH.exists() else {}
    host = env.get("API_HOST", os.getenv("API_HOST", "127.0.0.1"))
    port = env.get("API_PORT", os.getenv("API_PORT", "8004"))
    return f"http://{host}:{port}"

def _get_timeout() -> int:
    env = dotenv_values(_ENV_PATH) if _ENV_PATH.exists() else {}
    try:
        return int(env.get("API_TIMEOUT", os.getenv("API_TIMEOUT", "30")))
    except (ValueError, TypeError):
        return 30

def _get_endpoint(path: str) -> str:
    return f"{get_api_base()}{path}"
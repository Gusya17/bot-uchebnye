# Клиент OpenRouter — отправляет текст пользователя в LLM и возвращает ответ.
# Системный промпт загружается из system_prompt.md один раз при первом вызове.

import os
import logging
import pathlib

import aiohttp

log = logging.getLogger(__name__)

_MODEL = "openai/gpt-oss-20b:free"
_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_PROMPT_FILE = pathlib.Path(__file__).parent / "system_prompt.md"

# Кэш системного промпта — читаем файл только один раз
_system_prompt: str | None = None


def _load_system_prompt() -> str:
    global _system_prompt
    if _system_prompt is None:
        try:
            _system_prompt = _PROMPT_FILE.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            log.warning("system_prompt.md не найден — использую заглушку")
            _system_prompt = "Ты помощник сервиса учебных работ. Отвечай вежливо и коротко."
    return _system_prompt


async def ask(user_text: str) -> str | None:
    """Отправляет сообщение пользователя в OpenRouter.

    Возвращает текст ответа или None при любой ошибке.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        log.error("OPENROUTER_API_KEY не задан в .env")
        return None

    payload = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": _load_system_prompt()},
            {"role": "user", "content": user_text},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                _API_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    log.error("OpenRouter вернул %s: %s", resp.status, body[:200])
                    return None
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception:
        log.exception("Ошибка запроса к OpenRouter")
        return None

"""Persistent keyword config for poll answer classification."""
import json
from pathlib import Path

_FILE = Path.home() / ".config" / "vk_poll_tracker" / "keywords.json"

_DEFAULTS: dict = {
    "poll_keyword": "тренировка",
    "yes": ["буду", "приду", "да", "я"],
    "no":  ["не буду", "нет", "не"],
    "org": ["для"],
}


def load_keywords() -> dict:
    if _FILE.exists():
        try:
            data = json.loads(_FILE.read_text(encoding="utf-8"))
            result = {k: data.get(k, _DEFAULTS[k]) for k in _DEFAULTS}
            return result
        except Exception:
            pass
    return {k: (list(v) if isinstance(v, list) else v) for k, v in _DEFAULTS.items()}


def load_poll_keyword() -> str:
    return load_keywords().get("poll_keyword", _DEFAULTS["poll_keyword"])


def save_keywords(kw: dict) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(kw, ensure_ascii=False, indent=2), encoding="utf-8")

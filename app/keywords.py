"""Persistent keyword config for poll answer classification."""
import json
from pathlib import Path

_FILE = Path.home() / ".config" / "vk_poll_tracker" / "keywords.json"

_DEFAULTS: dict[str, list[str]] = {
    "yes": ["буду", "приду", "да", "я"],
    "no":  ["не буду", "нет", "не"],
    "org": ["для"],
}


def load_keywords() -> dict[str, list[str]]:
    if _FILE.exists():
        try:
            data = json.loads(_FILE.read_text(encoding="utf-8"))
            # Ensure all keys present
            return {k: data.get(k, _DEFAULTS[k]) for k in _DEFAULTS}
        except Exception:
            pass
    return {k: list(v) for k, v in _DEFAULTS.items()}


def save_keywords(kw: dict[str, list[str]]) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(kw, ensure_ascii=False, indent=2), encoding="utf-8")

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PICDIR = Path(__file__).resolve().parent / 'pic'
_MAP_PATH = Path(__file__).resolve().parent / 'icon_map.json'
_UNKNOWN_LOG = Path(__file__).resolve().parent.parent / 'data' / 'unknown_conditions.log'

_rules: list[dict] | None = None
_fallback: str = 'wi-cloud.bmp'
_logged_unknowns: set[str] | None = None


def _load() -> None:
    global _rules, _fallback
    with open(_MAP_PATH) as f:
        data = json.load(f)
    _rules = data['rules']
    _fallback = data.get('fallback', 'wi-cloud.bmp')


def _known_unknowns() -> set[str]:
    global _logged_unknowns
    if _logged_unknowns is None:
        _logged_unknowns = set()
        if _UNKNOWN_LOG.exists():
            _logged_unknowns = {line.strip() for line in _UNKNOWN_LOG.read_text().splitlines() if line.strip()}
    return _logged_unknowns


def _log_unknown(condition: str) -> None:
    known = _known_unknowns()
    if condition in known:
        return
    known.add(condition)
    try:
        _UNKNOWN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_UNKNOWN_LOG, 'a') as f:
            f.write(f"{condition}\n")
    except OSError as e:
        logger.debug(f"Could not write unknown_conditions.log: {e}")


def get_icon_path(condition: str, is_night: bool = False) -> Path:
    """Return the BMP path for a weather condition string.

    Matches by scanning lowercased condition text against ordered keyword rules.
    When is_night=True, prefers the rule's night_icon over icon if present and on disk.
    Logs unmatched conditions to data/unknown_conditions.log and returns the fallback icon.
    """
    if _rules is None:
        _load()

    if not condition:
        return _PICDIR / _fallback

    lower = condition.lower()

    for entry in _rules:
        if all(kw in lower for kw in entry['match']):
            if is_night and 'night_icon' in entry:
                night_path = _PICDIR / entry['night_icon']
                if night_path.exists():
                    return night_path
            icon_path = _PICDIR / entry['icon']
            if icon_path.exists():
                return icon_path
            logger.warning("Icon file missing for condition %r: %s", condition, icon_path)

    logger.warning("No icon mapping for condition: %r", condition)
    _log_unknown(condition)
    return _PICDIR / _fallback

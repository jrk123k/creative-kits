"""Speaking rate and punctuation pauses. Edit vo_rates.yaml; do not hard-code a one-off."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_RATE = 4.5
DEFAULT_TIGHT_MARGIN = 0.40
DEFAULT_PAUSES = {
    "comma": 0.20,
    "semicolon": 0.30,
    "colon": 0.25,
    "period": 0.40,
    "question": 0.45,
    "excl_mark": 0.40,
    "ellipsis": 0.50,
    "emdash": 0.30,
    "endash": 0.15,
}
_TOP_KEYS = {"version", "speaking_rate_syllables_per_second", "tight_margin_seconds", "pauses"}


class RatesError(Exception):
    """The rates file is unreadable or a value is not a duration."""


@dataclass(frozen=True)
class Rates:
    speaking_rate_syllables_per_second: float = DEFAULT_RATE
    tight_margin_seconds: float = DEFAULT_TIGHT_MARGIN
    pauses: dict[str, float] | None = None
    source: str = ""

    def __post_init__(self) -> None:
        if self.pauses is None:
            object.__setattr__(self, "pauses", dict(DEFAULT_PAUSES))

    def as_dict(self) -> dict[str, object]:
        return {
            "speaking_rate_syllables_per_second": self.speaking_rate_syllables_per_second,
            "tight_margin_seconds": self.tight_margin_seconds,
            "pauses": dict(self.pauses or {}),
            "source": self.source,
        }


def default_rates() -> Rates:
    return Rates(source="built-in default (4.5 syllables/s)")


def load_rates(path: Path) -> Rates:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RatesError(f"{path}: {exc}") from exc
    except OSError as exc:
        raise RatesError(f"{path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RatesError(f"{path}: the file must be a mapping")
    unknown = set(raw) - _TOP_KEYS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise RatesError(f"{path}: unknown key(s): {names}")
    version = raw.get("version", 1)
    if version != 1:
        raise RatesError(f"{path}: unsupported version {version!r} (this checker reads version 1)")
    rate = _number(
        raw.get("speaking_rate_syllables_per_second", DEFAULT_RATE),
        path,
        "speaking_rate_syllables_per_second",
    )
    if rate <= 0:
        raise RatesError(f"{path}: speaking_rate_syllables_per_second must be greater than 0")
    tight = _number(raw.get("tight_margin_seconds", DEFAULT_TIGHT_MARGIN), path, "tight_margin_seconds")
    if tight < 0:
        raise RatesError(f"{path}: tight_margin_seconds must be 0 or greater")
    pauses = dict(DEFAULT_PAUSES)
    custom = raw.get("pauses", {})
    if custom is None:
        custom = {}
    if not isinstance(custom, dict):
        raise RatesError(f"{path}: pauses must be a mapping of punctuation names to seconds")
    extra = set(custom) - set(DEFAULT_PAUSES)
    if extra:
        names = ", ".join(sorted(extra))
        known = ", ".join(sorted(DEFAULT_PAUSES))
        raise RatesError(f"{path}: unknown pause(s): {names}. Use: {known}")
    for key, value in custom.items():
        seconds = _number(value, path, f"pauses.{key}")
        if seconds < 0:
            raise RatesError(f"{path}: pauses.{key} must be 0 or greater")
        pauses[key] = seconds
    return Rates(
        speaking_rate_syllables_per_second=rate,
        tight_margin_seconds=tight,
        pauses=pauses,
        source=str(path),
    )


def _number(value: object, path: Path, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RatesError(f"{path}: {field} must be a number of seconds")
    return float(value)

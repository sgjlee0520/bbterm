from __future__ import annotations

import re
from dataclasses import dataclass

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,6}([.\-][A-Z0-9]{1,4})?$")


@dataclass(frozen=True)
class LoadSymbol:
    symbol: str


@dataclass(frozen=True)
class AddSymbol:
    symbol: str


@dataclass(frozen=True)
class RemoveSymbol:
    symbol: str


@dataclass(frozen=True)
class ShowChart:
    pass


@dataclass(frozen=True)
class ShowStats:
    pass


@dataclass(frozen=True)
class ShowFundamentals:
    pass


@dataclass(frozen=True)
class ShowFilings:
    pass


@dataclass(frozen=True)
class Help:
    pass


@dataclass(frozen=True)
class Unknown:
    text: str


def _is_symbol(token: str) -> bool:
    return bool(_SYMBOL_RE.match(token))


def parse_command(text: str):
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return Unknown(text)
    parts = cleaned.split(" ")
    verb = parts[0].upper()
    arg = parts[1].upper() if len(parts) > 1 else None

    if verb in ("ADD",):
        return AddSymbol(arg) if arg and _is_symbol(arg) else Unknown(text)
    if verb in ("DEL", "REMOVE"):
        return RemoveSymbol(arg) if arg and _is_symbol(arg) else Unknown(text)
    if verb == "GP":
        return ShowChart()
    if verb == "DES":
        return ShowStats()
    if verb == "FA":
        return ShowFundamentals()
    if verb == "FIL":
        return ShowFilings()
    if verb in ("?", "HELP"):
        return Help()
    if arg is None and _is_symbol(verb):
        return LoadSymbol(verb)
    return Unknown(text)

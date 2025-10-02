"""Brazilian Portuguese title normalization utilities."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List

_ABBREVIATIONS = {
    "sr": "sênior",
    "pl": "pleno",
    "jr": "júnior",
    "eng": "engenheiro",
    "dev": "desenvolvedor",
    "arq": "arquiteto",
    "coord": "coordenador",
    "anal": "analista",
}

_GENDER_SUFFIX_PATTERN = re.compile(r"\((a|o|as|os)\)", re.IGNORECASE)
_PUNCTUATION_PATTERN = re.compile(r"[\.,;:!@#?$%&*+=<>\"'`~^ºª\[\]{}()\/_|\\-]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _strip_gender_suffixes(text: str) -> str:
    return _GENDER_SUFFIX_PATTERN.sub("", text)


def _remove_punctuation(text: str) -> str:
    return _PUNCTUATION_PATTERN.sub(" ", text)


def _fold_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _expand_abbreviations(tokens: Iterable[str]) -> List[str]:
    return [_ABBREVIATIONS.get(token, token) for token in tokens]


def normalize_title(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = _strip_gender_suffixes(cleaned)
    cleaned = cleaned.lower()
    cleaned = _remove_punctuation(cleaned)
    cleaned = _WHITESPACE_PATTERN.sub(" ", cleaned).strip()
    tokens = cleaned.split(" ") if cleaned else []
    expanded = " ".join(_expand_abbreviations(token for token in tokens if token))
    folded = _fold_diacritics(expanded).lower()
    return _WHITESPACE_PATTERN.sub(" ", folded).strip()


class EcoTitleNormalizer:
    """Normalizer compatible with existing ECO processing entrypoints."""

    def normalize(self, text: str) -> str:
        return normalize_title(text)


def normalize_title_ptbr(text: str) -> str:
    return normalize_title(text)

__all__ = [
    "EcoTitleNormalizer",
    "normalize_title",
    "normalize_title_ptbr",
]

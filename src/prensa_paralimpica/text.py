"""Utilidades de texto: normalización, limpieza y control de calidad."""

from __future__ import annotations

import re
import unicodedata

# Palabras funcionales frecuentes (castellano + catalán) para estimar la calidad del texto.
STOPWORDS = frozenset(
    """de la que el en y a los se del las un por con no una su para es al lo como mas pero sus le
    ya o fue este ha si porque esta son entre cuando muy sin sobre tambien me hasta hay donde quien
    desde todo nos durante todos uno les ni contra otros ese eso ante ellos e esto antes algunos unos
    yo otro otras otra tanto esa estos mucho quienes nada muchos cual poco ella estar estas algunas
    algo nosotros i els amb per dels pel va""".split()
)

_ILLEGAL_XLSX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s: str) -> str:
    """Minúsculas y sin diacríticos: la forma sobre la que se aplica el libro de códigos."""
    return strip_accents((s or "").lower())


def quality_score(text: str, min_tokens: int = 20) -> float:
    """Proporción de palabras funcionales: ~0,35-0,50 en texto real y ~0 en texto corrupto.

    Devuelve 0 si hay menos de ``min_tokens`` palabras (no evaluable).
    """
    toks = re.findall(r"[a-záéíóúñüàèòç]+", (text or "").lower())
    if len(toks) < min_tokens:
        return 0.0
    return sum(w in STOPWORDS for w in toks) / len(toks)


def clean_text(text: str) -> str:
    """Une palabras cortadas por guion de fin de línea y colapsa espacios."""
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text or "")
    text = re.sub(r"(\w)- (\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def xlsx_safe(value):
    """Elimina caracteres de control que Excel no admite y recorta al límite de celda."""
    if isinstance(value, str):
        return _ILLEGAL_XLSX.sub("", value)[:32000]
    return value

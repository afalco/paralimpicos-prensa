"""Deduplicación y agrupación de piezas en 'historias' (misma noticia en varios medios)."""

from __future__ import annotations

import re
from collections import defaultdict

import pandas as pd

from .text import norm


def normalized_title(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", norm(s)).strip()


def drop_exact_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina repeticiones exactas (mismo titular normalizado + medio + fecha),
    p. ej. piezas presentes a la vez en los PDF 'digital' e 'impresa' del mismo día."""
    key = (df["titular"].fillna("").map(normalized_title) + "|" + df["medio"].fillna("")
           + "|" + df["fecha"].fillna(""))
    return df.loc[~key.duplicated()].reset_index(drop=True)


def _tokens(s: str) -> frozenset[str]:
    return frozenset(w for w in re.findall(r"\w+", norm(s)) if len(w) > 3)


def assign_stories(df: pd.DataFrame, threshold: float = 0.6, max_df: float = 0.02) -> pd.Series:
    """Agrupa titulares casi idénticos (Jaccard de tokens >= ``threshold``).

    Recorre las piezas por fecha; cada pieza se une a la primera historia existente
    cuyo titular representativo supera el umbral, o abre una historia nueva.
    Usa un índice invertido de tokens para escalar a un año completo; los tokens
    presentes en demasiadas historias no se usan para generar candidatos.
    """
    dates = pd.to_datetime(df["fecha"], format="%d/%m/%Y", errors="coerce")
    order = dates.sort_values(kind="stable").index
    reps: list[frozenset] = []
    inv: dict[str, list[int]] = defaultdict(list)
    story = pd.Series(-1, index=df.index, dtype=int)
    titles = df["titular"].fillna("")
    for i in order:
        t = _tokens(titles[i])
        found = -1
        if t:
            limit = max(50, int(max_df * max(len(reps), 1)))
            cands: set[int] = set()
            for w in t:
                ids = inv.get(w)
                if ids and len(ids) <= limit:
                    cands.update(ids)
            for sid in sorted(cands):
                r = reps[sid]
                if len(t & r) / len(t | r) >= threshold:
                    found = sid
                    break
        if found < 0:
            reps.append(t)
            found = len(reps) - 1
            for w in t:
                inv[w].append(found)
        story[i] = found
    return story

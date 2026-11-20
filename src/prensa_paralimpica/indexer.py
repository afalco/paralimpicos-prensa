"""Lectura del índice de cada PDF de resumen de prensa.

Cada entrada del índice es un enlace interno (LINK_GOTO) a la página donde empieza
la pieza. El texto bajo cada enlace contiene el titular (1-3 líneas) y una línea con el
medio y la fecha. Variantes observadas en 2025:

* ``Medio - dd/mm/aaaa`` · ``@ medio.com - dd/mm/aaaa`` · ``Cadena - PROGRAMA - dd/mm/aaaa``
* (desde junio) ``Medio -  By AUTOR - (ES) - dd/mm/aaaa`` · ``Cadena Ser () - (ES) - PROGRAMA 00:00 - dd/mm/aaaa``,
  seguidas de un extracto que empieza por ``<br>`` (se ignora).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DATE_RE = re.compile(r"^(.*?) - (\d{2}/\d{2}/\d{4})\s*$")
LINK_GOTO = 1  # == fitz.LINK_GOTO
_COUNTRY = re.compile(r"^\(([A-Z]{2})\)$")


@dataclass
class IndexEntry:
    titular: str
    linea_medio: str  # "?" si no se pudo leer
    fecha: str  # dd/mm/aaaa o "?"
    pagina: int  # 1-based

    def _parts(self) -> list[str]:
        return [p.strip() for p in self.linea_medio.lstrip("@ ").split(" - ")]

    @property
    def online(self) -> bool:
        return self.linea_medio.startswith("@")

    @property
    def medio(self) -> str:
        return re.sub(r"\s*\(\)\s*$", "", self._parts()[0]).strip()

    @property
    def autor(self) -> str | None:
        return next((p[3:].strip() for p in self._parts()[1:] if p.startswith("By ")), None)

    @property
    def pais(self) -> str | None:
        return next((_COUNTRY.match(p).group(1) for p in self._parts()[1:] if _COUNTRY.match(p)), None)

    @property
    def programa(self) -> str | None:
        rest = [p for p in self._parts()[1:] if p and not p.startswith("By ") and not _COUNTRY.match(p)]
        return " - ".join(rest) or None


def _lines(text: str) -> list[str]:
    return [
        x.strip() for x in text.split("\n")
        if x.strip() and not x.strip().isdigit() and x.strip() != "Índice"
    ]


def entry_from_lines(lines: list[str], page: int) -> IndexEntry:
    """Convierte las líneas bajo un enlace en una entrada (titular + medio + fecha).

    El titular son las líneas anteriores a la línea 'medio - fecha'; lo posterior (extracto
    '<br>…' del formato de junio en adelante) se descarta.
    """
    medline = next((x for x in lines if DATE_RE.match(x) and not x.startswith("<br>")), None)
    if medline is None:
        return IndexEntry(" ".join(x for x in lines if not x.startswith("<br>")), "?", "?", page)
    m = DATE_RE.match(medline)
    return IndexEntry(" ".join(lines[: lines.index(medline)]), m.group(1).strip(), m.group(2), page)


def parse_index(doc) -> tuple[list[IndexEntry], list[int]]:
    """Devuelve (entradas, páginas_del_índice_0based) de un documento PyMuPDF."""
    import pymupdf as fitz

    raw_entries: list[list] = []
    idx_pages: list[int] = []
    pending = None
    for i in range(1, doc.page_count):
        page = doc[i]
        links = sorted(
            (lk for lk in page.get_links() if lk.get("kind") == LINK_GOTO),
            key=lambda lk: lk["from"].y0,
        )
        if not links:
            if idx_pages:
                break
            continue
        idx_pages.append(i)
        width, bottom = page.rect.x1, page.rect.y1
        # Entrada partida entre páginas: su línea de medio queda arriba de esta página.
        if pending is not None:
            head = page.get_textbox(fitz.Rect(0, 0, width, links[0]["from"].y0 - 1))
            pending[0] += _lines(head)
            raw_entries.append(pending)
            pending = None
        for j, lk in enumerate(links):
            y0 = lk["from"].y0 - 1
            y1 = links[j + 1]["from"].y0 - 1 if j + 1 < len(links) else bottom
            lines = _lines(page.get_textbox(fitz.Rect(0, y0, width, y1)))
            item = [lines, lk["page"] + 1]
            if j + 1 == len(links) and not any(DATE_RE.match(x) for x in lines):
                pending = item
            else:
                raw_entries.append(item)
    if pending is not None:
        raw_entries.append(pending)
    return [entry_from_lines(lines, pg) for lines, pg in raw_entries], idx_pages

"""Extracción: PDF de resumen de prensa -> una fila por pieza (con caché por PDF).

Estructura esperada de la carpeta de entrada::

    <root>/                 p. ej. /Volumes/My Passport/2025
      01 Enero/20250107 digital.pdf
      01 Enero/20250108.pdf
      ...
      12 diciembre/...

Cada PDF se procesa una sola vez y se guarda en ``<cache>/<carpeta>/<nombre>.json``.
Si el PDF cambia (tamaño o fecha de modificación), la versión del extractor o el motor
de OCR, se vuelve a procesar. Al reprocesar por un cambio de versión del extractor se
**reutiliza el OCR** ya hecho (mismo motor y mismas páginas), que es la parte lenta.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date
from pathlib import Path

from . import __version__
from .indexer import parse_index
from .metadata import (
    broadcast_body,
    is_broadcast,
    is_online,
    online_body,
    parse_broadcast_meta,
    parse_online_meta,
    parse_print_meta,
    strip_print_header,
    to_number,
)
from .ocr import get_ocr
from .text import clean_text, quality_score

log = logging.getLogger(__name__)
EXTRACTOR_VERSION = f"{__version__}-1"
LINK_URI = 2  # == fitz.LINK_URI
MESES = {m: i for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), 1)}


# ---------------------------------------------------------------------------
# Selección de ficheros

def month_folders(root: Path, months: list[str] | None = None) -> list[Path]:
    """Subcarpetas de mes ('01 Enero', ...). ``months`` = ['01','02'] o None (todas)."""
    folders = sorted(p for p in root.iterdir() if p.is_dir() and re.match(r"^\d{2}\b", p.name))
    if months:
        wanted = {m.zfill(2) for m in months}
        folders = [p for p in folders if p.name[:2] in wanted]
    return folders


def list_pdfs(root: Path, months: list[str] | None = None) -> list[Path]:
    return [
        pdf for folder in month_folders(root, months)
        for pdf in sorted(folder.glob("*.pdf")) if not pdf.name.startswith("._")
    ]


def summary_day(stem: str) -> str | None:
    """'20250107 digital' -> '20250107'. None si el nombre no sigue el patrón AAAAMMDD."""
    m = re.match(r"^(\d{8})(?!\d)", stem)
    return m.group(1) if m else None


def cover_date(text: str) -> str | None:
    """Fecha del resumen leída de la portada (AAAAMMDD).

    Formatos: 'miércoles, 5 de marzo de 2025' · 'RESUMEN DE PRENSA 10/06/2025' · '19/05/2025'.
    """
    m = re.search(r"(\d{1,2}) de ([a-záéíóú]+) de (\d{4})", text.lower())
    if m and m.group(2) in MESES:
        try:
            return date(int(m.group(3)), MESES[m.group(2)], int(m.group(1))).strftime("%Y%m%d")
        except ValueError:
            return None
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y%m%d")
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Extracción de un PDF

def extract_pdf(path: Path, ocr=None, reuse_ocr: dict | None = None) -> list[dict]:
    """Devuelve una lista de piezas (dict) a partir de un PDF de resumen de prensa.

    ``reuse_ocr``: {(pag_ini, pag_fin): texto} de una extracción anterior con el mismo motor de OCR.
    """
    import fitz

    ocr = ocr or get_ocr("none")
    reuse_ocr = reuse_ocr or {}
    doc = fitz.open(path)
    entries, _ = parse_index(doc)
    dia_portada = cover_date(doc[0].get_text()) if doc.page_count else None
    dia_nombre = summary_day(path.stem)
    rows: list[dict] = []
    for k, e in enumerate(entries):
        start = e.pagina - 1
        end = entries[k + 1].pagina - 2 if k + 1 < len(entries) else doc.page_count - 1
        end = max(start, min(end, doc.page_count - 1))
        pages = range(start, end + 1)
        raw = "".join(doc[p].get_text() for p in pages)
        urls = [lk.get("uri") for p in pages for lk in doc[p].get_links() if lk.get("kind") == LINK_URI]
        known = e.linea_medio != "?"
        row = {
            "archivo": path.name,
            "carpeta": path.parent.name,
            "dia_resumen": dia_portada or dia_nombre,
            "dia_resumen_fuente": "portada" if dia_portada else ("nombre" if dia_nombre else None),
            "n_indice": k + 1,
            "titular": e.titular,
            "medio": e.medio if known else None,
            "programa": e.programa if known else None,
            "autor": e.autor if known else None,
            "pais_medio": e.pais if known else None,
            "fecha": e.fecha if known else None,
            "pag_ini": start + 1,
            "pag_fin": end + 1,
            "url": urls[0] if urls else None,
        }
        if is_broadcast(raw):
            meta = parse_broadcast_meta(raw)
            meta["programa"] = meta["programa"] or row["programa"]
            row.update(soporte="TV/Radio", **meta)
            body, method = broadcast_body(raw, e.titular, row["medio"]), "transcripcion"
        elif is_online(raw, e.linea_medio):
            meta = parse_online_meta(raw)
            meta["autor"] = row["autor"] or meta.get("autor")  # el del índice es más limpio
            row.update(soporte="Online", **meta)
            body, method = online_body(raw), "extracto_online"
        else:
            row.update(soporte="Impresa", **parse_print_meta(raw))
            key = (start + 1, end + 1)
            if key in reuse_ocr:
                body, method = reuse_ocr[key], "ocr"
            else:
                body = strip_print_header(" ".join(ocr(doc[p]) for p in pages))
                method = "ocr"
        body = clean_text(body)
        row["ots_num"] = to_number(row.get("ots"))
        row["ave_eur_num"] = to_number(row.get("ave_eur"))
        row.update(texto=body, n_chars=len(body), metodo_texto=method,
                   calidad_texto=round(quality_score(body), 3))
        rows.append(row)
    doc.close()
    return rows


# ---------------------------------------------------------------------------
# Corpus con caché

def _signature(pdf: Path, ocr_backend: str) -> dict:
    st = pdf.stat()
    return {"size": st.st_size, "mtime": int(st.st_mtime), "extractor": EXTRACTOR_VERSION, "ocr": ocr_backend}


def _reusable_ocr(data: dict, sig: dict) -> dict:
    """OCR de una caché antigua del MISMO PDF y MISMO motor: {(pag_ini, pag_fin): texto}."""
    old = data.get("signature", {})
    if any(old.get(k) != sig[k] for k in ("size", "mtime", "ocr")):
        return {}
    return {(r["pag_ini"], r["pag_fin"]): r["texto"] for r in data.get("rows", [])
            if r.get("metodo_texto") == "ocr" and r.get("texto")}


def extract_corpus(
    root: Path,
    cache_dir: Path,
    months: list[str] | None = None,
    ocr_backend: str = "livetext",
    dpi: int = 200,
    force: bool = False,
) -> list[dict]:
    """Extrae todos los PDF seleccionados (usando caché) y devuelve todas las filas."""
    pdfs = list_pdfs(root, months)
    if not pdfs:
        raise FileNotFoundError(f"No hay PDF en {root} para los meses {months or 'todos'}")
    ocr = None
    all_rows: list[dict] = []
    t0 = time.time()
    for i, pdf in enumerate(pdfs, 1):
        cache = cache_dir / pdf.parent.name / (pdf.stem + ".json")
        sig = _signature(pdf, ocr_backend)
        reuse: dict = {}
        if cache.exists():
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("signature") == sig and not force:
                all_rows += data["rows"]
                log.info("[%d/%d] %s (caché, %d piezas)", i, len(pdfs), pdf.name, len(data["rows"]))
                continue
            if not force:
                reuse = _reusable_ocr(data, sig)
        if ocr is None:
            ocr = get_ocr(ocr_backend, dpi)
        rows = extract_pdf(pdf, ocr, reuse)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"signature": sig, "rows": rows}, ensure_ascii=False), encoding="utf-8")
        all_rows += rows
        log.info("[%d/%d] %s -> %d piezas (OCR reutilizado: %d) (%.0f s acumulados)",
                 i, len(pdfs), pdf.name, len(rows), len(reuse), time.time() - t0)
    return all_rows

"""Extracción de metadatos de las fichas de cada pieza (impresa, online, TV/radio).

Funciones puras sobre el texto de la página: no dependen de PyMuPDF (fáciles de testear).
"""

from __future__ import annotations

import re

FRECUENCIAS = {
    "Diario", "Semanal", "Mensual", "Quincenal", "Bimestral", "Trimestral",
    "Anual", "Bimensual", "Semestral",
}
_FECHA_LARGA = re.compile(r"\d{1,2} \w+, \d{4}")


def kv(text: str, key: str) -> str | None:
    m = re.search(re.escape(key) + r":\s*([^\n]+)", text)
    return m.group(1).strip() if m else None


def to_number(value) -> float | None:
    """'6710 €' -> 6710 ; '1.470.457' -> 1470457 ; None/'' -> None."""
    if value is None:
        return None
    digits = re.sub(r"[^\d]", "", str(value))
    return float(digits) if digits else None


def is_broadcast(raw: str) -> bool:
    return "DURACIÓN:" in raw or "HORA EMISIÓN:" in raw


def is_online(raw: str, medio_line: str) -> bool:
    return medio_line.startswith("@") or "TMU:" in raw


def parse_print_meta(raw: str) -> dict:
    """Ficha de prensa impresa: etiquetas SECCIÓN/OTS/DIFUSIÓN/... seguidas de sus valores.

    Los valores salen en orden, pero OTS o DIFUSIÓN pueden faltar, así que se
    identifican por su forma (€, CM², frecuencia, fecha) y los numéricos por posición.
    """
    i = raw.find("SECCIÓN:")
    if i < 0:
        return {}
    lines = [ln.strip() for ln in raw[i:].split("\n") if ln.strip()]
    vals = [v for v in lines if not v.endswith(":")]
    out: dict = {"seccion": vals[0] if vals else None}
    out["fecha_pub_larga"] = next((v for v in vals if _FECHA_LARGA.search(v)), None)
    out["frecuencia"] = next((v for v in vals if v in FRECUENCIAS), None)
    out["area"] = next((v for v in vals if "CM²" in v), None)
    out["ave_eur"] = next((v for v in vals if v.endswith("€")), None)
    out["pais"] = "España" if "España" in vals else None
    nums = [v for v in vals[1:] if re.fullmatch(r"\d+", v)]
    if len(nums) >= 3:
        out["ots"], out["difusion"], out["paginas_medio"] = nums[:3]
    elif len(nums) == 2:
        out["difusion"], out["paginas_medio"] = nums
    return out


def parse_online_meta(raw: str) -> dict:
    flat = raw.replace("\n", "")
    out: dict = {}
    m = re.search(r"([\d.,]+)\s*minTMU:\s*(\d+)OTS:\s*(\d+)AMD:", flat)
    if m:
        out.update(tmu_min=m.group(1), ots=m.group(2), amd=m.group(3))
    ave = re.findall(r"(\d[\d.]*)\s*€", raw)
    out["ave_eur"] = ave[0] if ave else None
    au = re.search(r"\n([^\n]*)AUTOR:", raw)
    out["autor"] = au.group(1).strip() if au else None
    return out


def parse_broadcast_meta(raw: str) -> dict:
    return {
        "programa": kv(raw, "PROGRAMA"),
        "ots": kv(raw, "OTS"),
        "ave_eur": kv(raw, "AVE"),
        "duracion_s": kv(raw, "DURACIÓN"),
        "hora": kv(raw, "HORA EMISIÓN"),
    }


def strip_print_header(ocr_text: str) -> str:
    """Quita la cabecera de la ficha (PAÍS ... SECCIÓN: X) que el OCR lee antes del artículo."""
    if "SECCI" in ocr_text[:800]:
        return re.sub(r"^.*?SECCI[OÓ]N:\s*\S+", "", ocr_text, count=1, flags=re.S)
    return ocr_text

"""Extracción de metadatos de las fichas de cada pieza (impresa, online, TV/radio).

El proveedor del clipping cambió de formato durante 2025; se admiten todas las variantes observadas:

* **Formato A** (enero - 3 marzo 2025). Online: ``@ MEDIO 0,28 minTMU: …OTS: …AMD: … AVE: … AUTOR:``.
  TV/radio: ``PROGRAMA: … OTS: … HORA EMISIÓN: … AVE: … DURACIÓN: …``.
* **Formato B** (desde 4 marzo 2025). Online: ``PAÍS: ESP / TIPO: web / AVE: €54.00 / AUDIENCIA: /
  AMD: / TMU: / AUTOR: / URL:`` (sin ``@`` en el índice).
* **Formato C** (desde junio 2025, Onclusive). TV/radio: ``País : Spain / PROGRAMA : … / DURACIÓN : 27``
  (espacio antes de los dos puntos). Online como en B.
* Prensa impresa: misma ficha ``SECCIÓN/OTS/DIFUSIÓN/FRECUENCIA/ÁREA/AVE/PÁGINAS/PAÍS`` en todo el año.

Funciones puras sobre el texto de la página: no dependen de PyMuPDF (fáciles de testear).
"""

from __future__ import annotations

import re

FRECUENCIAS = {
    "Diario", "Semanal", "Mensual", "Quincenal", "Bimestral", "Trimestral",
    "Anual", "Bimensual", "Semestral",
}
_FECHA_LARGA = re.compile(r"\d{1,2} \w+, \d{4}")
_BROADCAST = re.compile(r"DURACI[OÓ]N\s*:|HORA EMISI[OÓ]N\s*:")
_ONLINE_B = re.compile(r"TIPO\s*:\s*web\b", re.IGNORECASE)


def kv(text: str, key: str) -> str | None:
    """Valor de 'CLAVE: valor' o 'CLAVE : valor' en la misma línea (None si falta o está vacío)."""
    m = re.search(r"(?m)^\s*" + re.escape(key) + r"[ \t]*:[ \t]*([^\n]*)$", text)
    if not m:
        m = re.search(re.escape(key) + r"[ \t]*:[ \t]*([^\n]+)", text)
    if not m:
        return None
    val = m.group(1).strip()
    return val or None


def to_number(value) -> float | None:
    """Convierte importes y audiencias a número.

    '6710 €' -> 6710 · '€54.00' -> 54.0 · '€2366.87' -> 2366.87 · '1.470.457' -> 1470457 ·
    '0,28' -> 0.28 · '1.234,5' -> 1234.5 · None/'' -> None
    """
    if value is None:
        return None
    s = re.sub(r"[^\d.,]", "", str(value))
    if not s or not re.search(r"\d", s):
        return None
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        s = s.replace(thou, "").replace(dec, ".")
    elif "." in s:
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
            s = s.replace(".", "")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def is_broadcast(raw: str) -> bool:
    return bool(_BROADCAST.search(raw))


def is_online(raw: str, medio_line: str) -> bool:
    return medio_line.startswith("@") or "TMU:" in raw or bool(_ONLINE_B.search(raw))


def online_format(raw: str) -> str:
    return "B" if _ONLINE_B.search(raw) else "A"


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
    out: dict = {"formato_ficha": online_format(raw)}
    if out["formato_ficha"] == "B":
        out["ave_eur"] = kv(raw, "AVE")
        out["audiencia"] = kv(raw, "AUDIENCIA")
        out["amd"] = kv(raw, "AMD")
        tmu = kv(raw, "TMU")
        out["tmu_min"] = tmu.replace("min", "").strip() if tmu else None
        out["autor"] = kv(raw, "AUTOR")
        out["url_ficha"] = kv(raw, "URL")
        out["ots"] = out["audiencia"]  # comparable con OTS del formato A
        return out
    flat = raw.replace("\n", "")
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


def _strip_trailing(lines: list[str], *labels: str | None) -> list[str]:
    """Quita del final las líneas que forman parte del titular o del nombre del medio."""
    ref = " ".join(x for x in labels if x).lower()
    while lines and lines[-1].strip() and lines[-1].strip().lower().rstrip("()").strip() in ref:
        lines.pop()
    return lines


def broadcast_body(raw: str, titular: str | None = None, medio: str | None = None) -> str:
    """Transcripción: lo anterior al bloque final (PROGRAMA / País), sin el título ni el medio."""
    m = re.search(r"(?m)^\s*(?:PROGRAMA|Pa[ií]s|PA[IÍ]S)\s*:", raw)
    body = raw[: m.start()] if m else raw
    return "\n".join(_strip_trailing(body.rstrip().split("\n"), titular, medio))


def online_body(raw: str) -> str:
    """Extracto online: hasta 'Pulse aquí' (A) o hasta la ficha 'PAÍS:' (B), sin la línea del medio."""
    cut = len(raw)
    for marker in (r"Pulse aquí", r"(?m)^PA[IÍ]S\s*:"):
        m = re.search(marker, raw)
        if m:
            cut = min(cut, m.start())
    lines = raw[:cut].rstrip().split("\n")
    if len(lines) > 1 and " " not in lines[-1].strip():  # línea con el dominio del medio
        lines.pop()
    return "\n".join(lines)


def strip_print_header(ocr_text: str) -> str:
    """Quita la cabecera de la ficha (PAÍS ... SECCIÓN: X) que el OCR lee antes del artículo."""
    if "SECCI" in ocr_text[:800]:
        return re.sub(r"^.*?SECCI[OÓ]N:\s*\S+", "", ocr_text, count=1, flags=re.DOTALL)
    return ocr_text

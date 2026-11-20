"""Motores de OCR para las páginas de prensa impresa.

La capa de texto de las páginas impresas no es utilizable (son imágenes o usan
fuentes con codificación propia), así que se rasteriza la página y se reconoce el texto.

Motores:
- ``livetext``  : Apple Vision / Live Text vía ``ocrmac`` (macOS 13+). Recomendado.
- ``tesseract`` : ``pytesseract`` + binario ``tesseract`` con datos ``spa``/``cat``.
- ``none``      : sin OCR (solo metadatos), útil para pruebas rápidas.
"""

from __future__ import annotations

import io
from collections.abc import Callable

OCRFunc = Callable[[object], str]
BACKENDS = ("livetext", "tesseract", "none")


def _render(page, dpi: int):
    from PIL import Image

    pix = page.get_pixmap(dpi=dpi)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def get_ocr(backend: str = "livetext", dpi: int = 200) -> OCRFunc:
    backend = backend.lower()
    if backend == "none":
        return lambda page: ""

    if backend == "livetext":
        try:
            from ocrmac import ocrmac
        except ImportError as exc:  # pragma: no cover - depende del sistema
            raise RuntimeError("El motor 'livetext' requiere macOS y `pip install ocrmac`.") from exc

        def _livetext(page) -> str:
            res = ocrmac.OCR(_render(page, dpi), framework="livetext").recognize()
            return " ".join(t for t, _conf, _box in res)

        return _livetext

    if backend == "tesseract":
        try:
            import pytesseract
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "El motor 'tesseract' requiere `pip install pytesseract` y el binario tesseract (spa, cat)."
            ) from exc

        def _tess(page) -> str:
            return pytesseract.image_to_string(_render(page, dpi), lang="spa+cat")

        return _tess

    raise ValueError(f"Motor OCR desconocido: {backend!r} (opciones: {', '.join(BACKENDS)})")

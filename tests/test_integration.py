"""Prueba de integración sobre un PDF real (no se ejecuta en CI).

    PRENSA_TEST_PDF="/Volumes/My Passport/2025/01 Enero/20250108.pdf" pytest -m integration
"""

import os
from pathlib import Path

import pytest

PDF = os.environ.get("PRENSA_TEST_PDF")


@pytest.mark.integration
@pytest.mark.skipif(not PDF or not Path(PDF).exists(), reason="definir PRENSA_TEST_PDF con un PDF real")
def test_extract_real_pdf():
    from prensa_paralimpica.extract import extract_pdf

    rows = extract_pdf(Path(PDF))  # sin OCR: rápido
    assert len(rows) > 0
    assert all(r["titular"] for r in rows)
    assert {r["soporte"] for r in rows} <= {"Online", "Impresa", "TV/Radio"}
    assert sum(r["medio"] is None for r in rows) <= 1

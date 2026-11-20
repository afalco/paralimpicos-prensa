# Uso: make install ; make enero ROOT="/Volumes/My Passport/2025" ; make anio ROOT=...
ROOT ?= /Volumes/My Passport/2025
PY   ?= python3

.PHONY: install test lint enero mes anio recodificar clean

install:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check src tests

# Piloto: enero
enero:
	prensa-para run --root "$(ROOT)" --months 01 --label "Enero 2025"

# Un mes cualquiera: make mes M=03
mes:
	prensa-para run --root "$(ROOT)" --months $(M)

# Año completo (usa la caché: solo hace OCR de lo que no esté procesado)
anio:
	prensa-para run --root "$(ROOT)" --tag 2025 --label "Año 2025"

# Tras editar config/codebook.toml: make recodificar TAG=meses_01
recodificar:
	prensa-para codify --tag $(TAG) && prensa-para report --tag $(TAG)

clean:
	rm -rf outputs data/processed

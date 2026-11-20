# Changelog

## 0.1.0 — 2026-11-20
- Primera versión del pipeline: índice por enlaces, metadatos por soporte, OCR (Live Text / Tesseract),
  caché por PDF, deduplicación e historias, libro de códigos TOML v0.1.0, informe (Excel, CSV, JSON, MD, figura),
  CLI `prensa-para`, tests y CI.
- Verificado con enero de 2025: 2.084 entradas → 2.060 piezas tras eliminar duplicados exactos, 889 historias.
  Mismos valores que el piloto manual en piezas, historias, titulares con término paralímpico (53,3 %),
  lenguaje desaconsejado (16 ocurrencias) y menciones por género (376 piezas de mujeres / 324 de hombres).
- **Corrección respecto al piloto manual:** en el piloto, la expresión del encuadre de superación se reconstruyó
  mal y no reconocía el término «superación». Las cifras de ese encuadre en el informe piloto estaban
  **infraestimadas**. Valores corregidos (piezas de 150 palabras o más): 30/85 (35,3 %) en piezas que mencionan
  deportistas mujeres frente a 25/86 (29,1 %) en las que mencionan hombres; Fisher bilateral p = 0,416
  (el piloto daba 22/85 frente a 14/86, p = 0,137).

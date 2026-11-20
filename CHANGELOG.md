# Changelog

## 0.2.1
- `import pymupdf` en lugar del alias obsoleto `fitz` (compatible con PyMuPDF >= 1.24.3 y 2.x). Verificado con PyMuPDF 2.1: 20 tests OK, incluido el de integración con un PDF de marzo de 2025.

## 0.2.0 — 2026-11-20
Ejecución del año completo de 2025: se detectaron cambios de formato del proveedor del clipping que la v0.1.0 no reconocía.
- **Formato B (desde el 4/3/2025):** la ficha online pasa a `TIPO: web / AVE: €… / AUDIENCIA / AMD / TMU / AUTOR / URL`, sin `@` en el índice.
  En la v0.1.0 unas 4.400 piezas online se trataban como impresas: soporte erróneo (online ≈ 40 % en lugar de ≈ 80 %), OCR innecesario y pérdida de AVE y audiencia.
- **Formato C (Onclusive, desde junio de 2025):** TV/radio con `PROGRAMA :` / `DURACIÓN :` (espacio antes de los dos puntos), que antes no se detectaba (0 piezas de TV/radio entre junio y diciembre).
  El índice pasa a `Medio - By AUTOR - (ES) - …` con extracto `<br>`. Ahora se separan `medio`, `autor`, `pais_medio` y `programa`.
- `to_number` admite `€54.00`, `€2366.87`, `1.470.457` y `0,28`. Nuevas columnas `ots_num` y `ave_eur_num`.
- La fecha del resumen se lee de la portada (corrige los ficheros mal nombrados `20280318.pdf`, `20260618.pdf`, `20260620 digital.pdf`, `224impresa.pdf`, `202506274.pdf` y `202507030.pdf`).
- Caracteres de control (`\x00`) eliminados en la extracción y antes de exportar a Excel. Con pandas 3 las columnas de texto ya no son `object` y la limpieza no se aplicaba, lo que hacía fallar la exportación.
- Al reprocesar por un cambio de versión del extractor **se reutiliza el OCR previo**: el año completo se reprocesa en unos 13 min en lugar de unos 106.
- El informe añade el contraste del encuadre de superación **por historia** (unidad independiente), además de por pieza.
- Nuevos tests: `tests/test_formatos_2025.py`, con 7 casos sobre fragmentos reales de cada formato.
- Resultados del año 2025: 22.307 piezas, 11.457 historias y 3.207 medios; online 78 %, impresa 19 % y TV/radio 3 % (estable mes a mes); AVE disponible en el 95–100 % de las piezas cada mes.


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

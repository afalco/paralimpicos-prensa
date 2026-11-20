# prensa-paralimpica

Pipeline reproducible para convertir los **resúmenes diarios de prensa (clipping) en PDF** sobre deporte
paralímpico en una **base de datos codificada** (una fila por pieza informativa) y en indicadores para
investigación académica: visibilidad, temas, modalidades, género, lenguaje sobre discapacidad, encuadre
de "superación" y organizaciones.

> **Estado:** v0.2.0. El libro de códigos se ha construido con el piloto de enero de 2025 y **no está
> validado** todavía con codificación manual. Los resultados son descriptivos y provisionales.

---

## 1. Qué hace

```
PDF diarios ─► índice (enlaces internos) ─► ficha de cada pieza ─► texto ─► dedup ─► codificación ─► informe
               titular, medio, fecha        metadatos (OTS, AVE…)  OCR /    historias  libro de códigos  Excel, CSV,
                                                                   extracto            (TOML)            figura, JSON, MD
```

| Etapa | Módulo | Detalle |
|---|---|---|
| Índice | `indexer.py` | Cada entrada del índice es un enlace a la página de la pieza. Se leen titular, medio, programa y fecha (también entradas partidas entre páginas). |
| Metadatos | `metadata.py` | Impresa: sección, OTS, difusión, frecuencia, área, AVE. Online: TMU, OTS, AMD, AVE, URL, autor. TV/Radio: programa, hora, duración, OTS, AVE. |
| Texto | `extract.py`, `ocr.py` | **Impresa:** OCR (la capa de texto de los PDF es inutilizable: imágenes o fuentes con codificación propia). **Online:** solo el extracto que incluye el clipping. **TV/Radio:** transcripción incluida. Se calcula un índice de calidad del texto. |
| Caché | `extract.py` | Un JSON por PDF en `data/interim/`. Solo se reprocesa si cambia el PDF, la versión del extractor o el motor de OCR. |
| Deduplicación | `dedup.py` | Elimina duplicados exactos (p. ej. ficheros `digital`/`impresa` del mismo día) y agrupa titulares casi idénticos en **historias** (Jaccard ≥ 0,6). |
| Codificación | `codebook.py` + `config/codebook.toml` | Diccionarios/regex sobre texto en minúsculas y sin tildes. |
| Informe | `report.py` | `resumen.json`, `resumen.md`, `panel.png`, `dataset.xlsx` (incluye el libro de códigos), CSV. |

### Formatos del clipping admitidos
El proveedor cambió el formato de los PDF durante 2025. El pipeline reconoce los tres formatos observados (ver `metadata.py`).
Cada pieza guarda `formato_ficha` (A o B en online) y la fecha del resumen se lee de la **portada** de cada PDF
(`dia_resumen_fuente = portada`), no del nombre del fichero.

| Formato | Periodo | Online | TV/Radio | Índice |
|---|---|---|---|---|
| A | hasta el 3 mar 2025 | `@ medio`, `TMU/OTS/AMD`, `AVE: 6710 €` | `PROGRAMA: … DURACIÓN: …` | `Medio - fecha` |
| B | desde el 4 mar 2025 | `TIPO: web`, `AVE: €54.00`, `AUDIENCIA`, `AMD`, `TMU`, `AUTOR`, `URL` | como en A | sin `@` |
| C (Onclusive) | desde jun 2025 | como en B | `PROGRAMA : … DURACIÓN : …` (espacio antes de los dos puntos) | `Medio - By AUTOR - (ES) - [PROGRAMA] - fecha`, seguido de un extracto `<br>…` |

La prensa impresa mantiene la misma ficha todo el año. **Si aparece un formato nuevo**, la tabla de calidad por mes
(soporte, % sin AVE, calidad del texto) lo delata enseguida: hay que añadir un caso en `metadata.py` y un test en
`tests/test_formatos_2025.py`.

## 2. Instalación

Requisitos: Python ≥ 3.11. Para el OCR recomendado, **macOS 13+** (Apple Vision / Live Text vía `ocrmac`).

```bash
git clone <URL-del-repo> prensa-paralimpica
cd prensa-paralimpica
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q            # tests unitarios (no necesitan los PDF)
```

En Linux/Windows se puede usar Tesseract: `pip install -e ".[tesseract]"`, instalar el binario `tesseract`
con los idiomas `spa` y `cat`, y ejecutar con `--ocr tesseract`. Los resultados del OCR no serán idénticos
a los de Live Text: **no mezclar motores dentro de un mismo estudio**.

## 3. Uso

Estructura esperada de los datos (no se incluyen en el repositorio):

```
/Volumes/My Passport/2025/
  01 Enero/20250107 digital.pdf
  01 Enero/20250108.pdf
  ...
  12 diciembre/...
```

```bash
# Un mes (piloto)  -> outputs/meses_01/
prensa-para run --root "/Volumes/My Passport/2025" --months 01 --label "Enero 2025"

# Varios meses o el año completo (reutiliza la caché: solo hace OCR de lo nuevo)
prensa-para run --root "/Volumes/My Passport/2025" --months 01 02 03
prensa-para run --root "/Volumes/My Passport/2025" --tag 2025 --label "Año 2025"

# Tras editar el libro de códigos: re-codificar sin repetir el OCR (segundos)
prensa-para codify --months 01 && prensa-para report --months 01 --label "Enero 2025"
```

Atajos: `make enero`, `make mes M=03`, `make anio`, `make recodificar TAG=meses_01`, `make test`, `make lint`.
Sin instalar el paquete: `PYTHONPATH=src python -m prensa_paralimpica run ...`

Opciones útiles: `--ocr {livetext,tesseract,none}` (`none` = solo metadatos, muy rápido), `--dpi 200`,
`--force` (ignorar la caché), `--data-dir`, `--out-dir`, `--codebook ruta.toml`, `-v`.

**Tiempos medidos** (OCR Live Text, Mac Apple Silicon):
- Enero de 2025 (20 PDF, 2.084 entradas): unos 5 min 20 s.
- Año 2025 completo (245 PDF, 23.230 entradas, 22.307 piezas tras eliminar duplicados): **unos 106 min la primera vez**.
- Reprocesar el año tras actualizar el extractor: unos 13 min, porque se **reutiliza el OCR** ya hecho (mismo PDF, mismo motor, mismas páginas).
- Recodificar e informe: unos 20 s.

Consejo: `caffeinate -i prensa-para run ...` evita que el Mac se suspenda en ejecuciones largas.

### Salidas (`outputs/<tag>/`)

| Fichero | Contenido |
|---|---|
| `dataset.xlsx` | Hojas `piezas` (una fila por pieza, con texto y todas las variables), `resumen`, `personas`, `historias`, `medios`, `calidad_texto`, `libro_de_codigos` |
| `piezas_con_texto.csv.gz` / `piezas_sin_texto.csv` | La misma tabla de piezas para R, Stata o Python |
| `panel.png` | Figura resumen de 6 paneles |
| `resumen.json` / `resumen.md` | Indicadores agregados, con la versión del pipeline y del libro de códigos |

## 4. Libro de códigos

Está en `config/codebook.toml`. Contiene:

- relevancia paralímpica;
- lenguaje recomendado y desaconsejado sobre discapacidad;
- encuadre de superación frente a encuadre deportivo;
- temas, modalidades, tipo de discapacidad y organizaciones;
- reglas de tipo de medio;
- lista curada de personas con género y rol.

Reglas:
- Los patrones se aplican sobre el texto **en minúsculas y sin tildes**.
- **Cada cambio debe subir `meta.version`.** Esa versión se guarda en todas las salidas.
- Los tests (`tests/test_codebook_dedup.py`) comprueban que todas las expresiones compilan y que detectan casos conocidos.

## 5. Variables principales (hoja `piezas`)

| Variable | Descripción |
|---|---|
| `archivo`, `carpeta`, `dia_resumen`, `n_indice` | Procedencia: PDF, mes, día del resumen y orden en el índice |
| `titular`, `medio`, `programa`, `fecha`, `url` | Datos de la pieza (`fecha` = publicación) |
| `soporte` | Online / Impresa / TV/Radio |
| `tipo_medio` | Agencia / Agregador / Deportivo / Generalista/local |
| `seccion`, `ots`, `difusion`, `ave_eur`, `area`, `tmu_min`, `duracion_s`, `hora` | Metadatos de audiencia y valor publicitario estimado del proveedor del clipping |
| `autor`, `pais_medio`, `formato_ficha`, `audiencia`, `amd`, `url_ficha` | Campos del formato B/C (autor e indicativo de país del índice; audiencia y AMD de la ficha online) |
| `ots_num`, `ave_eur_num` | OTS/audiencia y AVE convertidos a número (admite `6710 €`, `€54.00`, `1.470.457`) |
| `dia_resumen_fuente` | De dónde sale `dia_resumen`: `portada` (preferente) o `nombre` del fichero |
| `texto`, `metodo_texto`, `calidad_texto`, `n_palabras` | Texto (OCR, extracto o transcripción) y su calidad (palabras funcionales; < 0,2 = dudoso) |
| `historia_id` | Grupo de piezas que reproducen la misma noticia |
| `menc_para`, `para_en_titular` | Relevancia paralímpica/discapacidad |
| `L_bien_*`, `L_mal_*`, `leng_recomendado`, `leng_desaconsejado` | Lenguaje (ocurrencias) |
| `enc_superacion`, `enc_deportivo`, `hay_superacion`, `*_x1000` | Encuadres (ocurrencias y por cada 1.000 palabras) |
| `tema_*`, `dep_*`, `disc_*`, `org_*` | Presencia (True/False) |
| `P_*`, `menc_deportista_mujer/hombre`, `gram_fem/masc` | Personas y género |

## 6. Limitaciones metodológicas

1. **Corpus seleccionado:** es un clipping de un proveedor, no un censo de medios.
2. **Online:** solo hay extracto (mediana de unas 70 palabras). El lenguaje y el encuadre se miden sobre todo en prensa impresa y TV/Radio.
3. **Diccionarios no validados:** antes de publicar hay que hacer doble codificación manual de una muestra estratificada y calcular κ de Cohen o α de Krippendorff.
4. **Lista de personas sesgada:** se construyó a partir de las menciones de enero. Hay que ampliarla (por ejemplo con NER) y revisarla.
5. **AVE:** es una métrica discutida y está inflada en online. Solo se usa con fines descriptivos.
6. **No independencia por sindicación:** una misma historia aparece en decenas de medios. Los contrastes deben hacerse por **historia** (`historia_id`), como hace `resumen.json` (`historias_fisher_p`), o con modelos que tengan la historia como efecto aleatorio.
7. **Errores de OCR:** columnas mezcladas o cortes de palabra. Afectan poco a los recuentos léxicos. Live Text no es estrictamente determinista: puede haber diferencias mínimas entre ejecuciones.
8. **Derechos:** los PDF y los textos derivados no deben publicarse en el repositorio (`.gitignore` ya lo impide).

## 7. Desarrollo

```bash
make test                       # tests unitarios
PRENSA_TEST_PDF="/Volumes/My Passport/2025/01 Enero/20250108.pdf" pytest -m integration
make lint
```

La integración continua (`.github/workflows/tests.yml`) ejecuta lint y tests en Ubuntu con Python 3.11 y 3.12. No usa datos reales.

## 8. Hoja de ruta

- [ ] Muestra estratificada y protocolo de doble codificación manual, con cálculo de fiabilidad.
- [ ] Registro de medios (ámbito y comunidad autónoma) para el análisis territorial.
- [ ] NER de personas y federaciones.
- [ ] Modelos: series temporales; regresión logística del encuadre de superación según género, soporte, tipo de medio y modalidad (con la historia como efecto aleatorio); modelado de temas sobre prensa impresa.
- [ ] Recuperar el texto completo online desde la URL, revisando antes derechos y muros de pago.

## Licencia y cita

Pendiente de definir por el equipo investigador: añadir `LICENSE` y `CITATION.cff` antes de publicar.

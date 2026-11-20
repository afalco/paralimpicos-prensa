from prensa_paralimpica.extract import summary_day
from prensa_paralimpica.indexer import entry_from_lines
from prensa_paralimpica.metadata import (
    parse_broadcast_meta,
    parse_online_meta,
    parse_print_meta,
    strip_print_header,
    to_number,
)
from prensa_paralimpica.text import clean_text, norm, quality_score

# Fragmentos con el formato observado en los PDF de 2025.
PRINT = """SECCIÓN:
OTS:
DIFUSIÓN:
FRECUENCIA:
ÁREA:
AVE:
PÁGINAS:
PAÍS:
DEPORTES
74000
7976
Diario
94 CM² - 10%
731 €
35
España
8 Enero, 2025
"""

PRINT_SIN_OTS = """SECCIÓN:
OTS:
DIFUSIÓN:
FRECUENCIA:
ÁREA:
AVE:
PÁGINAS:
PAÍS:
GUADALAJARA
661
Semanal
254 CM² - 29%
392 €
10
España
4 Enero, 2025
"""

ONLINE = """La UPV y AEEPIM promueven el primer torneo
Pulse aquí para acceder a la versión online8 Enero, 2025
@ SUPERDEPORTE.ES 0,28 minTMU:
1470457OTS:
124264AMD:superdeporte.es
AVE:
PAÍS:
URL:
UnknownAUTOR:
6710 €
España
"""

TV = """Texto de la transcripción...
IB3
PROGRAMA: IB3 NOTICIES MIGDIA
OTS: 10000
HORA EMISIÓN: 14:48
AVE: 5320 €
DURACIÓN: 112 s
PAÍS: Spain
"""


def test_norm_and_clean():
    assert norm("Paralímpica ÑANDÚ") == "paralimpica nandu"
    assert clean_text("pre- sidente del\n  Comité") == "presidente del Comité"


def test_quality_score():
    real = ("el presidente del comité aseguró que entre los retos de la nueva etapa está bajar "
            "la edad media de los deportistas con la base")
    assert quality_score(real) > 0.3
    assert quality_score("&RLQFLGLHQGR FRQ HO LQLFLR GH OD WHPSRUDGD " * 5) < 0.05
    assert quality_score("demasiado corto") == 0.0


def test_print_meta():
    m = parse_print_meta(PRINT)
    assert m["seccion"] == "DEPORTES" and m["ots"] == "74000" and m["difusion"] == "7976"
    assert m["frecuencia"] == "Diario" and m["ave_eur"] == "731 €" and m["paginas_medio"] == "35"
    m2 = parse_print_meta(PRINT_SIN_OTS)
    assert m2["difusion"] == "661" and m2["paginas_medio"] == "10" and "ots" not in m2


def test_online_and_tv_meta():
    o = parse_online_meta(ONLINE)
    assert o["ots"] == "1470457" and o["amd"] == "124264" and o["ave_eur"] == "6710"
    t = parse_broadcast_meta(TV)
    assert t["programa"] == "IB3 NOTICIES MIGDIA" and t["duracion_s"] == "112 s" and t["hora"] == "14:48"


def test_strip_header_and_numbers():
    ocr = "Diario de Noticias 8 Enero, 2025 PAÍS: España SECCION: DEPORTES Alberto Durán revela sus metas"
    assert strip_print_header(ocr).strip().startswith("Alberto Durán")
    assert to_number("6710 €") == 6710 and to_number("1.470.457") == 1470457 and to_number(None) is None


def test_index_entry():
    e = entry_from_lines(
        ["Joan Munar, medallista paralímpic,", "en la Sant Silvestre", "IB3 - IB3 NOTICIES MIGDIA - 01/01/2025"], 8)
    assert e.titular.startswith("Joan Munar") and e.medio == "IB3" and e.programa == "IB3 NOTICIES MIGDIA"
    assert e.fecha == "01/01/2025" and not e.online
    e2 = entry_from_lines(["Titular online", "@ SUPERDEPORTE.ES - 07/01/2025"], 14)
    assert e2.online and e2.medio == "SUPERDEPORTE.ES"
    e3 = entry_from_lines(["Titular sin medio"], 3)
    assert e3.linea_medio == "?"


def test_summary_day():
    assert summary_day("20250107 digital") == "20250107"
    assert summary_day("20250113 digi") == "20250113"
    assert summary_day("224impresa") is None
    assert summary_day("202506274") is None  # nombre anómalo: 9 dígitos

"""Tests de los formatos B (desde 4/3/2025) y C (Onclusive, desde junio de 2025)."""

import pandas as pd

from prensa_paralimpica.extract import cover_date
from prensa_paralimpica.indexer import entry_from_lines
from prensa_paralimpica.metadata import (
    broadcast_body,
    is_broadcast,
    is_online,
    online_body,
    parse_broadcast_meta,
    parse_online_meta,
    to_number,
)
from prensa_paralimpica.text import clean_text, xlsx_safe

ONLINE_B = """Albacete será sede de los Cuartos de Final de la Champions
Cup de Baloncesto en Silla de Ruedas
La ciudad de Albacete se convierte en un enclave fundamental para el deporte internacional …
diariodelamancha.com
PAÍS: ESP
TIPO: web
AVE: €54.00
AUDIENCIA:
AUTOR:
URL: diariodelamancha.com
> 5 de marzo de 2025,
"""

ONLINE_B_FULL = """Mia Carol Bruguera i l'alta costura capil·lar
El guia que va protagonitzar un dels moments esportius més recordats …
ElPeriodico.cat
PAÍS: ESP
TIPO: web
AVE: €2366.87
AUDIENCIA: 577465
AMD: 43831.00
TMU: 0.15 min
AUTOR: Laura Estirado
URL: www.elperiodico.cat
"""

RADIO_C = """00:24:05 Javier Tebas, el presidente de la Liga, dando algunas de las explicaciones hoy en el micrófono de José David
Palacio, ha estado por aquí Teresa Perales después de los Juegos Paralímpicos. 00:24:32
La nadadora paralímpica Teresa Pereales, en el II
Congreso de As Deporte en Positivo
Cadena Ser ()
País : Spain
PROGRAMA : EL LARGUERO 00:00
DURACIÓN : 27
 10 junio 2025
"""

TV_A = """Una tradició que no es va voler perdre Joan Munar, medallista paralímpic el passat estiu a París.
Joan Munar, medallista paralímpic, en la Sant
Silvestre de Calvià
IB3
PROGRAMA: IB3 NOTICIES MIGDIA
OTS: 10000
HORA EMISIÓN: 14:48
AVE: 5320 €
DURACIÓN: 112 s
"""


def test_online_format_b_detected_and_parsed():
    assert is_online(ONLINE_B, "diariodelamancha.com") and not is_broadcast(ONLINE_B)
    m = parse_online_meta(ONLINE_B)
    assert m["formato_ficha"] == "B" and m["ave_eur"] == "€54.00" and m["audiencia"] is None and m["autor"] is None
    m2 = parse_online_meta(ONLINE_B_FULL)
    assert m2["audiencia"] == "577465" and m2["ots"] == "577465" and m2["amd"] == "43831.00"
    assert m2["tmu_min"] == "0.15" and m2["autor"] == "Laura Estirado" and m2["url_ficha"] == "www.elperiodico.cat"
    body = online_body(ONLINE_B)
    assert body.startswith("Albacete será sede") and "PAÍS" not in body and not body.endswith("diariodelamancha.com")


def test_broadcast_format_c():
    assert is_broadcast(RADIO_C)
    m = parse_broadcast_meta(RADIO_C)
    assert m["programa"] == "EL LARGUERO 00:00" and m["duracion_s"] == "27"
    body = broadcast_body(RADIO_C, "La nadadora paralímpica Teresa Pereales, en el II Congreso de As Deporte en Positivo",
                          "Cadena Ser")
    assert body.rstrip().endswith("00:24:32") and "Cadena Ser ()" not in body


def test_broadcast_format_a_body_keeps_transcript():
    body = broadcast_body(TV_A, "Joan Munar, medallista paralímpic, en la Sant Silvestre de Calvià", "IB3")
    assert body.endswith("passat estiu a París.")


def test_index_entry_onclusive():
    e = entry_from_lines(["Baloncesto en silla de ruedas. Agustín Alejos volverá a jugar en Brisbane",
                          "Faro de Vigo -  By ARMANDO ÁLVAREZ - (ES) - 10/06/2025",
                          "<br>BALONCESTO EN SILLA DE RUEDAS Agustín Alejos volverá a jugar en la liga australiana"], 9)
    assert e.medio == "Faro de Vigo" and e.autor == "ARMANDO ÁLVAREZ" and e.pais == "ES" and e.programa is None
    assert e.fecha == "10/06/2025" and e.titular.endswith("Brisbane")
    r = entry_from_lines(["Teresa Perales en el Congreso", "Cadena Ser () - (ES) - EL LARGUERO 00:00 - 10/06/2025"], 8)
    assert r.medio == "Cadena Ser" and r.programa == "EL LARGUERO 00:00" and r.pais == "ES"


def test_to_number_formats():
    assert to_number("€54.00") == 54.0
    assert to_number("€2366.87") == 2366.87
    assert to_number("6710 €") == 6710
    assert to_number("1.470.457") == 1470457
    assert to_number("0,28") == 0.28
    assert to_number("1.234,5") == 1234.5
    assert to_number("") is None and to_number(None) is None


def test_cover_date():
    assert cover_date("miércoles, 5 de marzo de 2025") == "20250305"
    assert cover_date("RESUMEN DE PRENSA\n10/06/2025") == "20250610"
    assert cover_date("sin fecha") is None


def test_control_characters_removed():
    txt = "es també l’amo de la \x00cadena de perruqueries"
    assert "\x00" not in clean_text(txt) and "\x00" not in xlsx_safe(txt)
    df = pd.DataFrame({"t": pd.Series([txt], dtype="string")})
    assert pd.api.types.is_string_dtype(df["t"])  # pandas >= 3 no usa dtype object

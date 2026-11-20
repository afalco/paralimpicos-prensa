import pandas as pd

from prensa_paralimpica.codebook import codify, load_codebook
from prensa_paralimpica.dedup import assign_stories, drop_exact_duplicates
from prensa_paralimpica.report import fisher_exact, summarize


def _df():
    return pd.DataFrame({
        "titular": [
            "La nadadora paralímpica Teresa Perales, premiada",
            "La nadadora paralímpica Teresa Perales, premiada en la gala",
            "El ciclista paralímpico Damián Ramos gana el campeonato",
            "Torneo de baloncesto en silla de ruedas",
        ],
        "texto": [
            "Un ejemplo de superación para las personas con discapacidad. Medalla de oro.",
            "Teresa Perales recibe el premio. Un ejemplo de superación.",
            "El ciclista, que sufre una parálisis cerebral, logró la victoria y el récord.",
            "Partido de baloncesto en silla organizado por la ONCE y el CPE para discapacitados.",
        ],
        "medio": ["MARCA", "EUROPA PRESS", "Faro de Vigo", "MSN ESPAÑA"],
        "fecha": ["10/01/2025", "10/01/2025", "11/01/2025", "12/01/2025"],
        "soporte": ["Online", "Online", "Impresa", "Online"],
        "dia_resumen": ["20250110"] * 4,
        "calidad_texto": [0.4] * 4,
    })


def test_codebook_loads_and_compiles():
    cb = load_codebook()
    assert cb.version
    assert len(cb.personas) > 10
    assert cb.tipo_de_medio("EUROPA PRESS") == "Agencia"
    assert cb.tipo_de_medio("MSN ESPAÑA") == "Agregador"
    assert cb.tipo_de_medio("MARCA") == "Deportivo"
    assert cb.tipo_de_medio("Faro de Vigo") == "Generalista/local"
    assert cb.tipo_de_medio(None) == "Generalista/local"
    assert cb.tipo_de_medio(float("nan")) == "Generalista/local"  # medio desconocido
    assert not cb.as_table().empty


def test_codify_detects_expected_categories():
    cb = load_codebook()
    df = codify(_df(), cb)
    assert df.loc[0, "hay_superacion"] and df.loc[0, "leng_recomendado"] == 1
    assert df.loc[2, "L_mal_sufre/padece + condición"] == 1
    assert df.loc[3, "L_mal_discapacitado/a(s)"] == 1
    assert df.loc[3, "dep_Baloncesto en silla"] and df.loc[3, "org_CPE"] and df.loc[3, "org_ONCE / Fundación ONCE"]
    assert df.loc[0, "P_Teresa Perales"] and df.loc[0, "menc_deportista_mujer"]
    assert df.loc[2, "menc_deportista_hombre"]
    assert df.loc[0, "gram_fem"] == 1 and df.loc[2, "gram_masc"] == 1
    assert df["para_en_titular"].sum() == 4


def test_dedup_and_stories():
    df = _df()
    dup = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    assert len(drop_exact_duplicates(dup)) == 4
    s = assign_stories(df)
    assert s[0] == s[1]  # titulares casi idénticos -> misma historia
    assert s.nunique() == 3


def test_summary_runs():
    cb = load_codebook()
    df = codify(_df(), cb)
    df["historia_id"] = assign_stories(df)
    df["n_palabras"] = 200  # fuerza piezas 'largas'
    S = summarize(df, cb)
    assert S["piezas"] == 4 and S["historias"] == 3
    assert S["genero"]["piezas_mujeres"] == 2


def test_fisher_exact_known_value():
    # Tabla clásica "lady tasting tea": [[3,1],[1,3]] -> p = 0.4857
    assert abs(fisher_exact(3, 1, 1, 3) - 0.4857) < 1e-3
    assert fisher_exact(0, 5, 5, 0) < 0.01

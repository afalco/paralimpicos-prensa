"""Indicadores agregados, figura resumen, Excel y resumen en Markdown."""

from __future__ import annotations

import json
from datetime import datetime
from math import comb
from pathlib import Path

import pandas as pd

from . import __version__
from .codebook import Codebook
from .text import xlsx_safe

SOPORTES = ["Online", "Impresa", "TV/Radio"]
COLORES = {"Online": "#4C78A8", "Impresa": "#F58518", "TV/Radio": "#54A24B"}
C_MUJER, C_HOMBRE = "#B279A2", "#4C78A8"


# ---------------------------------------------------------------------------
# Estadística

def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Test exacto de Fisher bilateral para la tabla [[a, b], [c, d]] (sin SciPy)."""
    n, r1, c1 = a + b + c + d, a + b, a + c

    def p(x: int) -> float:
        return comb(r1, x) * comb(n - r1, c1 - x) / comb(n, c1)

    p0 = p(a)
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= p0 * (1 + 1e-7)))


def _cols(df: pd.DataFrame, prefix: str) -> list[str]:
    return [c for c in df.columns if c.startswith(prefix)]


def people_table(df: pd.DataFrame, cb: Codebook) -> pd.DataFrame:
    rows = []
    for p in cb.personas:
        col = "P_" + p["nombre"]
        rows.append({
            "persona": p["nombre"], "genero": p["genero"], "rol": p["rol"],
            "piezas": int(df[col].sum()),
            "historias": int(df.loc[df[col], "historia_id"].nunique()),
        })
    return pd.DataFrame(rows).sort_values("piezas", ascending=False).reset_index(drop=True)


def summarize(df: pd.DataFrame, cb: Codebook, min_words: int = 150) -> dict:
    fechas = pd.to_datetime(df["fecha"], format="%d/%m/%Y", errors="coerce")
    S: dict = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "version_pipeline": __version__,
        "version_codebook": cb.version,
        "piezas": len(df),
        "historias": int(df["historia_id"].nunique()),
        "medios": int(df["medio"].nunique()),
        "dias_resumen": int(df["dia_resumen"].nunique()),
        "fecha_min": str(fechas.min().date()) if fechas.notna().any() else None,
        "fecha_max": str(fechas.max().date()) if fechas.notna().any() else None,
        "soporte": df["soporte"].value_counts().to_dict(),
        "tipo_medio": df["tipo_medio"].value_counts().to_dict(),
        "pct_para_en_titular": round(100 * df["para_en_titular"].mean(), 1),
        "pct_sin_mencion": round(100 * (df["menc_para"] == 0).mean(), 1),
        "calidad_texto_baja": int((df["calidad_texto"] < 0.2).sum()),
    }
    S["temas_pct"] = {c[5:]: round(100 * df[c].mean(), 1) for c in _cols(df, "tema_")}
    S["deportes_piezas"] = {c[4:]: int(df[c].sum()) for c in _cols(df, "dep_")}
    S["discapacidad_pct"] = {c[5:]: round(100 * df[c].mean(), 1) for c in _cols(df, "disc_")}
    S["organizaciones_piezas"] = {c[4:]: int(df[c].sum()) for c in _cols(df, "org_")}
    S["lenguaje"] = {
        "ocurrencias_recomendado": int(df["leng_recomendado"].sum()),
        "ocurrencias_desaconsejado": int(df["leng_desaconsejado"].sum()),
        "piezas_con_desaconsejado": int((df["leng_desaconsejado"] > 0).sum()),
        "detalle": {c.split("_", 2)[2]: int(df[c].sum()) for c in _cols(df, "L_")},
    }
    hist = df.groupby("historia_id")[["menc_deportista_mujer", "menc_deportista_hombre"]].any()
    S["genero"] = {
        "piezas_mujeres": int(df["menc_deportista_mujer"].sum()),
        "piezas_hombres": int(df["menc_deportista_hombre"].sum()),
        "historias_mujeres": int(hist["menc_deportista_mujer"].sum()),
        "historias_hombres": int(hist["menc_deportista_hombre"].sum()),
        "gramatical_fem": int(df["gram_fem"].sum()),
        "gramatical_masc": int(df["gram_masc"].sum()),
    }
    largas = df[df["n_palabras"] >= min_words]
    m, h = largas[largas["menc_deportista_mujer"]], largas[largas["menc_deportista_hombre"]]
    a, b = int(m["hay_superacion"].sum()), int((~m["hay_superacion"]).sum())
    c, d = int(h["hay_superacion"].sum()), int((~h["hay_superacion"]).sum())
    S["encuadre"] = {
        "min_palabras": min_words,
        "piezas_largas": len(largas),
        "pct_superacion_por_soporte": (100 * largas.groupby("soporte")["hay_superacion"].mean()).round(1).to_dict(),
        "superacion_mujeres": f"{a}/{a + b}",
        "superacion_hombres": f"{c}/{c + d}",
        "fisher_p": round(fisher_exact(a, b, c, d), 4) if (a + b) and (c + d) else None,
    }
    # Mismo contraste a nivel de HISTORIA (unidad independiente: evita inflar n con la sindicación)
    hs = largas.groupby("historia_id").agg(sup=("hay_superacion", "max"), M=("menc_deportista_mujer", "max"),
                                           H=("menc_deportista_hombre", "max"))
    hm, hh = hs[hs["M"]], hs[hs["H"]]
    a, b = int(hm["sup"].sum()), int((~hm["sup"]).sum())
    c, d = int(hh["sup"].sum()), int((~hh["sup"]).sum())
    S["encuadre"].update({
        "historias_superacion_mujeres": f"{a}/{a + b}",
        "historias_superacion_hombres": f"{c}/{c + d}",
        "historias_fisher_p": round(fisher_exact(a, b, c, d), 4) if (a + b) and (c + d) else None,
    })
    top = (df.groupby("historia_id")
             .agg(piezas=("titular", "size"), medios=("medio", "nunique"), titular=("titular", "first"))
             .sort_values("piezas", ascending=False).head(10))
    S["top_historias"] = top.to_dict(orient="records")
    return S


# ---------------------------------------------------------------------------
# Figura

def panel_figure(df: pd.DataFrame, cb: Codebook, S: dict, path: Path, titulo: str) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(3, 2, figsize=(13, 14))

    # A. Volumen temporal (diario si <= 62 días; semanal si más)
    f = pd.to_datetime(df["fecha"], format="%d/%m/%Y", errors="coerce")
    d = df.assign(_f=f).dropna(subset=["_f"])
    span = (d["_f"].max() - d["_f"].min()).days if len(d) else 0
    freq, lab = ("D", "día") if span <= 62 else ("W-MON", "semana")
    vol = (d.groupby([pd.Grouper(key="_f", freq=freq), "soporte"]).size()
             .unstack(fill_value=0).reindex(columns=SOPORTES, fill_value=0))
    bottom = None
    for s in SOPORTES:
        ax[0, 0].bar(vol.index, vol[s], bottom=bottom, color=COLORES[s], label=s,
                     width=0.8 if freq == "D" else 5)
        bottom = vol[s] if bottom is None else bottom + vol[s]
    ax[0, 0].set_title(f"A. Piezas por {lab} de publicación", loc="left", fontweight="bold")
    ax[0, 0].set_ylabel("Piezas")
    ax[0, 0].legend(frameon=False)
    ax[0, 0].tick_params(axis="x", rotation=45)

    def hbar(a, series, color, title, xlabel, fmt="{:.0f}"):
        s = pd.Series(series, dtype=float).sort_values()
        a.barh(s.index, s.values, color=color)
        a.set_title(title, loc="left", fontweight="bold")
        a.set_xlabel(xlabel)
        for y, v in enumerate(s.values):
            a.text(v, y, " " + fmt.format(v), va="center")

    hbar(ax[0, 1], S["temas_pct"], "#72B7B2", "B. Temas detectados", "% de piezas (multi-etiqueta)", "{:.0f}%")

    pt = people_table(df, cb).head(20).iloc[::-1]
    ax[1, 0].barh(pt["persona"], pt["piezas"], color=[C_MUJER if g == "mujer" else C_HOMBRE for g in pt["genero"]])
    ax[1, 0].set_title("C. Personas más mencionadas (lista curada)", loc="left", fontweight="bold")
    ax[1, 0].set_xlabel("Piezas")
    ax[1, 0].legend(handles=[Patch(color=C_MUJER, label="Mujer"), Patch(color=C_HOMBRE, label="Hombre")],
                    frameon=False, loc="lower right")

    deps = dict(sorted(S["deportes_piezas"].items(), key=lambda kv: -kv[1])[:12])
    hbar(ax[1, 1], deps, "#E45756", "D. Modalidades deportivas mencionadas", "Piezas")

    L = {k: v for k, v in S["lenguaje"]["detalle"].items() if v > 0}
    if L:
        Ls = pd.Series(L).sort_values()
        ax[2, 0].barh(Ls.index, Ls.values,
                      color=["#54A24B" if k in cb.recomendado else "#E45756" for k in Ls.index])
        ax[2, 0].set_xscale("log")
        for y, v in enumerate(Ls.values):
            ax[2, 0].text(v * 1.1, y, str(v), va="center")
    ax[2, 0].set_xlabel("Ocurrencias (escala log)")
    ax[2, 0].set_title("E. Lenguaje: recomendado (verde) vs desaconsejado (rojo)", loc="left", fontweight="bold")

    orgs = {k: v for k, v in S["organizaciones_piezas"].items() if v >= 3}
    hbar(ax[2, 1], orgs, "#9D755D", "F. Organizaciones y patrocinadores", "Piezas")

    fig.suptitle(f"{titulo} (n = {S['piezas']} piezas, {S['historias']} historias, {S['medios']} medios)",
                 fontsize=12, fontweight="bold", y=0.995)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Exportaciones

def export_excel(df: pd.DataFrame, cb: Codebook, S: dict, path: Path) -> Path:
    hist = (df.groupby("historia_id")
              .agg(piezas=("titular", "size"), medios=("medio", "nunique"),
                   primera_fecha=("fecha", "first"), titular=("titular", "first"))
              .sort_values("piezas", ascending=False).reset_index())
    medios = (df.groupby(["medio", "tipo_medio"])
                .agg(piezas=("titular", "size"), soporte=("soporte", lambda s: s.mode().iat[0]))
                .sort_values("piezas", ascending=False).reset_index())
    calidad = (df.groupby(["soporte", "metodo_texto"])
                 .agg(piezas=("titular", "size"), palabras_mediana=("n_palabras", "median"),
                      calidad_mediana=("calidad_texto", "median"),
                      calidad_baja=("calidad_texto", lambda s: int((s < 0.2).sum())))
                 .reset_index())
    resumen = pd.DataFrame(
        [(k, json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in S.items()],
        columns=["indicador", "valor"])
    sheets = {
        "piezas": df, "resumen": resumen, "personas": people_table(df, cb), "historias": hist,
        "medios": medios, "calidad_texto": calidad, "libro_de_codigos": cb.as_table(),
    }
    with pd.ExcelWriter(path) as w:
        for name, d in sheets.items():
            d = d.copy()
            for col in d.columns:
                if d[col].dtype == object or pd.api.types.is_string_dtype(d[col]):
                    d[col] = d[col].map(xlsx_safe)
            d.to_excel(w, sheet_name=name, index=False)
    return path


def write_markdown(S: dict, path: Path, titulo: str) -> Path:
    g, e, L = S["genero"], S["encuadre"], S["lenguaje"]
    sop = " · ".join(f"{k} {v}" for k, v in S["soporte"].items())
    tm = " · ".join(f"{k} {v}" for k, v in S["tipo_medio"].items())
    temas = "\n".join(f"| {k} | {v} % |" for k, v in sorted(S["temas_pct"].items(), key=lambda kv: -kv[1]))
    top = "\n".join(f"| {r['piezas']} | {r['medios']} | {r['titular'][:110]} |" for r in S["top_historias"])
    md = f"""# {titulo}

*Generado automáticamente el {S['generado']} · pipeline v{S['version_pipeline']} · libro de códigos v{S['version_codebook']}.*
*Indicadores descriptivos sin validación manual: no interpretar como resultados definitivos.*

## Corpus
| Indicador | Valor |
|---|---|
| Piezas / historias / medios | {S['piezas']} / {S['historias']} / {S['medios']} |
| Días de resumen | {S['dias_resumen']} |
| Fechas de publicación | {S['fecha_min']} → {S['fecha_max']} |
| Soporte | {sop} |
| Tipo de medio | {tm} |
| % con término paralímpico/discapacidad en el titular | {S['pct_para_en_titular']} % |
| % sin ningún término (ni titular ni texto) | {S['pct_sin_mencion']} % |
| Piezas con calidad de texto baja (< 0,2) | {S['calidad_texto_baja']} |

## Temas (% de piezas, multi-etiqueta)
| Tema | % |
|---|---|
{temas}

## Género (lista curada de deportistas)
| | Mujeres | Hombres |
|---|---|---|
| Piezas | {g['piezas_mujeres']} | {g['piezas_hombres']} |
| Historias | {g['historias_mujeres']} | {g['historias_hombres']} |
| Referencias gramaticales «deportista paralímpica/o» | {g['gramatical_fem']} | {g['gramatical_masc']} |

## Lenguaje
Recomendado: **{L['ocurrencias_recomendado']}** ocurrencias · Desaconsejado: **{L['ocurrencias_desaconsejado']}** ocurrencias en {L['piezas_con_desaconsejado']} piezas.

## Encuadre de superación (piezas ≥ {e['min_palabras']} palabras, n = {e['piezas_largas']})
- % con algún término de superación, por soporte: {e['pct_superacion_por_soporte']}
- Por pieza — mencionan deportistas mujeres: {e['superacion_mujeres']} · hombres: {e['superacion_hombres']} · Fisher bilateral p = {e['fisher_p']}
- Por historia (unidad recomendada) — mujeres: {e['historias_superacion_mujeres']} · hombres: {e['historias_superacion_hombres']} · Fisher bilateral p = {e['historias_fisher_p']}

## Historias con más piezas (sindicación)
| Piezas | Medios | Titular |
|---|---|---|
{top}
"""
    path.write_text(md, encoding="utf-8")
    return path

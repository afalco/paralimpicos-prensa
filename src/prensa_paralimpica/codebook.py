"""Carga del libro de códigos (TOML) y codificación automática de las piezas."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .text import norm

DEFAULT_CODEBOOK = Path(__file__).resolve().parents[2] / "config" / "codebook.toml"


@dataclass
class Codebook:
    version: str
    relevancia: re.Pattern
    desaconsejado: dict[str, str]
    recomendado: dict[str, str]
    superacion: re.Pattern
    deportivo: re.Pattern
    temas: dict[str, str]
    deportes: dict[str, str]
    discapacidad: dict[str, str]
    organizaciones: dict[str, str]
    tipo_medio: dict[str, str]
    personas: list[dict]
    roles_genero: str
    raw: dict = field(repr=False, default_factory=dict)

    def tipo_de_medio(self, medio: str | None) -> str:
        name = medio.upper() if isinstance(medio, str) else ""
        for label, pattern in self.tipo_medio.items():
            if re.search(pattern, name):
                return label
        return "Generalista/local"

    def as_table(self) -> pd.DataFrame:
        """Libro de códigos en formato tabla (para anexos y para el Excel)."""
        rows = [("Relevancia", "términos paralímpicos/discapacidad", self.relevancia.pattern)]
        rows += [("Lenguaje desaconsejado", k, v) for k, v in self.desaconsejado.items()]
        rows += [("Lenguaje recomendado", k, v) for k, v in self.recomendado.items()]
        rows += [("Encuadre", "Superación/inspiración", self.superacion.pattern),
                 ("Encuadre", "Deportivo/rendimiento", self.deportivo.pattern)]
        for dim, d in [("Tema", self.temas), ("Deporte", self.deportes),
                       ("Tipo de discapacidad", self.discapacidad), ("Organización", self.organizaciones),
                       ("Tipo de medio (sobre nombre del medio)", self.tipo_medio)]:
            rows += [(dim, k, v) for k, v in d.items()]
        rows += [(f"Persona ({p['rol']}, {p['genero']})", p["nombre"], p["patron"]) for p in self.personas]
        return pd.DataFrame(rows, columns=["dimension", "categoria", "regex (texto en minusculas y sin tildes)"])


def _words(patterns: list[str]) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(patterns) + r")\b")


def load_codebook(path: str | Path | None = None) -> Codebook:
    path = Path(path) if path else DEFAULT_CODEBOOK
    cfg = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    cb = Codebook(
        version=cfg["meta"]["version"],
        relevancia=_words(cfg["relevancia"]["patrones"]),
        desaconsejado=cfg["lenguaje"]["desaconsejado"],
        recomendado=cfg["lenguaje"]["recomendado"],
        superacion=_words(cfg["encuadre"]["superacion"]),
        deportivo=_words(cfg["encuadre"]["deportivo"]),
        temas=cfg["temas"],
        deportes=cfg["deportes"],
        discapacidad=cfg["discapacidad"],
        organizaciones=cfg["organizaciones"],
        tipo_medio=cfg["tipo_medio"],
        personas=cfg["personas"],
        roles_genero=cfg["genero_gramatical"]["roles"],
        raw=cfg,
    )
    # Validación: todas las expresiones deben compilar.
    for d in (cb.desaconsejado, cb.recomendado, cb.temas, cb.deportes, cb.discapacidad,
              cb.organizaciones, cb.tipo_medio):
        for k, v in d.items():
            try:
                re.compile(v)
            except re.error as exc:
                raise ValueError(f"Regex inválida en '{k}': {v!r} ({exc})") from exc
    for p in cb.personas:
        re.compile(p["patron"])
        if p["genero"] not in ("mujer", "hombre"):
            raise ValueError(f"Género no válido para {p['nombre']}: {p['genero']}")
    return cb


def codify(df: pd.DataFrame, cb: Codebook) -> pd.DataFrame:
    """Añade todas las variables codificadas. Devuelve un DataFrame nuevo."""
    tit = df["titular"].fillna("").map(norm)
    txt = (df["titular"].fillna("") + " . " + df["texto"].fillna("")).map(norm)
    c: dict[str, pd.Series] = {}
    c["n_palabras"] = txt.str.count(r"\w+")
    c["menc_para"] = txt.map(lambda s: len(cb.relevancia.findall(s)))
    c["para_en_titular"] = tit.map(lambda s: bool(cb.relevancia.search(s)))
    c["tipo_medio"] = df["medio"].map(cb.tipo_de_medio)
    for k, v in cb.desaconsejado.items():
        c[f"L_mal_{k}"] = txt.str.count(v)
    for k, v in cb.recomendado.items():
        c[f"L_bien_{k}"] = txt.str.count(v)
    c["leng_desaconsejado"] = sum(c[f"L_mal_{k}"] for k in cb.desaconsejado)
    c["leng_recomendado"] = sum(c[f"L_bien_{k}"] for k in cb.recomendado)
    c["enc_superacion"] = txt.map(lambda s: len(cb.superacion.findall(s)))
    c["enc_deportivo"] = txt.map(lambda s: len(cb.deportivo.findall(s)))
    c["hay_superacion"] = c["enc_superacion"] > 0
    words = c["n_palabras"].clip(lower=1)
    c["superacion_x1000"] = 1000 * c["enc_superacion"] / words
    c["deportivo_x1000"] = 1000 * c["enc_deportivo"] / words
    for prefix, d in [("tema_", cb.temas), ("dep_", cb.deportes),
                      ("disc_", cb.discapacidad), ("org_", cb.organizaciones)]:
        for k, v in d.items():
            c[prefix + k] = txt.str.contains(v, regex=True)
    for p in cb.personas:
        c["P_" + p["nombre"]] = txt.str.contains(r"\b" + p["patron"], regex=True)
    dep = [p for p in cb.personas if p["rol"] == "Deportista"]
    c["menc_deportista_mujer"] = pd.concat(
        [c["P_" + p["nombre"]] for p in dep if p["genero"] == "mujer"], axis=1).any(axis=1)
    c["menc_deportista_hombre"] = pd.concat(
        [c["P_" + p["nombre"]] for p in dep if p["genero"] == "hombre"], axis=1).any(axis=1)
    roles = cb.roles_genero
    c["gram_fem"] = txt.str.count(
        rf"\b(?:la|una) {roles} paralimpica\b|\b(?:nadadora|jugadora|esquiadora|campeona|lanzadora) paralimpica\b")
    c["gram_masc"] = txt.str.count(
        rf"\b(?:el|un) {roles} paralimpico\b|\b(?:nadador|jugador|esquiador|campeon|lanzador) paralimpico\b")
    out = pd.concat([df.reset_index(drop=True), pd.DataFrame(c).reset_index(drop=True)], axis=1)
    out.attrs["codebook_version"] = cb.version
    return out

"""Línea de órdenes: ``prensa-para {extract,codify,report,run}``.

Ejemplos::

    prensa-para run --root "/Volumes/My Passport/2025" --months 01
    prensa-para run --root "/Volumes/My Passport/2025" --tag 2025      # año completo
    prensa-para extract --root ... --months 01 02 --ocr livetext
    prensa-para codify --tag meses_01                                 # re-codifica sin repetir OCR
    prensa-para report --tag meses_01 --label "Enero 2025"
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

from . import __version__
from .codebook import DEFAULT_CODEBOOK, codify, load_codebook
from .dedup import assign_stories, drop_exact_duplicates
from .extract import extract_corpus
from .ocr import BACKENDS
from .report import export_excel, panel_figure, summarize, write_markdown

log = logging.getLogger("prensa_paralimpica")


def _paths(args) -> dict[str, Path]:
    data = Path(args.data_dir)
    tag = args.tag or ("meses_" + "-".join(args.months) if args.months else "todo")
    return {
        "cache": data / "interim",
        "corpus": data / "processed" / f"corpus_{tag}.pkl",
        "coded": data / "processed" / f"corpus_codificado_{tag}.pkl",
        "out": Path(args.out_dir) / tag,
    }


def cmd_extract(args) -> pd.DataFrame:
    p = _paths(args)
    rows = extract_corpus(Path(args.root), p["cache"], args.months, args.ocr, args.dpi, args.force)
    df = pd.DataFrame(rows)
    n0 = len(df)
    df = drop_exact_duplicates(df)
    log.info("Duplicados exactos eliminados: %d (quedan %d piezas)", n0 - len(df), len(df))
    df["historia_id"] = assign_stories(df)
    p["corpus"].parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(p["corpus"])
    log.info("Corpus guardado en %s", p["corpus"])
    return df


def cmd_codify(args, df: pd.DataFrame | None = None) -> pd.DataFrame:
    p = _paths(args)
    if df is None:
        df = pd.read_pickle(p["corpus"])
    cb = load_codebook(args.codebook)
    coded = codify(df, cb)
    coded.to_pickle(p["coded"])
    log.info("Corpus codificado (libro de códigos v%s) en %s", cb.version, p["coded"])
    return coded


def cmd_report(args, coded: pd.DataFrame | None = None) -> dict:
    p = _paths(args)
    if coded is None:
        coded = pd.read_pickle(p["coded"])
    cb = load_codebook(args.codebook)
    out = p["out"]
    out.mkdir(parents=True, exist_ok=True)
    label = args.label or out.name
    titulo = f"Cobertura de prensa del deporte paralímpico — {label}"
    S = summarize(coded, cb)
    (out / "resumen.json").write_text(json.dumps(S, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    panel_figure(coded, cb, S, out / "panel.png", titulo)
    export_excel(coded, cb, S, out / "dataset.xlsx")
    coded.drop(columns=["texto"]).to_csv(out / "piezas_sin_texto.csv", index=False)
    coded.to_csv(out / "piezas_con_texto.csv.gz", index=False, compression="gzip")
    write_markdown(S, out / "resumen.md", titulo)
    log.info("Informe en %s", out)
    return S


def cmd_run(args) -> dict:
    df = cmd_extract(args)
    coded = cmd_codify(args, df)
    return cmd_report(args, coded)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="prensa-para", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, needs_root in [("extract", True), ("run", True), ("codify", False), ("report", False)]:
        sp = sub.add_parser(name)
        if needs_root:
            sp.add_argument("--root", required=True, help="Carpeta del año (contiene '01 Enero', ...)")
            sp.add_argument("--ocr", default="livetext", choices=BACKENDS, help="Motor de OCR para prensa impresa")
            sp.add_argument("--dpi", type=int, default=200)
            sp.add_argument("--force", action="store_true", help="Ignorar la caché y reprocesar")
        sp.add_argument("--months", nargs="*", default=None, help="Meses, p. ej. 01 02 (por defecto: todos)")
        sp.add_argument("--tag", default=None, help="Nombre de la ejecución (por defecto se deriva de --months)")
        sp.add_argument("--data-dir", default="data", help="Datos intermedios (no se versionan)")
        sp.add_argument("--out-dir", default="outputs", help="Carpeta de resultados")
        sp.add_argument("--codebook", default=str(DEFAULT_CODEBOOK), help="Libro de códigos TOML")
        sp.add_argument("--label", default=None, help="Etiqueta para títulos (p. ej. 'Enero 2025')")
        sp.add_argument("-v", "--verbose", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)
    {"extract": cmd_extract, "codify": cmd_codify, "report": cmd_report, "run": cmd_run}[args.cmd](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

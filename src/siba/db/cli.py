"""Ligne de commande : siba-db update | rebuild."""

from __future__ import annotations

import argparse

from . import loader


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db-path", default=None, help="Chemin de la base DuckDB.")

    parser = argparse.ArgumentParser(
        prog="siba-db",
        description="Chargement DuckDB nappes + pluie.",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("update", parents=[common], help="Mise à jour incrémentale (défaut).")
    sub.add_parser("rebuild", parents=[common], help="Reconstruction complète.")

    args = parser.parse_args(argv)
    if args.command == "rebuild":
        loader.rebuild(db_path=args.db_path)
    else:
        loader.update(db_path=args.db_path)
    return 0

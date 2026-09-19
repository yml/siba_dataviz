"""Ligne de commande : siba-db update | rebuild."""

from __future__ import annotations

import argparse

from . import loader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="siba-db",
        description="Chargement DuckDB nappes + pluie.",
    )
    # --db-path is declared in exactly one place (the subparsers). The root
    # only carries a default so args.db_path exists when no subcommand is given
    # (bare `siba-db` == update). Putting the flag on both parsers made the
    # subparser default silently clobber a pre-subcommand value.
    parser.set_defaults(db_path=None)
    sub = parser.add_subparsers(dest="command")
    for name, help_text in (
        ("update", "Mise à jour incrémentale (défaut)."),
        ("rebuild", "Reconstruction complète."),
    ):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--db-path", default=None, help="Chemin de la base DuckDB.")

    args = parser.parse_args(argv)
    if args.command == "rebuild":
        loader.rebuild(db_path=args.db_path)
    else:
        loader.update(db_path=args.db_path)
    return 0

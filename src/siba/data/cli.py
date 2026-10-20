"""Ligne de commande : siba update | rebuild [--refresh] | versions | snapshot | restore <nom> | prune [--keep N]."""

from __future__ import annotations

import argparse
import sys

from . import loader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="siba",
        description="Chargement DuckDB nappes + pluie.",
    )
    # --db-path is declared in exactly one place (the subparsers). The root
    # only carries a default so args.db_path exists when no subcommand is given
    # (bare `siba` == update). Putting the flag on both parsers made the
    # subparser default silently clobber a pre-subcommand value.
    parser.set_defaults(db_path=None)
    sub = parser.add_subparsers(dest="command")
    for name, help_text in (
        ("update", "Mise à jour incrémentale (défaut)."),
        ("rebuild", "Reconstruction complète."),
        ("versions", "Liste les versions de la base (la courante est marquée *)."),
        ("snapshot", "Copie la version courante et y pointe la base."),
        ("restore", "Pointe la base sur une version existante."),
        ("prune", "Supprime les anciennes versions (jamais la courante)."),
    ):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--db-path", default=None, help="Chemin de la base DuckDB.")
        if name == "rebuild":
            sp.add_argument("--refresh", action="store_true", help="Retélécharge toutes les sources.")
        if name == "restore":
            sp.add_argument("name", help="Nom de la version (voir `versions`).")
        if name == "prune":
            sp.add_argument("--keep", type=int, default=None,
                            help="Versions récentes à garder (défaut : VERSIONS_KEEP ; "
                                 "0 = toutes sauf la courante).")

    args = parser.parse_args(argv)
    # Refus attendus (version inconnue, .wal, lien cassé, source vide) : une
    # ligne sur stderr et code 1, sans trace Python.
    try:
        if args.command == "rebuild":
            loader.rebuild(db_path=args.db_path, refresh=args.refresh)
        elif args.command == "versions":
            loader.list_versions(db_path=args.db_path)
        elif args.command == "snapshot":
            loader.snapshot(db_path=args.db_path)
        elif args.command == "restore":
            loader.restore(args.name, db_path=args.db_path)
        elif args.command == "prune":
            loader.prune(db_path=args.db_path, keep=args.keep)
        else:
            loader.update(db_path=args.db_path)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    return 0

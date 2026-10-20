"""Versions de la base : fichiers horodatés sous versions/, lien symbolique siba.duckdb.

``_data/siba.duckdb`` est un lien relatif vers
``_data/versions/<aaaammjj_hhmmss>__(load|snapshot)__siba.duckdb``. Un
chargement construit sa version dans un ``.tmp`` puis bascule le lien
(``os.replace`` d'un lien temporaire : atomique). Un client déjà ouvert garde
la version qu'il a ouverte.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

from . import config, schema

#: Nom fixe en fin de fichier, quel que soit le nom du lien (--db-path).
VERSION_SUFFIX = "siba.duckdb"
VERSION_RE = re.compile(r"^(\d{8}_\d{6})__(load|snapshot)__siba\.duckdb$")
_FMT = "%Y%m%d_%H%M%S"


def _now() -> dt.datetime:
    return dt.datetime.now()


def versions_dir(db_path) -> Path:
    return Path(db_path).parent / "versions"


def current(db_path) -> Path | None:
    """Cible du lien (chemin absolu), None si *db_path* n'est pas un lien."""
    p = Path(db_path)
    return (p.parent / os.readlink(p)).resolve() if p.is_symlink() else None


def _wal(path) -> Path:
    return path.with_name(path.name + ".wal")


def flip(db_path, target) -> None:
    """Pointe le lien sur *target* : lien temporaire puis os.replace (atomique)."""
    db_path = Path(db_path)
    tmp = db_path.with_name(db_path.name + ".lnk.tmp")
    tmp.unlink(missing_ok=True)
    os.symlink(os.path.relpath(target, db_path.parent), tmp)
    os.replace(tmp, db_path)


def _new_name(vdir, kind) -> str:
    """Nom horodaté libre (attend la seconde suivante en cas de collision)."""
    while True:
        name = f"{_now().strftime(_FMT)}__{kind}__{VERSION_SUFFIX}"
        if not (vdir / name).exists() and not (vdir / (name + ".tmp")).exists():
            return name
        time.sleep(1)


def list_versions(db_path) -> list[dict]:
    """Versions triées par nom : ``{"name", "kind", "size", "current"}``."""
    vdir = versions_dir(db_path)
    if not vdir.is_dir():
        return []
    cur = current(db_path)
    rows = []
    for p in sorted(vdir.iterdir()):
        m = VERSION_RE.match(p.name)
        if m:
            rows.append({
                "name": p.name, "kind": m.group(2),
                "size": p.stat().st_size, "current": p.resolve() == cur,
            })
    return rows


def prune(db_path, keep=None) -> list[Path]:
    """Supprime les versions au-delà des *keep* plus récentes (commande ``prune``).

    Jamais appelée automatiquement. Jamais la version courante, ni une version qui a un ``.wal`` (client en
    écriture ouvert). Les fichiers hors motif (``.tmp`` orphelins…) sont ignorés.
    """
    keep = config.VERSIONS_KEEP if keep is None else keep
    if keep < 0:
        raise RuntimeError(f"--keep doit être positif ou nul (reçu {keep}).")
    vdir = versions_dir(db_path)
    if not vdir.is_dir():
        return []
    cur = current(db_path)
    names = sorted((p for p in vdir.iterdir() if VERSION_RE.match(p.name)), reverse=True)
    removed = []
    for p in names[keep:]:
        if p.resolve() == cur or _wal(p).exists():
            continue
        p.unlink()
        removed.append(p)
    return removed


def migrate(db_path) -> Path | None:
    """Transforme une base classique (fichier) en première version + lien.

    Lien dur puis bascule : *db_path* n'est jamais absent. Sans effet si
    *db_path* est déjà un lien ou n'existe pas.
    """
    p = Path(db_path)
    if p.is_symlink() or not p.exists():
        return None
    if _wal(p).exists():
        raise RuntimeError(
            f"{p.name}.wal présent : fermer le client DuckDB (UI, notebook) "
            "avant de migrer la base en versions."
        )
    ts = dt.datetime.fromtimestamp(p.stat().st_mtime).strftime(_FMT)
    target = versions_dir(p) / f"{ts}__load__{VERSION_SUFFIX}"
    target.parent.mkdir(parents=True, exist_ok=True)
    os.link(p, target)
    flip(p, target)
    print(f"Migration : {p.name} → versions/{target.name}")
    return target


@contextmanager
def new_version(db_path, kind, *, copy=True):
    """Construit une nouvelle version et bascule le lien en cas de succès.

    La connexion fournie ouvre ``versions/<nom>.tmp``, copie de la version
    courante (*copy*) ou base vide. Une exception supprime le ``.tmp`` et laisse
    le lien intact. Avec *copy*, un lien qui pointe sur une version absente est
    refusé : partir d'une base vide perdrait les données sans prévenir.
    """
    p = Path(db_path)
    vdir = versions_dir(p)
    vdir.mkdir(parents=True, exist_ok=True)
    src = current(p)
    if src is not None and _wal(src).exists():
        raise RuntimeError(
            f"{src.name}.wal présent : un client en écriture a des modifications "
            "non écrites ; fermer DuckDB UI / le notebook avant de charger."
        )
    if copy and src is not None and not src.exists():
        raise RuntimeError(
            f"{p.name} pointe sur une version absente : {src.name} ; "
            "make versions puis make restore V=<nom>."
        )
    name = _new_name(vdir, kind)
    final = vdir / name
    tmp = vdir / (name + ".tmp")
    con = None
    # Copie et ouverture dans le try : une copie ratée ou une version courante
    # illisible ne laisse pas de .tmp orphelin.
    try:
        if copy and src is not None:
            shutil.copy2(src, tmp)
        con = schema.connect(tmp)
        yield con
        con.execute("CHECKPOINT")
    except BaseException:
        if con is not None:
            con.close()
        tmp.unlink(missing_ok=True)
        _wal(tmp).unlink(missing_ok=True)
        raise
    con.close()
    os.replace(tmp, final)
    flip(p, final)
    print(f"Version : versions/{name}")


def snapshot(db_path) -> Path:
    """Copie la version courante en ``__snapshot__`` et y pointe le lien."""
    if current(db_path) is None:
        raise RuntimeError(f"Aucune base à copier : {db_path} n'est pas une version.")
    with new_version(db_path, "snapshot"):
        pass
    return current(db_path)


def restore(db_path, name) -> Path:
    """Pointe le lien sur la version *name* ; ne copie ni ne supprime rien."""
    target = versions_dir(db_path) / name
    if not VERSION_RE.match(name) or not target.exists():
        raise FileNotFoundError(f"Version inconnue : {name}")
    flip(Path(db_path), target)
    return target

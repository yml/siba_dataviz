#!/usr/bin/env python3
"""Récupère les analyses bactériologiques (E. coli, entérocoques) depuis le
portail Enki du SIBA, année par année.

L'export interactif du portail tombe en erreur sur de grandes périodes : on
découpe donc la requête par année et on écrit un CSV par année.

Authentification : le portail est derrière un login Rails/Devise. Le script
demande le cookie de session ``_enki_session`` (jamais stocké, jamais affiché),
puis récupère lui-même le jeton CSRF.

Récupérer le cookie : ouvrir https://sibapublic.yourenki.com connecté, puis
DevTools → Application → Cookies → copier la valeur de ``_enki_session``.

Usage :
    uv run python scripts/fetch_enki.py                 # année en cours seulement
    uv run python scripts/fetch_enki.py --all           # 2014 → année en cours
    uv run python scripts/fetch_enki.py --years 2022 2024
    ENKI_SESSION=... uv run python scripts/fetch_enki.py --no-prompt

Les CSV atterrissent dans ``_data/enki/`` (non versionné).
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests

BASE = "https://sibapublic.yourenki.com"
REPORT_URL = f"{BASE}/reports/generic"
FORM_URL = f"{REPORT_URL}?project_id=2"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "_data" / "enki"

FIRST_YEAR = 2014  # 1re année avec des analyses (2012-2013 : aucune mesure)
DELAY = 5.0  # s entre deux requêtes : une année à la fois, sans bousculer le portail

# Corps du formulaire, repris tel quel d'une requête du navigateur. Les champs
# vides comptent (Rails les attend) : on ne garde que ce qui est nécessaire et
# on ne surcharge que le jeton et la fenêtre de dates. Les deux colonnes
# d'observation sont les analyses : observation_params_15_53 (entérocoques) et
# observation_params_14_53 (E. coli).
BODY_TEMPLATE = (
    "authenticity_token=&report_filters_form%5Bproject_ids%5D%5B%5D=&report_filters_form%5Bproject_ids%5D%5B%5D=2"
    "&report_filters_form%5Bwatershed%5D=&report_filters_form%5Bwaterbody%5D="
    "&report_filters_form%5Bsampling_point_justification_id%5D=&report_filters_form%5Bsampling_point_id%5D%5B%5D="
    "&leaflet-base-layers=on&report_filters_form%5Bperiods_type%5D=single&report_filters_form%5Bperiods_years%5D="
    "&report_filters_form%5Bsampling_start%5D=&report_filters_form%5Bsampling_end%5D="
    "&report_filters_form%5Bperiods%5D=&report_filters_form%5Bcontext_id%5D="
    "&report_filters_form%5Bsampling_objectives%5D%5B%5D=&report_filters_form%5Bprecipitation_type_id%5D%5B%5D="
    "&report_filters_form%5Bwind_type_id%5D%5B%5D=&report_filters_form%5Bwave_type_id%5D%5B%5D="
    "&report_filters_form%5Bsampling_protocol_id%5D%5B%5D=&report_filters_form%5Bsky_type_id%5D%5B%5D="
    "&report_filters_form%5Bwind_direction_type_id%5D%5B%5D=&report_filters_form%5Bobservation_depth_min%5D="
    "&report_filters_form%5Bobservation_depth_max%5D=&report_filters_form%5Bobservation_observers%5D%5B%5D="
    "&report_filters_form%5Bselected_columns%5D%5B%5D="
    "&report_filters_form%5Bselected_columns%5D%5B%5D=context_id"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=context_sampling_start_date"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=context_sampling_end_date"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=sampling_point_name"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=sampling_point_latitude"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=sampling_point_longitude"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=observer_name"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=observation_depth"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=context_sampling_start_time"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=context_sampling_end_time"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=waterbody_name"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=watershed_name"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=sampling_point_justification_value"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=sky_type_value"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=precipitation_type_value"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=wave_type_value"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=wind_type_value"
    "&report_filters_form%5Bselected_columns%5D%5B%5D=wind_direction_type_value"
    "&report_filters_form%5Bselected_obs_columns%5D%5B%5D="
    "&report_filters_form%5Bselected_obs_columns%5D%5B%5D=observation_params_15_53"
    "&report_filters_form%5Bselected_obs_columns%5D%5B%5D=observation_params_14_53"
    "&report_filters_form%5Bselected_ctx_columns%5D%5B%5D=&report_filters_form%5Btype%5D=export_csv"
    "&report_filters_form%5Bgroup_observers%5D=0&report_filters_form%5Bgroup_observers%5D=1"
    "&report_filters_form%5Bdisplay_codes%5D=0&report_filters_form%5Bdisplay_codes%5D=1"
    "&report_filters_form%5Bchart_logarithmic_y_axis%5D=0&report_filters_form%5Bchart_logarithmic_y_axis%5D=1"
    "&report_filters_form%5Bchart_logarithmic_x_axis%5D=0&report_filters_form%5Bchart_columns%5D%5B%5D="
    "&report_filters_form%5Bchart_columns%5D%5B%5D=observation_params_14_53"
    "&report_filters_form%5Bchart_parameter%5D=observation_params_15_53"
    "&report_filters_form%5Bchart_group_context%5D=0&report_filters_form%5Bchart_group_context%5D=1"
    "&report_filters_form%5Bcreate_report_template%5D=0&commit=Envoyer"
)


def read_session(prompt: bool) -> str:
    """Cookie depuis $ENKI_SESSION, sinon saisie masquée. Jamais journalisé."""
    cookie = os.environ.get("ENKI_SESSION", "").strip()
    if cookie:
        return cookie
    if not prompt:
        raise SystemExit(
            "Cookie absent : définir ENKI_SESSION ou retirer --no-prompt."
        )
    print(
        "Cookie de session Enki requis.\n"
        f"  1. se connecter sur {BASE}\n"
        "  2. DevTools → Application → Cookies → copier la valeur de « _enki_session »\n"
    )
    cookie = getpass.getpass("_enki_session (saisie masquée) : ").strip()
    if not cookie:
        raise SystemExit("Aucun cookie saisi.")
    return cookie


def _cookie_variants(cookie: str):
    """Le cookie tel que stocké est URL-encodé (``%2F``, ``%2B``…).

    DevTools affiche la version décodée quand « Show URL-decoded » est coché, et
    cette forme-là est refusée par le serveur. On essaie donc la valeur fournie
    puis son autre forme, plutôt que d'imposer le bon réglage de DevTools.
    """
    yield cookie
    alt = (
        urllib.parse.unquote(cookie)
        if "%" in cookie
        else urllib.parse.quote(cookie, safe="")
    )
    if alt != cookie:
        yield alt


def open_session(cookie: str) -> tuple[requests.Session, str]:
    """Ouvre une session authentifiée et renvoie (session, jeton CSRF).

    Le jeton utile est celui de la balise ``<meta name="csrf-token">`` : celui
    du champ caché ``authenticity_token`` du formulaire fait répondre 500.
    """
    for attempt, value in enumerate(_cookie_variants(cookie)):
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT})
        s.cookies.set("_enki_session", value, domain="sibapublic.yourenki.com")

        r = s.get(FORM_URL, timeout=60)
        r.raise_for_status()
        if "users/sign_in" in r.url:
            continue  # refusé : on tente l'autre encodage
        m = re.search(r'<meta name="csrf-token" content="([^"]+)"', r.text)
        if not m:
            raise SystemExit("Jeton CSRF introuvable dans la page du rapport.")
        if attempt:
            print("(cookie ré-encodé automatiquement)")
        return s, m.group(1)

    raise SystemExit(
        "Session refusée : redirection vers la page de connexion.\n"
        "  • le cookie a peut-être expiré — se reconnecter et en copier un nouveau ;\n"
        "  • vérifier d'avoir copié la valeur de « _enki_session » en entier "
        f"(≈470 caractères, reçu : {len(cookie)}) ;\n"
        "  • dans DevTools, décocher « Show URL-decoded » : la valeur doit\n"
        "    contenir des %2F / %2B, pas des / ni des +."
    )


def body_for(token: str, start: str, end: str) -> str:
    """Corps du formulaire pour une fenêtre [start, end] (dates ISO)."""
    periods = {
        "periods": [
            {"sampling_start": f"{start}T00:00:00.000Z",
             "sampling_end": f"{end}T00:00:00.000Z"}
        ]
    }
    overrides = {
        "authenticity_token": token,
        "report_filters_form[sampling_start]": start,
        "report_filters_form[sampling_end]": end,
        "report_filters_form[periods]": json.dumps(periods),
    }
    pairs = urllib.parse.parse_qsl(BODY_TEMPLATE, keep_blank_values=True)
    return urllib.parse.urlencode(
        [(k, overrides.get(k, v)) for k, v in pairs]
    )


def fetch_year(s: requests.Session, token: str, year: int) -> bytes:
    body = body_for(token, f"{year}-01-01", f"{year}-12-31")
    r = s.post(
        REPORT_URL, data=body, timeout=180,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": BASE, "Referer": FORM_URL,
        },
    )
    if r.status_code != 200:
        raise RuntimeError(f"{year} : HTTP {r.status_code} ({r.text[:120]!r})")
    if not r.content.startswith(b"ID,"):
        raise RuntimeError(
            f"{year} : réponse inattendue "
            f"({r.headers.get('Content-Type')}) — {r.text[:120]!r}"
        )
    return r.content


def _short(path: Path) -> str:
    """Chemin relatif au dépôt quand c'est possible, absolu sinon."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def count_rows(raw: bytes) -> int:
    """Lignes de données : on retire l'en-tête et la ligne d'unités."""
    lines = [ln for ln in raw.decode("utf-8", "replace").splitlines() if ln.strip()]
    return max(0, len(lines) - 2)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Récupère les analyses bactériologiques Enki, année par année."
    )
    ap.add_argument("--years", nargs=2, type=int, metavar=("DEBUT", "FIN"),
                    help="plage d'années explicite")
    ap.add_argument("--all", action="store_true",
                    help=f"tout l'historique ({FIRST_YEAR} → année en cours)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--no-prompt", action="store_true",
                    help="n'utiliser que $ENKI_SESSION, sans saisie interactive")
    args = ap.parse_args()

    this_year = dt.date.today().year
    if args.years:
        first, last = args.years
    elif args.all:
        first, last = FIRST_YEAR, this_year
    else:
        # Par défaut : rafraîchir l'année en cours, le cas courant. L'historique
        # complet ne bouge plus, il se récupère une fois avec --all.
        first, last = this_year, this_year
    if first > last:
        raise SystemExit("plage d'années invalide")

    s, token = open_session(read_session(prompt=not args.no_prompt))
    print(f"session OK, jeton CSRF récupéré\n")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    total, failed = 0, []
    for i, year in enumerate(range(first, last + 1)):
        try:
            raw = fetch_year(s, token, year)
        except RuntimeError as exc:
            print(f"  {year} : ÉCHEC — {exc}")
            failed.append(year)
        else:
            dest = args.out_dir / f"Export_siba_{year}.csv"
            dest.write_bytes(raw)
            n = count_rows(raw)
            total += n
            print(f"  {year} : {n:4} lignes → {_short(dest)}")
        if i < last - first:
            time.sleep(DELAY)

    print(f"\n{total} lignes au total dans {_short(args.out_dir)}")
    if failed:
        print(f"Années en échec : {failed} — relancer pour ces années.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    import duckdb
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from siba.data.config import DB_PATH
    from siba.paths import REPO_ROOT

    # Base locale construite depuis les classeurs SIBA (hors dépôt, _local/ ignoré).
    REFERE_DIR = REPO_ROOT / "_local" / "refere_from_Daniel_Lafon_20261017"
    REFERE_DB = REFERE_DIR / "refere.duckdb"

    # Une couleur par grandeur, la même dans tous les graphiques.
    C_STEP = "#eb6834"
    C_NAPPE = "#2a78d6"
    C_PLUIE = "#1baf7a"
    C_HC = "#e5484d"
    C_ENCRE = "#52514e"

    # Un jour est « sec » si le cumul de pluie sur 3 jours reste sous ce seuil.
    PLUIE_SEC_MM = 2.0
    return (
        C_ENCRE,
        C_HC,
        C_NAPPE,
        C_PLUIE,
        C_STEP,
        DB_PATH,
        PLUIE_SEC_MM,
        REFERE_DB,
        REFERE_DIR,
        duckdb,
        mdates,
        mo,
        np,
        pd,
        plt,
    )


@app.cell
def _(mo):
    mo.md("""
    # STEP de Biganos et nappe

    Débit d'eau brute entrant à la STEP de Biganos (m³/j, classeur SIBA 2025) face
    à la profondeur de la nappe. Par défaut, le piézomètre de Blagon (Lanton, ADES
    [08262X0023/F](https://ades.eaufrance.fr/Fiche/PointEau?code=08262X0023/F)) ;
    le sélecteur ci-dessous le remplace dans tout le notebook par Piraillan
    (Lège), Biganos (Canauley, même nappe que Blagon) ou La Teste (rive sud,
    hors du bassin de collecte de la STEP : référence régionale).

    Si les eaux claires parasites entrent dans le réseau EU quand la nappe monte,
    le débit de la STEP doit suivre la nappe, et pas seulement la pluie du jour.
    La pluie affichée est celle du pluviomètre de la STEP.
    """)
    return


@app.cell
def _(mo):
    nappe_ref = mo.ui.dropdown(
        options=["Blagon", "Piraillan", "Biganos", "La_Teste"],
        value="Blagon",
        label="Piézomètre",
    )
    nappe_ref
    return (nappe_ref,)


@app.cell
def _(DB_PATH, REFERE_DB, REFERE_DIR, duckdb, mo, nappe_ref):
    mo.stop(
        not REFERE_DB.exists(),
        mo.md(
            f"**Base STEP introuvable** : `{REFERE_DB}`.\n\n"
            f"La construire : `cd {REFERE_DIR} && duckdb refere.duckdb < load.sql`"
        ),
    )
    mo.stop(
        not DB_PATH.exists(),
        mo.md(f"**Base introuvable** : `{DB_PATH}`. Lancer `make rebuild`."),
    )

    _con = duckdb.connect(str(REFERE_DB), read_only=True)
    try:
        _con.execute(f"ATTACH '{DB_PATH}' AS siba (READ_ONLY)")
        # Jointure à gauche sur la STEP : la période est celle du classeur.
        # nappe_ref.value vient d'une liste fermée, pas d'une saisie libre.
        df_all = _con.execute(
            f"""
            SELECT s.date,
                   s.q_eau_brute_m3j,
                   s.pluie_mm,
                   sum(s.pluie_mm) OVER (
                       ORDER BY s.date ROWS 2 PRECEDING
                   )                   AS pluie_3j_mm,
                   n."{nappe_ref.value}" AS nappe_m
            FROM step_biganos_jour s
            LEFT JOIN siba.nappe_pluie_daily n USING (date)
            ORDER BY s.date
            """
        ).df()
        # Historique complet de la nappe (2015+) avec le drapeau HC.
        nappe_hist = _con.execute(
            f'SELECT "date", "{nappe_ref.value}" AS nappe_m, in_hc '
            "FROM siba.v_nappe_pluie_events ORDER BY \"date\""
        ).df()
        hc = _con.execute(
            "SELECT start_date, end_date, label FROM siba.hc_period ORDER BY start_date"
        ).df()
    finally:
        _con.close()
    return df_all, hc, nappe_hist


@app.cell
def _(df_all, mo):
    periode = mo.ui.date_range(
        start=df_all["date"].min().date(),
        stop=df_all["date"].max().date(),
        label="Période",
    )
    lissage = mo.ui.slider(
        start=1, stop=15, value=1, step=2,
        label="Moyenne glissante du débit (jours)", show_value=True,
    )
    mo.hstack([periode, lissage], justify="start", gap=2)
    return lissage, periode


@app.cell
def _(df_all, lissage, periode):
    _d0, _d1 = periode.value
    df = df_all[
        (df_all["date"].dt.date >= _d0) & (df_all["date"].dt.date <= _d1)
    ].set_index("date")
    # Centrée : un pic de débit reste aligné sur la date de l'épisode.
    df = df.assign(
        q_lisse=df["q_eau_brute_m3j"]
        .rolling(lissage.value, center=True, min_periods=1)
        .mean()
    )
    return (df,)


@app.cell
def _(df, mo):
    _q = df["q_eau_brute_m3j"]
    _n = df["nappe_m"].dropna()
    # Spearman : la relation débit / nappe n'a aucune raison d'être linéaire.
    _rho = df["q_eau_brute_m3j"].corr(df["nappe_m"], method="spearman")
    mo.hstack(
        [
            mo.stat(
                value=f"{_q.median():,.0f} m³/j".replace(",", " "),
                label="Débit médian",
                caption=f"{len(_q)} jours",
            ),
            mo.stat(
                value=f"{_q.max():,.0f} m³/j".replace(",", " "),
                label="Débit maximal",
                caption=str(_q.idxmax().date()),
            ),
            mo.stat(
                value=f"{_n.min():.2f} m" if len(_n) else "—",
                label="Nappe la plus haute",
                caption=str(_n.idxmin().date()) if len(_n) else "pas de mesure",
            ),
            mo.stat(
                value=f"{_rho:+.2f}" if len(_n) > 2 else "—",
                label="Spearman débit / profondeur",
                caption="négatif = débit fort quand la nappe est haute",
            ),
        ],
        justify="start",
        gap=2,
    )
    return


@app.cell
def _(C_NAPPE, C_PLUIE, C_STEP, df, lissage, mdates, nappe_ref, plt):
    def _plot():
        fig, (ax_q, ax_n, ax_p) = plt.subplots(
            3, 1, figsize=(11, 7.5), sharex=True, constrained_layout=True,
            gridspec_kw={"height_ratios": [2, 2, 1]},
        )

        # Débit STEP : brut en trait fin, lissé par-dessus si demandé.
        if lissage.value > 1:
            ax_q.plot(df.index, df["q_eau_brute_m3j"], color=C_STEP,
                      linewidth=0.8, alpha=0.35)
        ax_q.plot(df.index, df["q_lisse"], color=C_STEP, linewidth=2)
        _titre_q = "Débit d'eau brute STEP Biganos (m³/j)"
        if lissage.value > 1:
            _titre_q += f" — moyenne glissante {lissage.value} j"
        ax_q.set_title(_titre_q, loc="left", fontsize=11)
        ax_q.set_ylim(bottom=0)
        ax_q.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " "))
        )

        # Nappe : profondeur, axe inversé (vers le haut = nappe plus haute).
        _n = df["nappe_m"].dropna()
        ax_n.plot(_n.index, _n.values, color=C_NAPPE, linewidth=2)
        ax_n.invert_yaxis()
        ax_n.set_title(f"Profondeur de la nappe à {nappe_ref.value} (m, axe inversé)",
                       loc="left", fontsize=11)

        # Pluie journalière au pluviomètre de la STEP.
        ax_p.bar(df.index, df["pluie_mm"], width=0.8, color=C_PLUIE)
        ax_p.set_title("Pluie journalière à la STEP (mm)", loc="left", fontsize=11)
        ax_p.set_ylim(bottom=0)

        for ax in (ax_q, ax_n, ax_p):
            ax.grid(axis="y", color="#e5e4e0", linewidth=0.8)
            ax.set_axisbelow(True)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
        ax_p.xaxis.set_major_locator(mdates.MonthLocator())
        ax_p.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        return fig

    _plot()
    return


@app.cell
def _(mo):
    mo.md("""
    ## Débit en fonction de la nappe

    Un point par jour. Les jours de forte pluie (≥ 10 mm) sont cerclés : ils
    montrent la part du débit due au ruissellement immédiat, au-dessus du niveau
    de base imposé par la nappe.

    La courbe noire est la courbe en S ajustée sur tous les jours (voir la
    section suivante). Les points gris reliés sont les débits médians des
    jours secs (cumul de pluie sur 3 jours inférieur à 2 mm), par tranche de
    10 cm de profondeur : ils montrent l'effet de la nappe seule, sans la
    pluie. Les deux verticales marquent le début de la hausse et le plafond.
    """)
    return


@app.cell
def _(PLUIE_SEC_MM, df, np):
    # Jours secs : le ruissellement de la veille ou de l'avant-veille est exclu.
    sec = df.dropna(subset=["nappe_m"])
    sec = sec[sec["pluie_3j_mm"] < PLUIE_SEC_MM]

    # Débit médian par tranche de 10 cm de profondeur.
    _t = (sec["nappe_m"] / 0.1).round() * 0.1
    tranches = (
        sec.groupby(_t)["q_eau_brute_m3j"]
        .agg(debit_median_m3j="median", jours="size")
        .reset_index()
        .rename(columns={"nappe_m": "profondeur_m"})
    )

    # Courbe en S (logistique) ajustée sur tous les jours :
    #   Q(z) = Q_bas + (Q_haut − Q_bas) × f(z),  f(z) = 1 / (1 + exp((z − z_mi) / e))
    # z_mi = profondeur où le débit est à mi-chemin entre les deux paliers,
    # e = largeur de la transition. Tous les jours, pas seulement les secs :
    # aucun jour sec n'atteint le palier haut, il serait sinon extrapolé.
    # Pour z_mi et e fixés, Q est linéaire en (Q_bas, Q_haut) : balayage de
    # (z_mi, e) et moindres carrés pour les deux paliers.
    courbe = None
    _d = df.dropna(subset=["nappe_m"])
    _z = _d["nappe_m"].to_numpy()
    _q = _d["q_eau_brute_m3j"].to_numpy()
    if len(_d) >= 30 and _z.max() - _z.min() > 0.3:
        _best = None
        # Grille de z_mi calée sur la plage observée (au pas de 10 cm), pour
        # que la courbe s'ajuste quel que soit le piézomètre choisi.
        _lo, _hi = np.floor(_z.min() * 10) / 10, np.ceil(_z.max() * 10) / 10
        for _zm in np.arange(_lo, _hi, 0.005):
            for _e in np.arange(0.02, 0.30, 0.005):
                _f = 1 / (1 + np.exp((_z - _zm) / _e))
                _X = np.c_[1 - _f, _f]
                _coef, *_ = np.linalg.lstsq(_X, _q, rcond=None)
                _sse = float(((_q - _X @ _coef) ** 2).sum())
                if _best is None or _sse < _best[0]:
                    _best = (_sse, _zm, _e, _coef)
        _sse, _zm, _e, (_q_bas, _q_haut) = _best
        # Seuils à 10 % et 90 % de la transition : z_mi ± e × ln 9.
        _k = _e * np.log(9)
        courbe = {
            "z_mi": float(_zm),
            "e": float(_e),
            "q_bas": float(_q_bas),
            "q_haut": float(_q_haut),
            "z_debut": float(_zm + _k),
            "z_plafond": float(_zm - _k),
            # Pente maximale (au point milieu), ramenée à 10 cm de remontée.
            "pente_max_10cm": float((_q_haut - _q_bas) / (4 * _e) / 10),
            "r2": 1 - _sse / float(((_q - _q.mean()) ** 2).sum()),
            "n": len(_d),
            # Jours observés au-delà du plafond, et débit maximal mesuré :
            # sans eux, le palier haut est une extrapolation.
            "n_plafond": int((_z < _zm - _k).sum()),
            "q_max_obs": float(_q.max()),
        }

    def debit_modele(z):
        """Débit prédit par la courbe en S pour une profondeur z (m)."""
        f = 1 / (1 + np.exp((z - courbe["z_mi"]) / courbe["e"]))
        return courbe["q_bas"] + (courbe["q_haut"] - courbe["q_bas"]) * f

    return courbe, debit_modele, tranches


@app.cell
def _(
    C_ENCRE,
    C_HC,
    C_STEP,
    courbe,
    debit_modele,
    df,
    nappe_ref,
    np,
    plt,
    tranches,
):
    def _scatter():
        d = df.dropna(subset=["nappe_m"])
        fig, ax = plt.subplots(figsize=(8, 5.5), constrained_layout=True)
        ax.scatter(d["nappe_m"], d["q_eau_brute_m3j"], s=22, color=C_STEP,
                   alpha=0.6, edgecolor="white", linewidth=0.5,
                   label="Jour")
        _pluie = d[d["pluie_mm"] >= 10]
        ax.scatter(_pluie["nappe_m"], _pluie["q_eau_brute_m3j"], s=70,
                   facecolor="none", edgecolor="#0b0b0b", linewidth=1,
                   label="Pluie ≥ 10 mm")
        ax.plot(tranches["profondeur_m"], tranches["debit_median_m3j"],
                color=C_ENCRE, alpha=0.6, linewidth=1, marker="o", markersize=4,
                label="Médiane des jours secs (10 cm)")
        if courbe is not None:
            _zz = np.linspace(d["nappe_m"].min(), d["nappe_m"].max(), 200)
            ax.plot(_zz, debit_modele(_zz), color="#0b0b0b", linewidth=2.5,
                    label="Courbe en S ajustée")
            for _z, _nom, _c in (
                (courbe["z_debut"], "début de hausse", C_ENCRE),
                (courbe["z_plafond"], "plafond", C_HC),
            ):
                ax.axvline(_z, color=_c, linestyle="--", linewidth=1)
                ax.annotate(f"{_nom}\n{_z:.2f} m", (_z, 1000), xytext=(4, 0),
                            textcoords="offset points", fontsize=9, color=C_ENCRE)
        ax.invert_xaxis()  # vers la droite = nappe plus haute
        ax.set_xlabel(f"Profondeur de la nappe à {nappe_ref.value} (m) — nappe plus haute →")
        ax.set_ylabel("Débit d'eau brute STEP Biganos (m³/j)")
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " "))
        )
        ax.grid(color="#e5e4e0", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.legend(loc="upper left", fontsize=9, frameon=False)
        return fig

    _scatter()
    return


@app.cell
def _(courbe, debit_modele, mo, nappe_ref, tranches):
    def _fmt(v, arrondi=100):
        """Débit arrondi (à la centaine par défaut), espace des milliers."""
        return f"{round(v / arrondi) * arrondi:,.0f}".replace(",", " ")

    def _m(z):
        """Profondeur en mètres, virgule décimale."""
        return f"{z:.2f}".replace(".", ",")

    mo.stop(
        courbe is None,
        mo.md(
            "## Une relation en S, pas une droite\n\n"
            "Pas assez de jours (ou d'amplitude de nappe) sur la période "
            "choisie pour ajuster la courbe. Élargir la période."
        ),
    )
    _c = courbe

    # Palier haut : observé seulement si assez de jours dépassent le plafond.
    if _c["n_plafond"] >= 5:
        _point3 = f"""3. **Palier haut** : quand la nappe est à moins de
       **{_m(_c["z_plafond"])} m** de profondeur, le débit cesse d'augmenter
       et plafonne autour de **{_fmt(_c["q_haut"])} m³/j**. Ce palier
       ressemble à une limite de capacité hydraulique (STEP ou transfert en
       amont). Si c'est bien le cas, le surplus n'arrive plus à la STEP et doit
       sortir ailleurs : c'est le mécanisme attendu des débordements « hors de
       contrôle »."""
    else:
        _jours = (
            "Aucun jour de la période n'est"
            if _c["n_plafond"] == 0
            else f"Seuls {_c['n_plafond']} jours de la période sont"
        )
        _point3 = f"""3. **Palier haut : non observé avec ce piézomètre.** {_jours}
       à moins de {_m(_c["z_plafond"])} m de profondeur. Le palier haut de la courbe
       ({_fmt(_c["q_haut"])} m³/j) est une extrapolation, au-dessus du débit
       maximal mesuré ({_fmt(_c["q_max_obs"])} m³/j) : la courbe ne dit rien
       de fiable sur un plafond. Avec Blagon, ce palier est bien observé."""

    # Débit prédit tous les 10 cm, des deux côtés de la transition, pour
    # montrer que la hausse s'accélère puis s'arrête. Tableau construit sans
    # indentation : il passe dans son propre mo.md.
    _haut = round(_c["z_debut"] + 0.15, 1)
    _bas = round(_c["z_plafond"] - 0.15, 1)
    _paliers = [_haut - 0.1 * i for i in range(round((_haut - _bas) / 0.1) + 1)]
    _tableau = "| Profondeur nappe | Débit STEP prédit |\n|---|---|\n" + "\n".join(
        f"| {_m(z)[:-1]} m | {_fmt(debit_modele(z))} m³/j |" for z in _paliers
    )

    _phases = mo.md(f"""
    ## Une relation en S, pas une droite

    Le débit de la STEP n'est **pas proportionnel** à la hauteur de la nappe.
    Il suit une courbe en S, en trois phases :

    1. **Palier bas** : tant que la nappe de {nappe_ref.value} est plus profonde que
       **{_m(_c["z_debut"])} m**, le débit reste stable autour de
       **{_fmt(_c["q_bas"])} m³/j**. La nappe ne semble pas atteindre le réseau.
    2. **Montée de plus en plus raide** entre {_m(_c["z_debut"])} m et
       {_m(_c["z_plafond"])} m. Chaque centimètre de remontée ajoute plus de
       débit que le précédent. Au point le plus raide, vers
       {_m(_c["z_mi"])} m, 10 cm de remontée ajoutent environ
       **{_fmt(_c["pente_max_10cm"])} m³/j**. Une explication plausible : plus
       la nappe monte, plus la longueur de canalisations noyées augmente, et
       avec elle le nombre de points d'entrée d'eau claire parasite.
    {_point3}
    """)

    _lecture = mo.md(f"""
    **Comment lire les seuils.** Le « début de hausse » est la profondeur où
    le débit a parcouru 10 % du chemin entre les deux paliers ; le « plafond »,
    celle où il en a parcouru 90 %. Ce sont des repères commodes, pas des
    ruptures nettes : la transition est progressive.

    **Qualité de l'ajustement.** La courbe explique {_c["r2"] * 100:.0f} % des
    variations du débit (R² = {_m(_c["r2"])}, {_c["n"]} jours). Le reste vient
    surtout de la pluie du jour, qui ajoute du ruissellement par-dessus le
    niveau fixé par la nappe. La courbe, ses paliers et ses seuils sont
    recalculés à chaque changement de période.
    """)

    mo.vstack([
        _phases,
        mo.md(_tableau),
        _lecture,
        mo.md("**Débit médian des jours secs par tranche de profondeur**"),
        mo.ui.table(tranches.round(2), page_size=25, selection=None),
    ])
    return


@app.cell
def _(PLUIE_SEC_MM, courbe, df, mo, np, pd):
    mo.stop(courbe is None)

    # Trois zones délimitées par les seuils de la courbe en S.
    _z1, _z2 = courbe["z_debut"], courbe["z_plafond"]
    ZONES = [
        f"Palier bas (> {_z1:.2f} m)".replace(".", ","),
        f"Transition ({_z2:.2f} – {_z1:.2f} m)".replace(".", ","),
        f"Plafond (< {_z2:.2f} m)".replace(".", ","),
    ]
    zdf = df.dropna(subset=["nappe_m"]).copy()
    zdf["zone"] = np.select(
        [zdf["nappe_m"] > _z1, zdf["nappe_m"] > _z2], ZONES[:2], ZONES[2]
    )

    def _stats_zone(g, rng):
        """Spearman, IC 95 % bootstrap et pente de Theil-Sen pour une zone."""
        n = len(g)
        ligne = {"jours": n, "etendue_prof_m": None, "spearman": None,
                 "ic95_bas": None, "ic95_haut": None, "pente_m3j_10cm": None}
        if n < 5:
            return ligne
        z = g["nappe_m"].to_numpy()
        q = g["q_eau_brute_m3j"].to_numpy()
        # Spearman = Pearson sur les rangs (rangs moyens en cas d'égalité).
        rz = pd.Series(z).rank().to_numpy()
        rq = pd.Series(q).rank().to_numpy()
        rho = float(np.corrcoef(rz, rq)[0, 1])
        # Bootstrap : on retire des jours au hasard (avec remise) 1 000 fois.
        _boot = []
        for _ in range(1000):
            i = rng.integers(0, n, n)
            a = pd.Series(z[i]).rank().to_numpy()
            b = pd.Series(q[i]).rank().to_numpy()
            if a.std() > 0 and b.std() > 0:
                _boot.append(np.corrcoef(a, b)[0, 1])
        lo, hi = np.percentile(_boot, [2.5, 97.5])
        # Theil-Sen : médiane des pentes entre toutes les paires de jours,
        # peu sensible aux jours de forte pluie. Signe inversé et ramené à
        # 10 cm : débit gagné quand la nappe remonte de 10 cm.
        ii, jj = np.triu_indices(n, 1)
        m = z[ii] != z[jj]
        pente = float(np.median((q[ii][m] - q[jj][m]) / (z[ii][m] - z[jj][m]))) * -0.1
        ligne.update({
            "etendue_prof_m": round(float(z.max() - z.min()), 2),
            "spearman": round(rho, 2),
            "ic95_bas": round(float(lo), 2),
            "ic95_haut": round(float(hi), 2),
            "pente_m3j_10cm": round(pente, -1),
        })
        return ligne

    def _tableau(sous_ensemble):
        rng = np.random.default_rng(0)  # graine fixe : résultats reproductibles
        lignes = []
        for zone in ZONES:
            g = sous_ensemble[sous_ensemble["zone"] == zone]
            lignes.append({"zone": zone, **_stats_zone(g, rng)})
        return pd.DataFrame(lignes)

    stats_zones = _tableau(zdf)
    stats_zones_sec = _tableau(zdf[zdf["pluie_3j_mm"] < PLUIE_SEC_MM])
    return ZONES, stats_zones, stats_zones_sec, zdf


@app.cell
def _(C_STEP, ZONES, nappe_ref, plt, stats_zones, zdf):
    def _petits_multiples():
        # Un panneau par zone, même échelle de débit : on compare les pentes.
        fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharey=True,
                                 constrained_layout=True)
        for ax, zone in zip(axes, ZONES):
            g = zdf[zdf["zone"] == zone]
            ax.scatter(g["nappe_m"], g["q_eau_brute_m3j"], s=18, color=C_STEP,
                       alpha=0.6, edgecolor="white", linewidth=0.5)
            _rho = stats_zones.loc[stats_zones["zone"] == zone, "spearman"].iloc[0]
            _txt = "—" if _rho is None else f"{_rho:+.2f}".replace(".", ",")
            ax.set_title(f"{zone}\nSpearman = {_txt} ({len(g)} jours)",
                         loc="left", fontsize=10)
            ax.invert_xaxis()
            ax.set_xlabel(f"Profondeur nappe {nappe_ref.value} (m)")
            ax.grid(color="#e5e4e0", linewidth=0.8)
            ax.set_axisbelow(True)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
        axes[0].set_ylabel("Débit STEP Biganos (m³/j)")
        axes[0].set_ylim(bottom=0)
        axes[0].yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " "))
        )
        return fig

    _petits_multiples()
    return


@app.cell
def _(ZONES, mo, stats_zones, stats_zones_sec, zdf):
    def _r(v):
        # v != v : NaN (zone sans assez de jours).
        return "—" if v is None or v != v else f"{v:+.2f}".replace(".", ",")

    def _ligne(t, zone):
        return t[t["zone"] == zone].iloc[0]

    _bas, _tr, _pl = (_ligne(stats_zones, z) for z in ZONES)
    _tr_sec = _ligne(stats_zones_sec, ZONES[1])

    # Jours au plafond : débit, profondeur et pluie, pour l'exemple concret.
    _plafond = (
        zdf[zdf["zone"] == ZONES[2]]
        .reset_index()[["date", "nappe_m", "q_eau_brute_m3j", "pluie_mm"]]
        .assign(date=lambda t: t["date"].dt.date)
        .rename(columns={"nappe_m": "profondeur_m", "q_eau_brute_m3j": "debit_m3j"})
    )

    def _fmt(v):
        return f"{v:,.0f}".replace(",", " ")

    def _m(v, d=2):
        """Nombre à virgule décimale."""
        return f"{v:.{d}f}".replace(".", ",")

    if len(_plafond):
        _pluvieux = _plafond.loc[_plafond["pluie_mm"].idxmax()]
        _jour = _pluvieux["date"].strftime("%d/%m/%Y")
        _texte_plafond = f"""
    Sur les {len(_plafond)} jours au plafond, le débit reste entre
    **{_fmt(_plafond["debit_m3j"].min())} et {_fmt(_plafond["debit_m3j"].max())} m³/j**,
    alors que la nappe varie de {_m(_plafond["profondeur_m"].max())} m à
    {_m(_plafond["profondeur_m"].min())} m. Le
    **{_jour}** est le cas le plus parlant :
    {_m(_pluvieux["pluie_mm"], 1)} mm de pluie, nappe à
    {_m(_pluvieux["profondeur_m"])} m, et pourtant un débit de
    {_fmt(_pluvieux["debit_m3j"])} m³/j seulement, au niveau des jours sans
    pluie. Ni la nappe ni la pluie ne font plus monter le débit : c'est la
    signature d'une limite de capacité. Le surplus continue sans doute
    d'entrer dans le réseau, mais il ne parvient plus à la STEP et part
    ailleurs (bassins de délestage, débordements).
    """
    else:
        _texte_plafond = "\n    Aucun jour au plafond sur la période choisie.\n    "

    # Palier bas : le texte suit le coefficient observé (intervalle contenant
    # zéro = aucune relation), car il change selon le piézomètre choisi.
    _ic = (_bas["ic95_bas"], _bas["ic95_haut"])
    if any(v is None or v != v for v in _ic) or _ic[0] <= 0 <= _ic[1]:
        _point1_zone = f"""1. **Palier bas : aucune relation** (Spearman {_r(_bas["spearman"])},
       intervalle [{_r(_bas["ic95_bas"])} ; {_r(_bas["ic95_haut"])}]).
       La nappe y varie pourtant sur {_m(_bas["etendue_prof_m"])} m :
       l'absence de lien ne vient pas d'un manque de variation. Le débit varie
       bien dans cette zone, mais sous l'effet de la pluie."""
    else:
        _point1_zone = f"""1. **Palier bas : relation faible mais réelle** (Spearman
       {_r(_bas["spearman"])}, intervalle [{_r(_bas["ic95_bas"])} ;
       {_r(_bas["ic95_haut"])}], qui ne contient pas zéro). Avec ce
       piézomètre, le palier bas n'est pas tout à fait plat : la séparation
       entre les zones est moins nette qu'avec Blagon."""
    if _pl["jours"] >= 5:
        _point3_zone = f"""3. **Plafond : plus de relation mesurable** (Spearman
       {_r(_pl["spearman"])}, intervalle [{_r(_pl["ic95_bas"])} ;
       {_r(_pl["ic95_haut"])}], qui contient zéro). Trop peu de jours pour un
       coefficient précis ; l'argument tient surtout à la stabilité du débit."""
    else:
        _point3_zone = f"""3. **Plafond : pas assez de jours** ({_pl["jours"]}) dans cette
       zone pour calculer une corrélation avec ce piézomètre."""

    mo.vstack([
        mo.md(f"""
    ## La corrélation dans chaque zone

    Hypothèse : la nappe n'influence le débit que dans la zone de transition.

    - **Palier bas** : les canalisations EU sont hors de la nappe, le débit
      ne dépend pas de sa hauteur. Corrélation attendue : nulle.
    - **Transition** : la nappe noie une part croissante du réseau, le débit
      la suit. Corrélation attendue : maximale.
    - **Plafond** : le débit arrivant à la STEP est bloqué, il ne peut plus
      suivre la nappe. Corrélation attendue : nulle.

    Pour chaque zone : le coefficient de Spearman, son intervalle de
    confiance à 95 % (bootstrap, 1 000 tirages de jours avec remise), et la
    pente de Theil-Sen (médiane des pentes entre toutes les paires de jours,
    peu sensible aux jours de forte pluie), exprimée en m³/j gagnés pour
    10 cm de remontée de la nappe. Rappel : le coefficient est négatif quand
    le débit augmente avec la remontée, parce qu'on le calcule sur une
    profondeur.
    """),
        mo.md("**Tous les jours**"),
        mo.ui.table(stats_zones, selection=None),
        mo.md("**Jours secs seulement** (cumul de pluie sur 3 jours < 2 mm)"),
        mo.ui.table(stats_zones_sec, selection=None),
        mo.md(f"""
    **Lecture.**

    {_point1_zone}
    2. **Transition : relation forte** (Spearman {_r(_tr["spearman"])} sur
       tous les jours, **{_r(_tr_sec["spearman"])} sur les jours secs**).
       Sans la pluie, le lien est encore plus net : c'est bien la nappe qui
       pilote le débit dans cette zone. Environ
       **{_fmt(_tr["pente_m3j_10cm"])} m³/j** de plus pour 10 cm de remontée.
    {_point3_zone}
    """),
        mo.md(_texte_plafond),
        mo.md("**Jours au plafond**"),
        mo.ui.table(_plafond.round(2), selection=None),
        mo.md("""
    **Limites.** Les zones sont délimitées par la courbe en S ajustée sur
    ces mêmes données, conçue pour trouver des paliers plats : le résultat
    est en partie circulaire. Une autre année de débits STEP permettrait de
    le vérifier de façon indépendante.
    """),
    ])
    return


@app.cell
def _(mo, nappe_ref):
    mo.md(f"""
    ## La nappe pendant les épisodes HC (2015–2026)

    Les données de la STEP ne couvrent que 2025, mais la nappe de {nappe_ref.value} et
    les épisodes « hors de contrôle » du réseau EU remontent à 2015. Si le
    plafond de débit explique les débordements, les épisodes HC passés doivent
    tomber quand la nappe atteint la zone du plafond. Les bandes rouges
    marquent les épisodes HC ; les deux lignes pointillées reprennent les
    seuils de la courbe en S.
    """)
    return


@app.cell
def _(C_ENCRE, C_HC, C_NAPPE, courbe, hc, mdates, nappe_hist, nappe_ref, plt):
    def _historique():
        fig, ax = plt.subplots(figsize=(11, 4), constrained_layout=True)
        for i, (_, ev) in enumerate(hc.iterrows()):
            ax.axvspan(ev["start_date"], ev["end_date"], color=C_HC, alpha=0.18,
                       linewidth=0, label="Épisode HC" if i == 0 else None)
        _n = nappe_hist.dropna(subset=["nappe_m"])
        ax.plot(_n["date"], _n["nappe_m"], color=C_NAPPE, linewidth=1.2,
                label=f"Profondeur nappe {nappe_ref.value}")
        if courbe is not None:
            ax.axhline(courbe["z_debut"], color=C_ENCRE, linestyle="--", linewidth=1,
                       label=f"Début de hausse du débit ({courbe['z_debut']:.2f} m)")
            ax.axhline(courbe["z_plafond"], color=C_HC, linestyle="--", linewidth=1,
                       label=f"Plafond du débit ({courbe['z_plafond']:.2f} m)")
        ax.invert_yaxis()
        ax.set_title(f"Profondeur de la nappe à {nappe_ref.value} (m, axe inversé) et épisodes HC",
                     loc="left", fontsize=11)
        ax.set_xlim(_n["date"].min(), _n["date"].max())
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.grid(axis="y", color="#e5e4e0", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=9,
                  frameon=False, ncol=4)
        return fig

    _historique()
    return


@app.cell
def _(DB_PATH, courbe, duckdb, mo, nappe_ref):
    mo.stop(
        courbe is None,
        mo.md("Seuils indisponibles : élargir la période pour ajuster la courbe."),
    )
    _z_debut = round(courbe["z_debut"], 2)
    _z_plafond = round(courbe["z_plafond"], 2)
    # Colonne choisie, entre guillemets (liste fermée, pas de saisie libre).
    _c = f'"{nappe_ref.value}"'
    _con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        _par_episode = _con.execute(
            f"""
            SELECT h.label                    AS episode,
                   count(v.{_c})            AS jours,
                   round(min(v.{_c}), 2)    AS prof_min_m,
                   round(median(v.{_c}), 2) AS prof_mediane_m,
                   round(max(v.{_c}), 2)    AS prof_max_m
            FROM hc_period h
            JOIN v_nappe_pluie_events v ON v.date BETWEEN h.start_date AND h.end_date
            GROUP BY h.label, h.start_date
            ORDER BY h.start_date
            """
        ).df()
        _hc_vs_hors = _con.execute(
            f"""
            SELECT CASE WHEN in_hc THEN 'Pendant HC' ELSE 'Hors HC' END AS periode,
                   count(*)                                   AS jours,
                   round(median({_c}), 2)                   AS prof_mediane_m,
                   round(100 * avg(({_c} < ?)::INT))        AS pct_jours_zone_hausse,
                   round(100 * avg(({_c} < ?)::INT))        AS pct_jours_zone_plafond
            FROM v_nappe_pluie_events
            WHERE {_c} IS NOT NULL
            GROUP BY in_hc
            ORDER BY in_hc DESC
            """,
            [_z_debut, _z_plafond],
        ).df()
        _par_annee = _con.execute(
            f"""
            SELECT year(date)                       AS annee,
                   count(*) FILTER ({_c} < ?)     AS jours_zone_hausse,
                   count(*) FILTER ({_c} < ?)     AS jours_zone_plafond,
                   count(*) FILTER (in_hc)        AS jours_hc,
                   round(min({_c}), 2)            AS prof_min_m
            FROM v_nappe_pluie_events
            GROUP BY annee
            ORDER BY annee
            """,
            [_z_debut, _z_plafond],
        ).df()
    finally:
        _con.close()

    mo.vstack([
        mo.md("**Pendant et hors épisodes HC** (une profondeur plus faible signifie une nappe plus haute)"),
        mo.ui.table(_hc_vs_hors, selection=None),
        mo.md(f"""
    Pendant les épisodes HC, la profondeur médiane est de
    **{str(_hc_vs_hors.iloc[0]["prof_mediane_m"]).replace(".", ",")} m**. La nappe est dans la
    zone du plafond de débit (à moins de {str(_z_plafond).replace(".", ",")} m de profondeur)
    **{_hc_vs_hors.iloc[0]["pct_jours_zone_plafond"]:.0f} %** du temps, contre
    **{_hc_vs_hors.iloc[1]["pct_jours_zone_plafond"]:.0f} %** hors épisodes.
    Elle est dans la zone de hausse (à moins de {str(_z_debut).replace(".", ",")} m)
    **{_hc_vs_hors.iloc[0]["pct_jours_zone_hausse"]:.0f} %** du temps pendant
    les épisodes, contre **{_hc_vs_hors.iloc[1]["pct_jours_zone_hausse"]:.0f} %**
    hors épisodes.
    """),
        mo.md("**Profondeur de la nappe pendant chaque épisode HC**"),
        mo.ui.table(_par_episode, selection=None),
        mo.md("**Bilan annuel**"),
        mo.ui.table(_par_annee, selection=None, page_size=20),
    ])
    return


@app.cell
def _(DB_PATH, REFERE_DB, duckdb, mo):
    mo.stop(not REFERE_DB.exists() or not DB_PATH.exists())
    _con = duckdb.connect(str(REFERE_DB), read_only=True)
    try:
        _con.execute(f"ATTACH '{DB_PATH}' AS siba (READ_ONLY)")
        # Les quatre piézomètres de nappe libre, sur la période de la STEP.
        piezos_step = _con.execute(
            """
            SELECT s.date,
                   s.q_eau_brute_m3j,
                   sum(s.pluie_mm) OVER (
                       ORDER BY s.date ROWS 2 PRECEDING
                   ) AS pluie_3j_mm,
                   n."Blagon", n."Piraillan", n."Biganos", n."La_Teste"
            FROM step_biganos_jour s
            LEFT JOIN siba.nappe_pluie_daily n USING (date)
            ORDER BY s.date
            """
        ).df()
    finally:
        _con.close()
    return (piezos_step,)


@app.cell
def _(PLUIE_SEC_MM, np, pd, piezos_step):
    # Même courbe en S que pour Blagon, mais la grille de (z_mi, e) suit la
    # plage de profondeur de chaque piézomètre : Biganos et La Teste ne sont
    # pas entre 1 et 2 m.
    def _r2_courbe_s(_z, _q):
        _lo, _hi = np.quantile(_z, [0.02, 0.98])
        _sse_min = np.inf
        for _zm in np.linspace(_lo, _hi, 120):
            for _e in np.linspace(0.01, 0.3, 60) * (_hi - _lo):
                _f = 1 / (1 + np.exp((_z - _zm) / _e))
                _X = np.c_[1 - _f, _f]
                _coef, *_ = np.linalg.lstsq(_X, _q, rcond=None)
                _sse_min = min(_sse_min, float(((_X @ _coef - _q) ** 2).sum()))
        return 1 - _sse_min / float(((_q - _q.mean()) ** 2).sum())

    _lignes = []
    for _col in ["Blagon", "Piraillan", "Biganos", "La_Teste"]:
        _d = piezos_step.dropna(subset=[_col, "q_eau_brute_m3j"])
        _ligne = {"piezometre": _col, "jours": len(_d)}
        if len(_d) >= 30:
            _s = _d[_d["pluie_3j_mm"] < PLUIE_SEC_MM]
            _ligne |= {
                "prof_min_m": round(_d[_col].min(), 2),
                "prof_max_m": round(_d[_col].max(), 2),
                "spearman_tous": round(_d["q_eau_brute_m3j"].corr(_d[_col], method="spearman"), 2),
                "spearman_secs": round(_s["q_eau_brute_m3j"].corr(_s[_col], method="spearman"), 2),
                "r2_courbe_s": round(_r2_courbe_s(_d[_col].to_numpy(), _d["q_eau_brute_m3j"].to_numpy()), 2),
            }
        _lignes.append(_ligne)
    comparaison_piezos = pd.DataFrame(_lignes)
    return (comparaison_piezos,)


@app.cell
def _(comparaison_piezos, mo):
    def _n(v):
        return f"{v:+.2f}".replace(".", ",").replace("-", "−")

    def _r2(v):
        return f"{v:.2f}".replace(".", ",")

    _c = comparaison_piezos.set_index("piezometre")
    _best = _c["spearman_secs"].abs().idxmax()
    mo.vstack([
        mo.md(f"""
    ## Quel piézomètre suit le mieux la STEP ?

    Les sections précédentes reposent sur un seul piézomètre (Blagon par
    défaut). Ici les quatre sont comparés côte à côte, quel que soit le
    sélecteur. En plus de Blagon et Piraillan : Canauley à **Biganos**, dans
    la même nappe que Blagon et à quelques kilomètres de la STEP, et
    Villemarie à **La Teste**, sur la rive sud. Les eaux usées de La Teste ne vont pas à
    Biganos : ce piézomètre sert de référence régionale, pour voir si une
    nappe sans lien avec ce réseau suit aussi bien le débit.

    Pour chaque piézomètre, sur 2025 : la corrélation de Spearman entre la
    profondeur et le débit d'entrée, sur tous les jours puis sur les jours
    secs, et le R² de la même courbe en S que plus haut. Une corrélation
    négative veut dire : nappe plus haute (moins profonde), débit plus fort.

    Sur les jours secs, **{_best}** suit le mieux le débit (Spearman
    {_n(_c.loc[_best, "spearman_secs"])}, R² de la courbe en S
    {_r2(_c.loc[_best, "r2_courbe_s"])}), contre
    {_n(_c.loc["Blagon", "spearman_secs"])} et {_r2(_c.loc["Blagon", "r2_courbe_s"])}
    pour Blagon. Toutes les nappes montent en hiver : une corrélation forte à
    La Teste mesure la saison commune, pas un lien avec le réseau. Seul un
    écart net en faveur de Biganos ou de Blagon dit quelque chose sur
    l'emplacement des entrées d'eau.
    """),
        mo.ui.table(comparaison_piezos, selection=None),
    ])
    return


@app.cell
def _(C_ENCRE, C_STEP, comparaison_piezos, pd, piezos_step, plt):
    _cols = list(comparaison_piezos["piezometre"])
    _stats = comparaison_piezos.set_index("piezometre")
    _fig, _axes = plt.subplots(1, len(_cols), figsize=(14, 3.8), sharey=True)
    for _ax, _c in zip(_axes, _cols):
        _d = piezos_step.dropna(subset=[_c])
        _ax.scatter(_d[_c], _d["q_eau_brute_m3j"], s=10, color=C_STEP,
                    alpha=0.5, edgecolors="none")
        _rho = _stats.loc[_c].get("spearman_tous")
        _sous_titre = (
            f"ρ = {_rho:+.2f}".replace(".", ",").replace("-", "−")
            if pd.notna(_rho) else "pas de données"
        )
        _ax.set_title(f"{_c}\n{_sous_titre}", fontsize=10, color=C_ENCRE)
        _ax.invert_xaxis()
        _ax.set_xlabel("Profondeur (m) — nappe plus haute →", fontsize=9)
        _ax.grid(alpha=0.25)
    _axes[0].set_ylabel("Débit d'entrée STEP (m³/j)")
    _fig.tight_layout()
    _fig
    return


@app.cell
def _(mo):
    mo.md("""
    ## Limites et questions ouvertes

    - **Le seuil est nécessaire, pas suffisant.** En 2018, 2019 et 2025, la
      nappe est entrée dans la zone du plafond (7 à 10 jours dans l'année)
      sans épisode HC recensé. Les années avec HC y passent en général plus
      de temps (17 à 36 jours ; 2016 fait exception avec 11 jours). La durée
      passée dans la zone du plafond compte donc probablement, tout comme la
      pluie qui s'y ajoute ou le remplissage des bassins de sécurité. Voir le
      bilan annuel ci-dessus.
    - **Une seule année de débit STEP.** Les seuils de débit reposent sur 2025.
      Le lien entre nappe et épisodes HC couvre onze ans, mais il est indirect.
    - **Hystérésis non testée.** Le débit pourrait suivre un chemin différent
      quand la nappe monte et quand elle descend.
    - **Questions pour le SIBA** :
        - Quelle est la capacité hydraulique de la STEP de Biganos et du
          transfert en amont ? Le palier à 27 000 à 30 000 m³/j
          l'expliquerait-il ?
        - Peut-on obtenir les débits journaliers d'entrée STEP de 2014 à 2026,
          pour tester les deux seuils sur les épisodes de 2016, 2020, 2023 et
          2024 ?
        - Comment est suivi le bassin de délestage de la Titoune (Lanton) ?
          Il n'apparaît pas dans le classeur des volumes mensuels des postes
          de pompage 2025. Existe-t-il un historique de ses mises en charge,
          au moins pour 2018, 2019 et 2025 ? Si le surplus est parti vers les
          bassins en forêt (Titoune, Lège, Audenge) au lieu de déborder en
          ville, cela expliquerait ces années sans épisode HC constaté.
        - Quelle est la capacité de TAUSSAT GARE ? C'est la pompe de
          relevage du collecteur principal qui alimente la STEP (confirmé par
          le SIBA), et son volume représente les deux tiers du volume entrant
          à la STEP (voir le notebook `postes_pompage_nappe.py`). Sa capacité
          pourrait expliquer le plafond de débit.
    """)
    return


@app.cell
def _(df, mo):
    mo.vstack([mo.md("## Données"), mo.ui.table(df.round(2).reset_index(), page_size=15)])
    return


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    import duckdb
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from siba.data.config import CAP_FERRET_NUM_POSTE, DB_PATH
    from siba.paths import REPO_ROOT

    # Base locale construite depuis les classeurs SIBA (hors dépôt, _local/ ignoré).
    REFERE_DIR = REPO_ROOT / "_local" / "refere_from_Daniel_Lafon_20261017"
    REFERE_DB = REFERE_DIR / "refere.duckdb"

    CF = CAP_FERRET_NUM_POSTE
    CAZAUX, PIERROTON, BELIN = "33529001", "33122003", "33042001"

    # Les 11 postes de config.METEO_STATIONS. Une couleur par poste, la même
    # dans tous les graphiques : actifs saturés, fermés en demi-teinte, postes
    # d'avant 1950 en gris/bruns. Classe de site et changements : fiches
    # Météo-France (INFOS_POSTES), lues pour les quatre postes actifs.
    STATIONS = {
        "33236002": dict(label="Cap-Ferret", couleur="#0066cc", fiche="LEGE-CAP-FERRET",
                         groupe="actives", classe_site="4 → 5 (11/07/2023)",
                         changements="11/07/2023 : clôture retirée, site classe 5 ; "
                                     "10/09/2023 : fin de l'abri grand modèle ; "
                                     "pluviomètre R3070 depuis 22/05/2002"),
        "33529001": dict(label="Cazaux", couleur="#1baf7a", fiche="LA-TESTE-DE-BUCH",
                         groupe="actives", classe_site="1 → 2 (norme, 12/04/2016)",
                         changements="même site depuis 29/06/1944 ; automatique "
                                     "depuis 1997 ; mesure classe B"),
        "33122003": dict(label="Pierroton", couleur="#6250d6", fiche="CESTAS",
                         groupe="actives", classe_site="2",
                         changements="site unique depuis 1996 ; mesure classe E"),
        "33042001": dict(label="Belin-Béliet", couleur="#eda100", fiche="BELIN-BELIET",
                         groupe="actives", classe_site="4",
                         changements="21/07/2021 : pluviomètre SPIEA → Préci-Méca "
                                     "3029, station PULSIA IV"),
        "33051001": dict(label="Biganos", couleur="#e87ba4", fiche="BIGANOS",
                         groupe="fermées", classe_site="—", changements="—"),
        "33236004": dict(label="Lège-Bourg", couleur="#008300", fiche="LEGE-CAP-FERRET",
                         groupe="fermées", classe_site="—", changements="—"),
        "33011001": dict(label="Arès", couleur="#4e9a96", fiche="ARES",
                         groupe="fermées", classe_site="—", changements="—"),
        "33009001": dict(label="Arcachon", couleur="#a07cc5", fiche="ARCACHON",
                         groupe="fermées", classe_site="—", changements="—"),
        "33019001": dict(label="Audenge", couleur="#9c7a54", fiche="AUDENGE",
                         groupe="avant 1950", classe_site="—", changements="—"),
        "33529004": dict(label="La Salie", couleur="#7f7f7f", fiche="LA-TESTE-DE-BUCH",
                         groupe="avant 1950", classe_site="—", changements="—"),
        "33009004": dict(label="Arcachon CMD", couleur="#bfa27a", fiche="ARCACHON",
                         groupe="avant 1950", classe_site="—", changements="—"),
    }
    FICHE_URL = ("https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/"
                 "BASE/INFOS_POSTES/33/{num}_33_{fiche}.pdf")

    SEUIL_RR7 = 70
    RUPTURE = pd.Timestamp("2023-07-11")
    C_STEP = "#eb6834"
    C_HC = "#e5484d"
    C_ENCRE = "#52514e"

    def style_axes(ax):
        """Grille horizontale discrète, sans cadre haut/droite."""
        ax.grid(axis="y", color="#e5e4e0", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)

    def fr(x, d=2):
        """Nombre à la française : virgule décimale, espace des milliers."""
        if x is None or pd.isna(x):
            return "—"
        return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")

    def label(num):
        return STATIONS[num]["label"]

    def couleur(num):
        return STATIONS[num]["couleur"]
    return (
        BELIN,
        CAZAUX,
        CF,
        C_ENCRE,
        C_HC,
        C_STEP,
        DB_PATH,
        FICHE_URL,
        PIERROTON,
        REFERE_DB,
        REFERE_DIR,
        RUPTURE,
        SEUIL_RR7,
        STATIONS,
        couleur,
        duckdb,
        fr,
        label,
        mo,
        np,
        pd,
        plt,
        style_axes,
    )


@app.cell
def _(mo):
    mo.md("""
    # Comparaison des stations de pluie

    Les 11 postes Météo-France conservés dans `meteo_jour` (voir
    `config.METEO_STATIONS`) : quatre postes actifs (Cap-Ferret, Cazaux,
    Pierroton, Belin-Béliet), quatre postes fermés autour du Bassin (Biganos,
    Lège-Bourg, Arès, Arcachon) et trois longues séries d'avant 1950 (Audenge,
    La Salie, Arcachon CMD). Pluie journalière RR (mm, de 06h UTC à 06h UTC le
    lendemain), fichiers quotidiens de Météo-France pour la Gironde, archive
    avant 1950 comprise.

    Le notebook compare les postes entre eux, explique la rupture de site de
    Cap-Ferret en juillet 2023, reprend l'analyse du critère SIBA des 70 mm sur
    7 jours (ancien notebook `meteofrance_33_precipation.ipynb`) et regarde les
    épisodes HC depuis chaque poste.

    Cap-Ferret reste la référence des autres notebooks ; la rupture de 2023 n'y
    est pas mentionnée car elle ne change pas leurs conclusions.

    Les cumuls glissants (RR7, RR28, RR30, RR56) suivent la règle du
    chargement : un cumul n'existe que si ses N jours ont une mesure.
    """)
    return


@app.cell
def _(CF, DB_PATH, STATIONS, duckdb, mo, pd):
    mo.stop(
        not DB_PATH.exists(),
        mo.md(f"**Base introuvable** : `{DB_PATH}`. Lancer `make rebuild`."),
    )
    _con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        pluie = _con.execute(
            'SELECT "NUM_POSTE" AS num_poste, "date", TRY_CAST("RR" AS DOUBLE) AS rr '
            'FROM meteo_jour ORDER BY num_poste, "date"'
        ).df()
        meta = _con.execute(
            """
            SELECT "NUM_POSTE" AS num_poste, any_value("NOM_USUEL") AS nom,
                   any_value(TRY_CAST("LAT" AS DOUBLE)) AS lat,
                   any_value(TRY_CAST("LON" AS DOUBLE)) AS lon,
                   any_value(TRY_CAST("ALTI" AS DOUBLE)) AS alti,
                   min("date") AS debut, max("date") AS fin, count("RR") AS jours_rr
            FROM meteo_jour GROUP BY 1 ORDER BY 1
            """
        ).df()
        hc = _con.execute(
            "SELECT start_date, end_date, label FROM hc_period ORDER BY start_date"
        ).df()
        _evts = _con.execute(
            'SELECT "date", rr_7d FROM v_nappe_pluie_events WHERE rr_7d IS NOT NULL'
        ).df()
    finally:
        _con.close()

    hc["start_date"] = pd.to_datetime(hc["start_date"])
    hc["end_date"] = pd.to_datetime(hc["end_date"])

    # Une colonne par poste, un jour par ligne, jours manquants compris.
    pluie["date"] = pd.to_datetime(pluie["date"])
    rr_wide = pluie.pivot(index="date", columns="num_poste", values="rr")
    rr_wide = rr_wide.reindex(
        index=pd.date_range(rr_wide.index.min(), rr_wide.index.max(), freq="D"),
        columns=[n for n in STATIONS if n in rr_wide.columns],
    )
    # Même règle que le chargement : min_periods = fenêtre.
    fen = {w: rr_wide.rolling(w, min_periods=w).sum() for w in (7, 28, 30, 56)}
    rr7 = fen[7]

    # Contrôle : le RR7 Cap-Ferret d'ici = rr_7d de nappe_pluie_daily.
    _ev = _evts.set_index(pd.to_datetime(_evts["date"]))["rr_7d"]
    ecart_rr7 = (rr7[CF].reindex(_ev.index) - _ev).abs().max()
    mo.stop(
        not ecart_rr7 < 1e-6,
        mo.md(f"**Incohérence** : RR7 Cap-Ferret ≠ `nappe_pluie_daily.rr_7d` "
              f"(écart max {ecart_rr7} mm). Le notebook et la base divergent."),
    )
    return ecart_rr7, fen, hc, meta, rr7, rr_wide


@app.cell
def _(ecart_rr7, fr, mo, rr_wide):
    mo.md(f"""
    {len(rr_wide.columns)} postes, du {rr_wide.index.min():%d/%m/%Y} au
    {rr_wide.index.max():%d/%m/%Y}. Contrôle : le RR7 de Cap-Ferret calculé ici
    et la colonne `rr_7d` de `nappe_pluie_daily` diffèrent au plus de
    {fr(ecart_rr7, 6)} mm.
    """)
    return


@app.cell
def _(FICHE_URL, STATIONS, fr, meta, mo, np, pd):
    def _distance_km(lat, lon):
        # Haversine depuis la rive est du Bassin (44,66 N ; 1,05 O).
        lat0, lon0 = np.radians(44.66), np.radians(-1.05)
        lat, lon = np.radians(lat), np.radians(lon)
        a = (np.sin((lat - lat0) / 2) ** 2
             + np.cos(lat0) * np.cos(lat) * np.sin((lon - lon0) / 2) ** 2)
        return 2 * 6371 * np.arcsin(np.sqrt(a))

    _m = meta.set_index("num_poste")
    _rows = []
    for _num, _s in STATIONS.items():
        if _num not in _m.index:
            continue
        _r = _m.loc[_num]
        _rows.append({
            "code": _num,
            "poste": _s["label"],
            "nom Météo-France": _r["nom"],
            "groupe": _s["groupe"],
            "distance (km)": fr(_distance_km(_r["lat"], _r["lon"]), 0),
            "début": pd.Timestamp(_r["debut"]).strftime("%d/%m/%Y"),
            "fin": pd.Timestamp(_r["fin"]).strftime("%d/%m/%Y"),
            "jours RR": fr(_r["jours_rr"], 0),
            "classe de site": _s["classe_site"],
            "changements datés": _s["changements"],
            "fiche": FICHE_URL.format(num=_num, fiche=_s["fiche"]),
        })
    mo.vstack([
        mo.md("""
        ## 1. Les postes

        Distance mesurée depuis la rive est du Bassin (44,66 N ; 1,05 O). Les
        dates de changement de Cap-Ferret (11/07/2023) et de Belin-Béliet
        (21/07/2021) viennent des fiches Météo-France (lien en dernière
        colonne) ; les fiches des postes fermés n'ont pas été relevées.
        """),
        mo.ui.table(pd.DataFrame(_rows), selection=None, page_size=11),
    ])
    return


@app.cell
def _(CF, rr_wide):
    # Totaux annuels sur les années quasi complètes (≥ 330 jours mesurés).
    _g = rr_wide.groupby(rr_wide.index.year)
    annuel = _g.sum(min_count=1).where(_g.count() >= 330)
    ratio_cf = annuel.div(annuel[CF], axis=0).drop(columns=CF).dropna(axis=1, how="all")
    return annuel, ratio_cf


@app.cell
def _(C_ENCRE, RUPTURE, annuel, couleur, fr, label, mo, pd, plt, ratio_cf, style_axes):
    def _plot():
        fig, (ax_a, ax_b) = plt.subplots(
            2, 1, figsize=(11, 8), constrained_layout=True,
            gridspec_kw={"height_ratios": [3, 2]},
        )
        # Pas de dropna : une année incomplète coupe la ligne au lieu de la relier.
        for num in annuel.columns:
            s = annuel[num]
            ax_a.plot(s.index, s.values, color=couleur(num), linewidth=1.5,
                      marker="o", markersize=2.5, label=label(num))
        ax_a.set_title("A. Pluie annuelle par poste (mm, années ≥ 330 jours mesurés)",
                       loc="left", fontsize=11)
        ax_a.set_ylim(bottom=0)
        ax_a.legend(ncol=4, fontsize=8, frameon=False, loc="lower left")
        for num in ratio_cf.columns:
            s = ratio_cf[num]
            ax_b.plot(s.index, s.values, color=couleur(num), linewidth=1.5,
                      marker="o", markersize=3, label=label(num))
        ax_b.axhline(1, color=C_ENCRE, linewidth=1)
        ax_b.axvline(RUPTURE.year + RUPTURE.dayofyear / 365, color=C_ENCRE,
                     linewidth=1, linestyle="--")
        ax_b.set_title("B. Rapport poste / Cap-Ferret, années complètes communes "
                       "(tirets : rupture de juillet 2023)", loc="left", fontsize=11)
        ax_b.legend(ncol=5, fontsize=8, frameon=False, loc="upper left")
        for ax in (ax_a, ax_b):
            style_axes(ax)
        return fig

    def _med(num, a, b):
        return ratio_cf.loc[a:b, num].median()

    _tbl = pd.DataFrame([
        {
            "poste": label(num),
            "médiane 2015–2021": fr(_med(num, 2015, 2021)),
            "médiane 2023–2026": fr(_med(num, 2023, 2026)),
            "années 2015–2021": int(ratio_cf.loc[2015:2021, num].notna().sum()),
            "années 2023–2026": int(ratio_cf.loc[2023:2026, num].notna().sum()),
        }
        for num in ratio_cf.columns if ratio_cf.loc[2015:2026, num].notna().any()
    ])
    mo.vstack([
        mo.md("""
        ## 2. Totaux annuels

        Le haut montre chaque poste sur toute sa période. Le bas rapporte chaque
        poste à Cap-Ferret sur les années complètes des deux postes : avant
        juillet 2023, tous les autres postes reçoivent environ 1,3 fois la pluie
        de Cap-Ferret ; après, l'écart se resserre d'un coup.
        """),
        _plot(),
        mo.md("**Rapport médian à Cap-Ferret, avant et après la rupture**"),
        mo.ui.table(_tbl, selection=None),
    ])
    return


@app.cell
def _(BELIN, CAZAUX, CF, PIERROTON, RUPTURE, pd, rr_wide):
    # Fenêtres de 2 ans coupées le 11 juillet, date de la rupture de Cap-Ferret.
    _debut = pd.Timestamp("2015-07-11")
    _fin = rr_wide.index.max()
    _bornes = []
    _d = _debut
    while _d <= _fin:
        _bornes.append((_d, min(_d + pd.DateOffset(years=2), _fin + pd.Timedelta(days=1))))
        _d = _d + pd.DateOffset(years=2)

    def _ratio(a, b, lo, hi):
        # Σ a / Σ b sur les jours où les deux postes ont une mesure.
        x = rr_wide.loc[lo:hi - pd.Timedelta(days=1), [a, b]].dropna()
        return x[a].sum() / x[b].sum() if len(x) else float("nan")

    _paires = {
        "CF / Cazaux": (CF, CAZAUX),
        "CF / Pierroton": (CF, PIERROTON),
        "CF / Belin": (CF, BELIN),
        "Belin / Cazaux": (BELIN, CAZAUX),
        "Pierroton / Cazaux": (PIERROTON, CAZAUX),
    }
    fenetres_2ans = pd.DataFrame(
        [
            {"fenêtre": f"{lo.year}–{str((hi - pd.Timedelta(days=1)).year)[2:]}",
             "début": lo,
             **{k: _ratio(a, b, lo, hi) for k, (a, b) in _paires.items()}}
            for lo, hi in _bornes
        ]
    )

    # Rapport journalier médian CF / Cazaux sur les jours de pluie communs.
    _j = rr_wide.loc[_debut:, [CF, CAZAUX]].dropna()
    _j = _j[(_j[CF] >= 1) & (_j[CAZAUX] >= 1)]
    _r = _j[CF] / _j[CAZAUX]
    ratio_jour_avant = _r[_r.index < RUPTURE].median()
    ratio_jour_apres = _r[_r.index >= RUPTURE].median()
    n_jours_avant = int((_r.index < RUPTURE).sum())
    n_jours_apres = int((_r.index >= RUPTURE).sum())

    # Vue longue : blocs de 5 ans depuis 1950, jours communs avec Cazaux.
    _rows = []
    for _y in range(1950, rr_wide.index.max().year + 1, 5):
        _row = {"bloc": f"{_y}–{_y + 4}", "an": _y}
        for _k, _num in (("Cap-Ferret / Cazaux", CF), ("Arcachon / Cazaux", "33009001")):
            _x = rr_wide.loc[str(_y):str(_y + 4), [_num, CAZAUX]].dropna()
            _row[_k] = _x[_num].sum() / _x[CAZAUX].sum() if len(_x) > 365 else float("nan")
        _rows.append(_row)
    blocs_5ans = pd.DataFrame(_rows)
    return (
        blocs_5ans,
        fenetres_2ans,
        n_jours_apres,
        n_jours_avant,
        ratio_jour_apres,
        ratio_jour_avant,
    )


@app.cell
def _(
    BELIN,
    CAZAUX,
    CF,
    C_ENCRE,
    PIERROTON,
    RUPTURE,
    blocs_5ans,
    couleur,
    fenetres_2ans,
    fr,
    mo,
    n_jours_apres,
    n_jours_avant,
    pd,
    plt,
    ratio_jour_apres,
    ratio_jour_avant,
    style_axes,
):
    def _plot():
        fig, (ax_cf, ax_mu, ax_long) = plt.subplots(
            3, 1, figsize=(11, 10), constrained_layout=True,
        )
        _x = fenetres_2ans["début"] + pd.DateOffset(years=1)
        for k, num in (("CF / Cazaux", CAZAUX), ("CF / Pierroton", PIERROTON),
                       ("CF / Belin", BELIN)):
            ax_cf.plot(_x, fenetres_2ans[k], color=couleur(num), linewidth=2,
                       marker="o", markersize=6, label=k)
        ax_cf.set_title("A. Cap-Ferret rapporté aux autres postes, fenêtres de 2 ans "
                        "coupées le 11 juillet", loc="left", fontsize=11)
        for k, num in (("Belin / Cazaux", BELIN), ("Pierroton / Cazaux", PIERROTON)):
            ax_mu.plot(_x, fenetres_2ans[k], color=couleur(num), linewidth=2,
                       marker="o", markersize=6, label=k)
        ax_mu.set_title("B. Contrôle mutuel : Belin et Pierroton rapportés à Cazaux",
                        loc="left", fontsize=11)
        for ax in (ax_cf, ax_mu):
            ax.axvline(RUPTURE, color=C_ENCRE, linewidth=1, linestyle="--")
            ax.axhline(1, color=C_ENCRE, linewidth=0.8)
            ax.legend(fontsize=8, frameon=False, loc="upper left")
        for k, num in (("Cap-Ferret / Cazaux", CF), ("Arcachon / Cazaux", "33009001")):
            # Dernier palier répété : le bloc final garde sa largeur de 5 ans.
            x = list(blocs_5ans["an"]) + [blocs_5ans["an"].iloc[-1] + 5]
            y = list(blocs_5ans[k]) + [blocs_5ans[k].iloc[-1]]
            ax_long.step(x, y, where="post", color=couleur(num), linewidth=2, label=k)
        ax_long.axhline(1, color=C_ENCRE, linewidth=0.8)
        ax_long.set_title("C. Vue longue : blocs de 5 ans, jours communs avec Cazaux",
                          loc="left", fontsize=11)
        ax_long.legend(fontsize=8, frameon=False, loc="lower left")
        for ax in (ax_cf, ax_mu, ax_long):
            style_axes(ax)
        return fig

    _tbl = fenetres_2ans.drop(columns="début").copy()
    for _c in _tbl.columns[1:]:
        _tbl[_c] = _tbl[_c].map(fr)
    _blocs = blocs_5ans.drop(columns="an").copy()
    for _c in _blocs.columns[1:]:
        _blocs[_c] = _blocs[_c].map(fr)

    mo.vstack([
        mo.md(f"""
        ## 3. La rupture de Cap-Ferret (juillet 2023)

        **Ce que dit la fiche Météo-France** (`33236002_33_LEGE-CAP-FERRET.pdf`,
        éditée le 05/01/2026) : la qualité du site pluie passe de la classe 4
        (« clôture plaques fibro-ciment, arbres à proximité ») jusqu'au
        10/07/2023 à la classe 5 (« arbres à proximité ») à partir du
        11/07/2023 : la clôture a disparu. Le même été, l'abri grand modèle est
        retiré (fin le 10/09/2023) et les photos du 08/09/2023 montrent un mât
        compact portant pluviomètre et abri. Le pluviomètre, un auget R3070
        installé le 22/05/2002, n'a pas changé.

        **Ce que disent les données.** Sur les fenêtres de 2 ans, Cap-Ferret
        recueille 0,7 à 0,85 fois la pluie de ses voisins jusqu'en 2023, puis
        s'en rapproche d'un coup. Le rapport journalier médian Cap-Ferret /
        Cazaux, sur les jours où les deux postes mesurent au moins 1 mm, passe
        de **{fr(ratio_jour_avant)}** ({n_jours_avant} jours depuis le
        11/07/2015) à **{fr(ratio_jour_apres)}** après le 11/07/2023
        ({n_jours_apres} jours). Belin et Pierroton, rapportés à Cazaux, restent
        plats sur les mêmes fenêtres, y compris Belin en 2021 (changement de
        pluviomètre) : seul Cap-Ferret saute.
        """),
        _plot(),
        mo.ui.table(_tbl, selection=None),
        mo.md("""
        **Vue longue.** Le déficit de Cap-Ferret n'est pas constant : proche de
        Cazaux dans les années 1950–1960, il se creuse ensuite et s'aggrave de
        2005 à 2023, ce qui s'accorde avec les « arbres à proximité » notés sur
        la fiche depuis 1999. Il n'existe donc pas de facteur de correction
        unique. Arcachon, poste de rivage indépendant, se tenait lui aussi vers
        0,85–0,9 de Cazaux entre 1970 et 2000 : une partie du déficit peut être
        réelle (rivage plus sec que Cazaux), et le « vrai » niveau du rivage
        reste incertain ; après 2023, Cap-Ferret lit peut-être un peu haut. Un
        possible changement à Cazaux vers 1967–1970 (abri en 1967, anémomètre en
        1968) est signalé mais n'a pas été étudié.
        """),
        mo.ui.table(_blocs, selection=None, page_size=16),
    ])
    return


@app.cell
def _(BELIN, CAZAUX, CF, PIERROTON, fr, label, mo, plt, rr7, rr_wide):
    _cols = [c for c in (CF, CAZAUX, PIERROTON, BELIN, "33051001", "33236004")
             if c in rr_wide.columns]
    _corr_j = rr_wide.loc["2015":, _cols].corr()
    _corr_7 = rr7.loc["2015":, _cols].corr()

    def _plot():
        fig, axes = plt.subplots(1, 2, figsize=(11, 5), constrained_layout=True)
        vmin = min(_corr_j.min().min(), _corr_7.min().min())
        for ax, m, titre in ((axes[0], _corr_j, "Pluie journalière"),
                             (axes[1], _corr_7, "RR7")):
            im = ax.imshow(m.values, cmap="Blues", vmin=vmin, vmax=1)
            names = [label(c) for c in m.columns]
            ax.set_xticks(range(len(names)), names, rotation=45, ha="right", fontsize=9)
            ax.set_yticks(range(len(names)), names, fontsize=9)
            for i in range(len(names)):
                for j in range(len(names)):
                    v = m.values[i, j]
                    ax.text(j, i, fr(v), ha="center", va="center", fontsize=8,
                            color="white" if v > (vmin + 1) / 2 else "#0b0b0b")
            ax.set_title(f"{titre}, 2015 →", loc="left", fontsize=11)
        fig.colorbar(im, ax=axes, shrink=0.8, label="r de Pearson")
        return fig

    mo.vstack([
        mo.md("""
        ## 4. Accord entre stations

        Corrélation de Pearson depuis 2015, sur les jours où les deux postes ont
        une mesure (Biganos et Lège-Bourg jusqu'à leur fermeture). La
        corrélation ignore l'échelle : un poste qui recueille 20 % de moins
        mais au même rythme reste à r ≈ 1. La rupture de Cap-Ferret ne se voit
        donc pas ici, seulement dans les rapports de la section 3.
        """),
        _plot(),
    ])
    return


@app.cell
def _(CF, SEUIL_RR7, fen, pd, rr7):
    # Jours au-dessus du seuil et épisodes (suites de jours consécutifs), par an.
    _an = rr7.index.year
    depasse = rr7 > SEUIL_RR7
    _valide = rr7.notna().groupby(_an).sum()
    jours_70 = depasse.groupby(_an).sum().where(_valide > 0)
    _debut_ep = depasse & ~depasse.shift(1, fill_value=False)
    episodes_70 = _debut_ep.groupby(_an).sum().where(_valide > 0)

    # Records par poste.
    _rec = []
    for _num in rr7.columns:
        _s7, _s30 = fen[7][_num].dropna(), fen[30][_num].dropna()
        if _s7.empty:
            continue
        _rec.append({"num": _num, "rr7_max": _s7.max(), "rr7_date": _s7.idxmax(),
                     "rr30_max": _s30.max(), "rr30_date": _s30.idxmax()})
    records = pd.DataFrame(_rec)

    # Cap-Ferret, années complètes (≥ 300 jours de RR7) : part des jours au-dessus.
    _cf = pd.DataFrame({"jours": jours_70[CF], "valides": _valide[CF]}).dropna()
    cf_annees = _cf[_cf["valides"] >= 300].assign(pct=lambda d: 100 * d["jours"] / d["valides"])
    return cf_annees, depasse, episodes_70, jours_70, records


@app.cell
def _(
    BELIN,
    CAZAUX,
    CF,
    PIERROTON,
    RUPTURE,
    cf_annees,
    depasse,
    episodes_70,
    fen,
    fr,
    jours_70,
    label,
    mo,
    np,
    pd,
    plt,
    ratio_jour_apres,
    ratio_jour_avant,
    records,
):
    def _plot():
        m = jours_70.T
        fig, ax = plt.subplots(figsize=(13, 4.2), constrained_layout=True)
        im = ax.imshow(np.ma.masked_invalid(m.values.astype(float)), aspect="auto",
                       cmap="Blues", interpolation="nearest")
        ax.set_yticks(range(len(m.index)), [label(c) for c in m.index], fontsize=9)
        _years = list(m.columns)
        _ticks = [i for i, y in enumerate(_years) if y % 10 == 0]
        ax.set_xticks(_ticks, [_years[i] for i in _ticks], fontsize=9)
        ax.set_facecolor("#f3f2ef")
        ax.set_title("Jours par an où RR7 > 70 mm (gris : pas de mesure)",
                     loc="left", fontsize=11)
        fig.colorbar(im, ax=ax, label="jours", shrink=0.9)
        return fig

    def _int_table(df):
        out = df.copy()
        out.index.name = "année"
        out.columns = [label(c) for c in out.columns]
        return out.map(lambda v: "" if pd.isna(v) else int(v)).reset_index().sort_values(
            "année", ascending=False)

    # 2015 → : quatre postes actifs.
    _recents = {label(n): int(depasse.loc["2015":, n].sum())
                for n in (CF, CAZAUX, PIERROTON, BELIN)}

    # Cap-Ferret : années complètes.
    _n_ans = len(cf_annees)
    _n_un = int((cf_annees["jours"] >= 1).sum())
    _n_dix = int((cf_annees["jours"] >= 10).sum())
    _pct_avant = cf_annees.loc[cf_annees.index < 2015, "pct"].mean()
    _pct_depuis = cf_annees.loc[cf_annees.index >= 2015, "pct"].mean()
    _rang_2023 = int((cf_annees["jours"] > cf_annees.loc[2023, "jours"]).sum()) + 1
    _top = cf_annees.sort_values(["jours", "pct"], ascending=False).head(10)
    _top_tbl = pd.DataFrame({
        "année": _top.index, "jours > 70 mm": _top["jours"].astype(int),
        "% des jours": _top["pct"].map(lambda v: fr(v, 1)),
    })

    # Records RR7 / RR30.
    _rec_tbl = pd.DataFrame({
        "poste": records["num"].map(label),
        "RR7 max (mm)": records["rr7_max"].map(lambda v: fr(v, 1)),
        "date RR7": records["rr7_date"].dt.strftime("%d/%m/%Y"),
        "RR30 max (mm)": records["rr30_max"].map(lambda v: fr(v, 1)),
        "date RR30": records["rr30_date"].dt.strftime("%d/%m/%Y"),
    })

    # 2023 relu à la lumière de la rupture.
    _cf30 = fen[30][CF]
    _v23, _d23 = _cf30.loc["2023"].max(), _cf30.loc["2023"].idxmax()
    _avant = _cf30.loc[:RUPTURE - pd.Timedelta(days=1)]
    _v_av, _d_av = _avant.max(), _avant.idxmax()
    # Record antérieur tous postes confondus (celui que citait l'ancien notebook).
    _tous = fen[30].loc[:RUPTURE - pd.Timedelta(days=1)]
    _num_tous = _tous.max().idxmax()
    _v_tous, _d_tous = _tous[_num_tous].max(), _tous[_num_tous].idxmax()
    _v23_corr = _v23 * ratio_jour_avant / ratio_jour_apres
    _rangs = []
    for _num in (CAZAUX, PIERROTON, BELIN):
        _s = fen[30][_num]
        _nov = _s.loc["2023-11"].max()
        _maxi = _s.groupby(_s.index.year).max().dropna()
        _k = int((_maxi.drop(2023) > _nov).sum()) + 1
        _rangs.append(f"{label(_num)} {fr(_nov, 1)} mm, rang {_k} sur {len(_maxi)} années")

    mo.vstack([
        mo.md("""
        ## 5. Le critère SIBA des 70 mm sur 7 jours

        Le SIBA a défini fin 2016 un critère de « situation inhabituelle » pour
        encadrer les rejets d'eaux usées dans le Bassin :

        > Les notions de « fortes pluies » et d' « inondation » manquant de
        > précision et pouvant être sujettes à interprétation, il avait été
        > proposé fin 2016, après une analyse statistique des situations
        > rencontrées lors des différents épisodes pluvieux enregistrés de 2013
        > à 2016, que soit déclaré au niveau du Bassin d'Arcachon « situation
        > inhabituelle » lorsque les précipitations cumulées sur 7 jours
        > consécutifs dépassent 70 mm.

        Source : [plainte de l'ADEBA contre le SIBA](https://adeba.fr/index.php/2023/12/31/plainte-contre-le-siba-pour-pollution-des-eaux-du-bassin/).
        La question reprise de l'ancien notebook : ce seuil est-il vraiment
        inhabituel ? Ici un jour compte si RR7 > 70 mm avec 7 jours mesurés ;
        l'ancien notebook acceptait les fenêtres incomplètes et n'avait pas
        Arcachon CMD (1885–1946) : les comptes diffèrent légèrement.
        """),
        _plot(),
        mo.ui.tabs({
            "Jours > 70 mm par an": mo.ui.table(_int_table(jours_70), selection=None,
                                                page_size=15),
            "Épisodes par an": mo.ui.table(_int_table(episodes_70), selection=None,
                                           page_size=15),
        }),
        mo.md(f"""
        Un épisode est une suite de jours consécutifs au-dessus du seuil,
        compté l'année de son premier jour. Depuis 2015, jours au-dessus de
        70 mm : {", ".join(f"{k} {v}" for k, v in _recents.items())}. Cap-Ferret
        en compte moitié moins que ses voisins : c'est son déficit de captation
        (section 3), pas une pluie plus faible.

        **Cap-Ferret, {_n_ans} années complètes** (≥ 300 jours de RR7) : au
        moins un jour au-dessus du seuil dans {_n_un} années sur {_n_ans}
        ({fr(100 * _n_un / _n_ans, 0)} %), dix jours ou plus dans {_n_dix}
        années. Part moyenne des jours au-dessus : {fr(_pct_avant, 1)} % avant
        2015, {fr(_pct_depuis, 1)} % depuis : pas de hausse récente. 2023 se
        classe {_rang_2023}{"re" if _rang_2023 == 1 else "e"} par le nombre de
        jours.
        """),
        mo.hstack([
            mo.vstack([mo.md("**Cap-Ferret : les 10 années les plus chargées**"),
                       mo.ui.table(_top_tbl, selection=None)]),
            mo.vstack([mo.md("**Records par poste**"),
                       mo.ui.table(_rec_tbl, selection=None)]),
        ], widths=[1, 2], gap=2),
        mo.md(f"""
        **Le record de novembre 2023, relu.** L'ancien notebook présentait le
        RR30 de Cap-Ferret du {_d23:%d/%m/%Y} ({fr(_v23, 1)} mm) comme un record
        absolu. Il tombe après la rupture du 11/07/2023. Ramené à l'échelle
        d'avant la rupture (rapport journalier à Cazaux {fr(ratio_jour_avant)}
        avant, {fr(ratio_jour_apres)} après), il vaudrait environ
        {fr(_v23_corr, 0)} mm : {"au-dessus" if _v23_corr > _v_av else "en dessous"}
        du maximum antérieur de Cap-Ferret ({fr(_v_av, 1)} mm le
        {_d_av:%d/%m/%Y}), mais {"au-dessus" if _v23_corr > _v_tous else "en dessous"}
        du record antérieur tous postes confondus ({fr(_v_tous, 1)} mm à
        {label(_num_tous)} le {_d_tous:%d/%m/%Y}). Aux autres postes actifs, le
        maximum de RR30 de novembre 2023 se place ainsi parmi les maxima
        annuels de leur série : {" ; ".join(_rangs)}. Novembre 2023 est donc
        bien exceptionnel chez les voisins ; c'est son écart au passé de
        Cap-Ferret qui est gonflé par la rupture.

        **Conclusion.** Le seuil de 70 mm n'est pas rare : il est franchi la
        plupart des années, à Cap-Ferret comme ailleurs, et plus souvent encore
        aux postes qui captent mieux. Il reste le critère du SIBA.
        """),
    ])
    return


@app.cell
def _(SEUIL_RR7, fen, hc, pd, rr_wide):
    _postes = [c for c in rr_wide.columns
               if rr_wide.loc["2014":, c].notna().any()]

    # Maximum des cumuls sur [début − 14 j, fin] de chaque épisode HC.
    _rows = []
    for _, _e in hc.iterrows():
        _lo, _hi = _e["start_date"] - pd.Timedelta(days=14), _e["end_date"]
        for _num in _postes:
            if rr_wide.loc[_lo:_hi, _num].notna().sum() == 0:
                continue
            _rows.append({"episode": _e["label"], "debut": _e["start_date"], "num": _num,
                          **{f"rr{w}": fen[w].loc[_lo:_hi, _num].max() for w in (7, 28, 56)}})
    hc_max = pd.DataFrame(_rows)

    # Drapeau HC journalier depuis 2014.
    _jours = pd.date_range("2014-01-01", rr_wide.index.max(), freq="D")
    in_hc = pd.Series(False, index=_jours)
    for _, _e in hc.iterrows():
        in_hc.loc[_e["start_date"]:_e["end_date"]] = True

    def _auc(v, y):
        # Mann–Whitney : probabilité qu'un jour HC dépasse un jour hors HC.
        r = v.rank()
        n1, n0 = int(y.sum()), int((~y).sum())
        if n1 == 0 or n0 == 0:
            return float("nan")
        return (r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)

    _auc_rows, _seuil_rows = [], []
    for _num in _postes:
        _row = {"num": _num}
        for _w in (7, 28, 56):
            _v = fen[_w].loc[_jours, _num]
            _m = _v.notna()
            _row[f"rr{_w}"] = _auc(_v[_m], in_hc[_m])
        _auc_rows.append(_row)
        _v7 = fen[7].loc[_jours, _num]
        _m = _v7.notna()
        _au = (_v7 > SEUIL_RR7) & _m
        _hc = in_hc & _m
        _seuil_rows.append({
            "num": _num,
            "jours > 70": int(_au.sum()),
            "précision": (_au & _hc).sum() / _au.sum() if _au.sum() else float("nan"),
            "couverture": (_au & _hc).sum() / _hc.sum() if _hc.sum() else float("nan"),
            "jours HC mesurés": int(_hc.sum()),
        })
    hc_auc = pd.DataFrame(_auc_rows)
    hc_seuil = pd.DataFrame(_seuil_rows)
    return hc_auc, hc_max, hc_seuil


@app.cell
def _(C_HC, SEUIL_RR7, couleur, fr, hc_auc, hc_max, hc_seuil, label, mo, np, pd, plt, style_axes):
    def _plot():
        eps = hc_max.drop_duplicates("episode").sort_values("debut")["episode"].tolist()
        postes = list(dict.fromkeys(hc_max["num"]))
        fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True, constrained_layout=True)
        width = 0.8 / len(postes)
        for ax, w in zip(axes, (7, 28, 56)):
            for i, num in enumerate(postes):
                sub = hc_max[hc_max["num"] == num].set_index("episode").reindex(eps)
                x = np.arange(len(eps)) - 0.4 + width * (i + 0.5)
                ax.bar(x, sub[f"rr{w}"], width=width * 0.9, color=couleur(num),
                       label=label(num))
            ax.set_title(f"RR{w} maximal sur l'épisode et les 14 jours avant (mm)",
                         loc="left", fontsize=11)
            style_axes(ax)
        axes[0].axhline(SEUIL_RR7, color=C_HC, linewidth=1, linestyle="--")
        axes[0].legend(ncol=len(postes), fontsize=8, frameon=False, loc="upper left")
        axes[-1].set_xticks(range(len(eps)), [e.split(" (")[0] for e in eps], fontsize=9)
        return fig

    _max_tbl = hc_max.assign(poste=hc_max["num"].map(label))[
        ["episode", "poste", "rr7", "rr28", "rr56"]].copy()
    for _c in ("rr7", "rr28", "rr56"):
        _max_tbl[_c] = _max_tbl[_c].map(lambda v: fr(v, 0))
    _max_tbl.columns = ["épisode", "poste", "RR7 max", "RR28 max", "RR56 max"]

    _auc_tbl = pd.DataFrame({
        "poste": hc_auc["num"].map(label),
        "AUC RR7": hc_auc["rr7"].map(fr), "AUC RR28": hc_auc["rr28"].map(fr),
        "AUC RR56": hc_auc["rr56"].map(fr),
    })
    _seuil_tbl = pd.DataFrame({
        "poste": hc_seuil["num"].map(label),
        "jours RR7 > 70": hc_seuil["jours > 70"],
        "précision": hc_seuil["précision"].map(fr),
        "couverture": hc_seuil["couverture"].map(lambda v: fr(100 * v, 0) + " %"),
        "jours HC mesurés": hc_seuil["jours HC mesurés"],
    })

    mo.vstack([
        mo.md(f"""
        ## 6. Les épisodes HC vus depuis chaque poste

        Pour chacun des {hc_max["episode"].nunique()} épisodes de `hc_period`,
        le cumul maximal sur l'épisode et les 14 jours qui le précèdent. Les
        tirets rouges marquent le seuil de 70 mm.
        """),
        _plot(),
        mo.ui.table(_max_tbl, selection=None, page_size=12),
        mo.md("""
        **Séparation jours HC / autres jours** depuis 2014 : l'AUC est la
        probabilité qu'un jour HC tiré au hasard ait un cumul plus élevé qu'un
        jour hors HC (0,5 = aucune séparation). La **précision** du seuil est la
        part des jours RR7 > 70 mm qui tombent en HC ; sa **couverture** la part
        des jours HC qu'il signale.
        """),
        mo.hstack([mo.ui.table(_auc_tbl, selection=None),
                   mo.ui.table(_seuil_tbl, selection=None)], gap=2),
        mo.md("""
        La longueur de la fenêtre compte bien plus que le poste : l'AUC passe
        d'environ 0,7 en RR7 à 0,9 en RR56 partout, et une AUC est insensible au
        facteur d'échelle de Cap-Ferret. Le seuil des 70 mm sur 7 jours sépare
        mal : la plupart des jours au-dessus ne sont pas HC, et il ne couvre
        qu'une petite part des jours HC. Prudence : 8 à 9 épisodes seulement,
        des jours autocorrélés, et les dates de 2014 à 2020 sont approximatives.
        """),
    ])
    return


@app.cell
def _(REFERE_DB, REFERE_DIR, duckdb, mo, pd):
    mo.stop(
        not REFERE_DB.exists(),
        mo.md(
            f"**Base STEP introuvable** : `{REFERE_DB}`. Section 7 ignorée.\n\n"
            f"La construire : `cd {REFERE_DIR} && duckdb refere.duckdb < load.sql`"
        ),
    )
    _con = duckdb.connect(str(REFERE_DB), read_only=True)
    try:
        step = _con.execute(
            "SELECT date, pluie_mm FROM step_biganos_jour ORDER BY date"
        ).df()
    finally:
        _con.close()
    step = step.set_index(pd.to_datetime(step["date"]))["pluie_mm"]
    return (step,)


@app.cell
def _(BELIN, CAZAUX, CF, C_STEP, PIERROTON, couleur, fen, fr, label, mo, np, pd, plt, rr_wide, step, style_axes):
    _postes = [CF, CAZAUX, PIERROTON, BELIN]
    _jours = step.index
    _an = _jours[0].year
    _df = pd.concat([step.rename("STEP"), rr_wide.reindex(_jours)[_postes]], axis=1)
    _mois = _df.groupby(_df.index.month).sum(min_count=1)
    _step7 = step.rolling(7, min_periods=7).sum()

    _rows = [{"poste": "STEP Biganos", "total (mm)": fr(step.sum(), 0),
              "r journalier": "", "r RR7": ""}]
    for _num in _postes:
        _s = rr_wide[_num].reindex(_jours)
        _s7 = fen[7][_num].reindex(_jours)
        _rows.append({
            "poste": label(_num),
            "total (mm)": fr(_s.sum(min_count=1), 0),
            "r journalier": fr(step.corr(_s)),
            "r RR7": fr(_step7.corr(_s7)),
        })
    _ecart7 = (_step7 - fen[7][CF].reindex(_jours)).mean()
    _rapport = step.sum() / rr_wide[CF].reindex(_jours).sum()

    def _plot():
        fig, ax = plt.subplots(figsize=(11, 4.5), constrained_layout=True)
        series = [("STEP Biganos", "STEP", C_STEP)] + [
            (label(n), n, couleur(n)) for n in _postes]
        width = 0.8 / len(series)
        for i, (nom, col, c) in enumerate(series):
            x = np.arange(12) - 0.4 + width * (i + 0.5)
            ax.bar(x, _mois[col].reindex(range(1, 13)), width=width * 0.9, color=c, label=nom)
        ax.set_xticks(range(12), ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.",
                                  "août", "sept.", "oct.", "nov.", "déc."])
        ax.set_title(f"Pluie mensuelle {_an} (mm)", loc="left", fontsize=11)
        ax.set_ylim(0, ax.get_ylim()[1] * 1.15)  # place pour la légende
        ax.legend(ncol=5, fontsize=8, frameon=False, loc="upper center")
        style_axes(ax)
        return fig

    mo.vstack([
        mo.md(f"""
        ## 7. Le pluviomètre de la STEP de Biganos ({_an})

        Le classeur SIBA donne la pluie journalière mesurée à la STEP de
        Biganos, sur la rive est. Sur {_an}, elle totalise {fr(step.sum(), 0)} mm,
        soit {fr(_rapport, 2)} fois Cap-Ferret ; le RR7 de la STEP dépasse en
        moyenne celui de Cap-Ferret de {fr(_ecart7, 1)} mm.
        """),
        _plot(),
        mo.ui.table(pd.DataFrame(_rows), selection=None),
        mo.md("""
        L'écart avec Cap-Ferret ressemble à un vrai gradient plutôt qu'à un
        biais du pluviomètre : tous les postes intérieurs reçoivent environ 1,3
        fois la pluie de Cap-Ferret avant 2023 (section 2), et Pierroton est
        proche de la STEP. Reste à savoir à quel pluviomètre se réfère le seuil
        de 70 mm du SIBA.
        """),
    ])
    return


@app.cell
def _(mo):
    mo.md("""
    ## Questions ouvertes pour Daniel

    1. Sur quel pluviomètre le SIBA calcule-t-il le seuil de 70 mm sur 7 jours ?
    2. Depuis quand le pluviomètre de la STEP de Biganos mesure-t-il ? Le SIBA
       a-t-il d'autres pluviomètres ?
    3. Le SIBA sait-il que le site de Cap-Ferret a changé en juillet 2023
       (environ +20 % de pluie mesurée depuis) ?
    """)
    return


if __name__ == "__main__":
    app.run()

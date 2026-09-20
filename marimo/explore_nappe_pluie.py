import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    import datetime as dt
    import duckdb
    import matplotlib.pyplot as plt

    from siba.data.config import DB_PATH

    return DB_PATH, dt, duckdb, mo, plt


@app.cell
def _(DB_PATH, mo):
    mo.md(f"""
    # Nappe + pluie — exploration réactive

    Les données viennent de la base DuckDB `{DB_PATH}` (table `nappe_pluie_daily`,
    alimentée par `siba.data`). Aucun cache CSV, aucun appel réseau : le notebook
    lit la base en lecture seule.

    Si la base n'existe pas encore : `make rebuild` (ou `make update`).

    Choisir la période, le piézomètre et la fenêtre de cumul de pluie ci-dessous ;
    seules les cellules qui en dépendent sont recalculées. Les bandes rouges
    marquent les périodes « hors de contrôle » (HC) du réseau EU.
    """)
    return


@app.cell
def _(DB_PATH, duckdb, mo):
    mo.stop(
        not DB_PATH.exists(),
        mo.md(f"**Base introuvable** : `{DB_PATH}`. Lancer `make rebuild`."),
    )

    _con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        _cols = [
            r[1] for r in _con.execute("PRAGMA table_info('nappe_pluie_daily')").fetchall()
        ]
        # Piézomètres = tout sauf la date et les colonnes de pluie.
        piezo_cols = [c for c in _cols if c != "date" and not c.startswith("rr")]
        # Fenêtres de cumul disponibles, déduites des colonnes rr_<n>d.
        rr_windows = sorted(
            int(c[3:-1]) for c in _cols if c.startswith("rr_") and c.endswith("d")
        )
        db_start, db_end = _con.execute(
            "SELECT MIN(date), MAX(date) FROM nappe_pluie_daily"
        ).fetchone()
    finally:
        _con.close()
    return db_end, db_start, piezo_cols, rr_windows


@app.cell
def _(db_end, db_start, dt, mo, piezo_cols, rr_windows):
    # Par défaut : les ~6 dernières années disponibles.
    _default_start = max(db_start, db_end - dt.timedelta(days=6 * 365))
    periode = mo.ui.date_range(
        start=db_start, stop=db_end, value=(_default_start, db_end), label="Période"
    )
    piezo = mo.ui.dropdown(
        options=piezo_cols, value=piezo_cols[0], label="Piézomètre"
    )
    fenetre = mo.ui.dropdown(
        options={f"{w} jours": w for w in rr_windows},
        value=f"{rr_windows[0]} jours",
        label="Fenêtre de pluie",
    )
    seuil = mo.ui.slider(
        start=10, stop=300, value=70, step=5, label="Seuil cumul (mm)", show_value=True
    )
    mo.vstack(
        [
            mo.hstack([periode, piezo], justify="start", gap=2),
            mo.hstack([fenetre, seuil], justify="start", gap=2),
        ]
    )
    return fenetre, periode, piezo, seuil


@app.cell
def _(DB_PATH, duckdb, fenetre, periode):
    date_start, date_end = periode.value
    rr_col = f"rr_{fenetre.value}d"
    rr_label = f"RR{fenetre.value}"

    _con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        df = _con.execute(
            'SELECT * FROM nappe_pluie_daily WHERE "date" BETWEEN ? AND ? '
            'ORDER BY "date"',
            [date_start, date_end],
        ).df()
        # Épisodes HC recoupant la période, bornés à celle-ci (sinon une bande
        # déborderait et étirerait l'axe des dates).
        hc = _con.execute(
            """
            SELECT greatest(start_date, ?::DATE) AS start_date,
                   least(end_date, ?::DATE)      AS end_date,
                   label
            FROM hc_period
            WHERE end_date >= ?::DATE AND start_date <= ?::DATE
            ORDER BY start_date
            """,
            [date_start, date_end, date_start, date_end],
        ).df()
    finally:
        _con.close()
    df = df.set_index("date")
    return date_end, date_start, df, hc, rr_col, rr_label


@app.cell
def _(df, mo, piezo, rr_col, rr_label, seuil):
    _n_jours = int((df[rr_col] > seuil.value).sum())
    _prof = df[piezo.value].dropna()

    mo.stop(
        _prof.empty,
        mo.md(
            f"**Aucune mesure de nappe pour {piezo.value}** sur la période — "
            "la base contient la pluie mais pas la nappe (source Hub'eau vide ?). "
            "Relancer `make update` une fois la source rétablie."
        ),
    )

    mo.hstack(
        [
            mo.stat(
                value=f"{_n_jours}",
                label=f"Jours {rr_label} > {seuil.value} mm",
                caption=f"sur {len(df)} jours",
            ),
            mo.stat(
                value=f"{_prof.min():.2f} m",
                label="Nappe la plus haute",
                caption=str(_prof.idxmin().date()),
            ),
            mo.stat(
                value=f"{_prof.max():.2f} m",
                label="Nappe la plus basse",
                caption=str(_prof.idxmax().date()),
            ),
        ],
        justify="start",
        gap=2,
    )
    return


@app.cell
def _(df, hc, piezo, plt, rr_col, rr_label, seuil):
    def _plot():
        fig, ax = plt.subplots(figsize=(11, 4.5), constrained_layout=True)

        # Périodes « hors de contrôle » du réseau EU, en fond.
        for i, (_, ev) in enumerate(hc.iterrows()):
            ax.axvspan(
                ev["start_date"], ev["end_date"], color="red", alpha=0.15,
                zorder=0, label="Hors de contrôle" if i == 0 else None,
            )

        serie = df[piezo.value].dropna()
        if len(serie) > 0:
            ax.plot(serie.index, serie.values, color="#0066cc", linewidth=1.1,
                    label=f"Nappe {piezo.value}")
        ax.invert_yaxis()  # profondeur : vers le bas = nappe plus basse
        ax.set_ylabel("Prof. nappe (m)", color="#0066cc")
        ax.set_title(f"{piezo.value} vs cumul de pluie {rr_label}")
        if len(hc) or len(serie):
            ax.legend(loc="upper right", fontsize=9)

        ax2 = ax.twinx()
        rr = df[rr_col].dropna()
        ax2.fill_between(rr.index, 0, rr.values, alpha=0.2, color="green")
        ax2.axhline(seuil.value, color="orange", linestyle="--", linewidth=0.9)
        ax2.set_ylabel(f"{rr_label} (mm)", color="green")
        ax2.set_ylim(bottom=0)
        return fig

    _plot()
    return


@app.cell
def _(mo):
    mo.md("""
    ## Agrégats annuels (SQL sur DuckDB)

    La requête tourne directement sur la base, sans passer par pandas.
    """)
    return


@app.cell
def _(DB_PATH, date_end, date_start, duckdb, piezo, rr_col, seuil):
    def _annuel():
        # piezo.value et rr_col viennent des colonnes de la base, pas d'une
        # saisie libre.
        col = piezo.value
        con = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            return con.execute(
                f"""
                SELECT
                    year("date")              AS annee,
                    round(avg("{col}"), 2)    AS nappe_moy_m,
                    round(min("{col}"), 2)    AS nappe_haute_m,
                    round(max("{col}"), 2)    AS nappe_basse_m,
                    round(sum(rr), 0)         AS pluie_totale_mm,
                    count(*) FILTER (WHERE "{rr_col}" > ?) AS jours_au_dessus_seuil
                FROM nappe_pluie_daily
                WHERE "date" BETWEEN ? AND ?
                GROUP BY annee
                ORDER BY annee
                """,
                [seuil.value, date_start, date_end],
            ).df()
        finally:
            con.close()

    _annuel()
    return


@app.cell
def _(mo):
    mo.md("""
    ## Analyses bactériologiques par point

    Extrêmes d'*E. coli* et d'entérocoques (UFC/100 mL) sur la période choisie,
    depuis `analyse_bacterio` (portail Enki).

    La colonne `*_max_cens` indique comment lire le maximum : `=` valeur exacte,
    `>` **plafond de quantification atteint** (le vrai maximum est plus élevé,
    typiquement `>2419.6` en Colilert), `<` sous la limite de détection.
    """)
    return


@app.cell
def _(DB_PATH, date_end, date_start, duckdb, mo):
    def _par_point():
        con = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            out = con.execute(
                """
                SELECT point,
                       count(ecoli)                     AS n,
                       min(ecoli)                       AS ecoli_min,
                       max(ecoli)                       AS ecoli_max,
                       arg_max(ecoli_censure, ecoli)    AS ecoli_max_cens,
                       arg_max(date_prelevement, ecoli) AS jour_ecoli_max,
                       min(entero)                      AS entero_min,
                       max(entero)                      AS entero_max,
                       arg_max(entero_censure, entero)  AS entero_max_cens
                FROM analyse_bacterio
                WHERE date_prelevement BETWEEN ? AND ?
                GROUP BY point
                HAVING count(ecoli) > 0
                ORDER BY ecoli_max DESC
                """,
                [date_start, date_end],
            ).df()
        finally:
            con.close()
        if out.empty:
            return mo.md(
                "**Aucune analyse sur la période.** Récupérer les exports Enki :\n"
                "`uv run python scripts/fetch_enki.py --all`, puis `make update`."
            )
        return out

    _par_point()
    return


@app.cell
def _(mo):
    mo.md("""
    ### Contexte pluie / nappe le jour du pic de contamination

    Pour chaque point, le jour où *E. coli* est maximal, replacé dans son
    contexte : cumuls de pluie, profondeur de nappe, et appartenance à un
    épisode « hors de contrôle ». C'est l'unité d'analyse utile — comparer des
    médianes HC/hors-HC mélange les saisons et les programmes de prélèvement.
    """)
    return


@app.cell
def _(DB_PATH, date_end, date_start, duckdb, mo):
    def _contexte_pics():
        con = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            out = con.execute(
                """
                WITH pics AS (
                    SELECT point,
                           arg_max(date_prelevement, ecoli) AS jour,
                           max(ecoli)                       AS ecoli_max,
                           arg_max(ecoli_censure, ecoli)    AS cens
                    FROM analyse_bacterio
                    WHERE date_prelevement BETWEEN ? AND ?
                    GROUP BY point
                    HAVING count(ecoli) > 0
                )
                SELECT p.point, p.jour, p.ecoli_max, p.cens,
                       round(d.rr_7d, 1)   AS rr_7d,
                       round(d.rr_28d, 1)  AS rr_28d,
                       round(d."Blagon", 2)    AS blagon,
                       round(d."Piraillan", 2) AS piraillan,
                       EXISTS (
                           SELECT 1 FROM hc_period h
                           WHERE p.jour BETWEEN h.start_date AND h.end_date
                       ) AS en_hc
                FROM pics p
                LEFT JOIN nappe_pluie_daily d ON d."date" = p.jour
                ORDER BY p.ecoli_max DESC
                """,
                [date_start, date_end],
            ).df()
        finally:
            con.close()
        if out.empty:
            return mo.md("**Aucune analyse sur la période.**")
        return out

    _contexte_pics()
    return


if __name__ == "__main__":
    app.run()

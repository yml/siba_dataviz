import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    import duckdb
    import matplotlib.pyplot as plt

    from siba.data.config import DB_PATH

    return DB_PATH, duckdb, mo, plt


@app.cell
def _(DB_PATH, mo):
    mo.md(f"""
    # Nappe + pluie — exploration réactive

    Les données viennent de la base DuckDB `{DB_PATH}` (table `nappe_pluie_daily`,
    alimentée par `siba.data`). Aucun cache CSV, aucun appel réseau : le notebook
    lit la base en lecture seule.

    Si la base n'existe pas encore : `make rebuild` (ou `make update`).

    Bouger un curseur recalcule uniquement les cellules qui en dépendent.
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
        # Colonnes de piézomètres = tout sauf la date et les colonnes de pluie.
        _cols = [
            r[1] for r in _con.execute("PRAGMA table_info('nappe_pluie_daily')").fetchall()
        ]
        piezo_cols = [c for c in _cols if c != "date" and not c.startswith("rr")]
        annee_min, annee_max = _con.execute(
            "SELECT year(MIN(date)), year(MAX(date)) FROM nappe_pluie_daily"
        ).fetchone()
    finally:
        _con.close()
    return annee_max, annee_min, piezo_cols


@app.cell
def _(annee_max, annee_min, mo, piezo_cols):
    annee_debut = mo.ui.slider(
        start=annee_min,
        stop=annee_max,
        value=max(annee_min, annee_max - 6),
        step=1,
        label="Année de début",
        show_value=True,
    )
    piezo = mo.ui.dropdown(
        options=piezo_cols, value=piezo_cols[0], label="Piézomètre"
    )
    seuil_rr7 = mo.ui.slider(
        start=20, stop=120, value=70, step=5, label="Seuil RR7 (mm)", show_value=True
    )
    mo.hstack([annee_debut, piezo, seuil_rr7], justify="start", gap=2)
    return annee_debut, piezo, seuil_rr7


@app.cell
def _(DB_PATH, annee_debut, duckdb):
    date_min = f"{annee_debut.value}-01-01"
    _con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        df = _con.execute(
            'SELECT * FROM nappe_pluie_daily WHERE "date" >= ? ORDER BY "date"',
            [date_min],
        ).df()
    finally:
        _con.close()
    df = df.set_index("date")
    return date_min, df


@app.cell
def _(df, mo, piezo, seuil_rr7):
    _n_jours = int((df["rr_7d"] > seuil_rr7.value).sum())
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
                label=f"Jours RR7 > {seuil_rr7.value} mm",
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
def _(df, piezo, plt, seuil_rr7):
    def _plot():
        fig, ax = plt.subplots(figsize=(11, 4.5), constrained_layout=True)

        serie = df[piezo.value].dropna()
        if len(serie) > 0:
            ax.plot(serie.index, serie.values, color="#0066cc", linewidth=1.1)
        ax.invert_yaxis()  # profondeur : vers le bas = nappe plus basse
        ax.set_ylabel("Prof. nappe (m)", color="#0066cc")
        ax.set_title(f"{piezo.value} vs précipitations glissantes 7 j")

        ax2 = ax.twinx()
        rr7 = df["rr_7d"].dropna()
        ax2.fill_between(rr7.index, 0, rr7.values, alpha=0.2, color="green")
        ax2.axhline(seuil_rr7.value, color="orange", linestyle="--", linewidth=0.9)
        ax2.set_ylabel("RR7 (mm)", color="green")
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
def _(DB_PATH, date_min, duckdb, piezo, seuil_rr7):
    def _annuel():
        # piezo.value vient des colonnes de la base, pas d'une saisie libre.
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
                    count(*) FILTER (WHERE rr_7d > ?) AS jours_au_dessus_seuil
                FROM nappe_pluie_daily
                WHERE "date" >= ?
                GROUP BY annee
                ORDER BY annee
                """,
                [seuil_rr7.value, date_min],
            ).df()
        finally:
            con.close()

    _annuel()
    return


if __name__ == "__main__":
    app.run()

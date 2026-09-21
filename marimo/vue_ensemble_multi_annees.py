import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    import duckdb
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    from siba.data.config import DB_PATH

    return DB_PATH, duckdb, mdates, mo, pd, plt


@app.cell
def _(DB_PATH, mo):
    mo.md(f"""
    # Vue d'ensemble multi-années — nappe + pluie

    Un sous-graphe par année : la profondeur de nappe (axe gauche, inversé) et le
    cumul de pluie sur 7 jours RR7 (axe droit). Les bandes rouges marquent les
    périodes « hors de contrôle » (HC) du réseau EU.

    **Provenance des données** — nappe : [Hub'eau piézométrie](https://hubeau.eaufrance.fr/page/api-piezometrie)
    (stations ADES [Blagon 08262X0023/F](https://ades.eaufrance.fr/Fiche/PointEau?code=08262X0023/F),
    [Piraillan 08257X0086/F](https://ades.eaufrance.fr/Fiche/PointEau?code=08257X0086/F)) ;
    pluie : [Météo-France données ouvertes](https://meteo.data.gouv.fr/) (poste
    Cap-Ferret 33236002). Détail des champs : `DATA_DICTIONARY.md`.

    Base locale : `{DB_PATH}` — tables `nappe_pluie_daily` et `hc_period`.
    La table journalière démarre en 2015 (`DAILY_START`) ; l'épisode HC 2014
    n'apparaît donc pas ici.
    """)
    return


@app.cell
def _(DB_PATH, duckdb, pd):
    con = duckdb.connect(str(DB_PATH), read_only=True)
    daily = con.execute(
        'SELECT "date", "Blagon", "Piraillan", rr_7d '
        'FROM nappe_pluie_daily ORDER BY "date"'
    ).df()
    hc = con.execute(
        "SELECT start_date, end_date, label FROM hc_period ORDER BY start_date"
    ).df()
    con.close()

    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.set_index("date")
    hc["start_date"] = pd.to_datetime(hc["start_date"])
    hc["end_date"] = pd.to_datetime(hc["end_date"])
    return daily, hc


@app.cell
def _(daily, hc, mdates, plt):
    # Séries de nappe (profondeur) et leurs couleurs — ordre fixe.
    nappe_cols = ["Blagon", "Piraillan"]
    colors_nappe = ["#0066cc", "#cc6600"]
    seuil_rr7 = 70  # seuil SIBA (mm / 7 j)

    years_list = sorted(set(daily.index.year))
    n_years = len(years_list)
    n_cols = 3
    n_rows = (n_years + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(20, 4 * n_rows), sharex=False)
    axes_flat = axes.flatten()

    for i, year in enumerate(years_list):
        ax = axes_flat[i]
        df_year = daily.loc[daily.index.year == year]

        # Nappe (axe gauche, inversé : nappe haute = peu profonde = en haut)
        for j, col in enumerate(nappe_cols):
            data = df_year[col].dropna()
            if len(data) > 0:
                ax.plot(
                    data.index,
                    data.values,
                    color=colors_nappe[j % len(colors_nappe)],
                    linewidth=1.2,
                    label=col,
                )
        ax.invert_yaxis()
        ax.set_ylabel("Prof. nappe (m)", fontsize=8)

        # RR7 (axe droit)
        ax2 = ax.twinx()
        rr7 = df_year["rr_7d"].dropna()
        if len(rr7) > 0:
            ax2.fill_between(rr7.index, 0, rr7.values, alpha=0.2, color="green")
            ax2.plot(rr7.index, rr7.values, color="green", linewidth=0.8, alpha=0.7)
        ax2.axhline(
            y=seuil_rr7, color="orange", linestyle="--", linewidth=0.8, alpha=0.5
        )
        ax2.set_ylabel("RR7 (mm)", fontsize=8, color="green")
        ax2.set_ylim(bottom=0)

        # Périodes « hors de contrôle » (bandes rouges), depuis hc_period
        for _, ev in hc.iterrows():
            if ev["start_date"].year == year or ev["end_date"].year == year:
                ax.axvspan(
                    max(ev["start_date"], df_year.index.min()),
                    min(ev["end_date"], df_year.index.max()),
                    alpha=0.15,
                    color="red",
                )

        ax.set_title(str(year), fontsize=12, fontweight="bold")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.tick_params(axis="x", labelsize=7)

    # Masquer les axes vides
    for k in range(n_years, len(axes_flat)):
        axes_flat[k].set_visible(False)

    # Légende commune (nappe)
    handles, labels = axes_flat[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=len(nappe_cols),
        fontsize=10,
        bbox_to_anchor=(0.5, 1.01),
    )
    fig.suptitle(
        f"Nappes phréatiques et précipitations — Bassin d'Arcachon "
        f"({years_list[0]}–{years_list[-1]})",
        fontsize=16,
        fontweight="bold",
        y=1.03,
    )
    fig.tight_layout()
    fig
    return


@app.cell
def _(mo):
    mo.md("""
    ## Nuages cumul de pluie vs profondeur de nappe

    Matrice de nuages de points : une ligne par fenêtre de cumul de pluie
    (RR7 / RR14 / RR28 / RR56), une colonne par piézomètre. Chaque point est un
    jour ; abscisse = cumul de pluie, ordonnée = profondeur de nappe (axe inversé,
    nappe haute en haut). Les points **rouges** sont les jours « hors de contrôle »
    (`in_hc` de `v_nappe_pluie_events`, toutes périodes confondues).

    Élargir la fenêtre (7 → 56 j) resserre la relation nappe/pluie ; les jours HC
    se regroupent en haut (nappe haute) et à droite (cumuls élevés).
    """)
    return


@app.cell
def _(DB_PATH, duckdb, plt):
    def _scatter():
        con = duckdb.connect(str(DB_PATH), read_only=True)
        ev = con.execute(
            'SELECT "Blagon", "Piraillan", rr_7d, rr_14d, rr_28d, rr_56d, in_hc '
            "FROM v_nappe_pluie_events"
        ).df()
        con.close()

        windows = [("rr_7d", "RR7"), ("rr_14d", "RR14"),
                   ("rr_28d", "RR28"), ("rr_56d", "RR56")]
        piezos = ["Blagon", "Piraillan"]

        fig, axes = plt.subplots(len(windows), len(piezos), figsize=(13, 18))
        for r, (wcol, wlabel) in enumerate(windows):
            for c, pz in enumerate(piezos):
                ax = axes[r][c]
                sub = ev.dropna(subset=[wcol, pz])
                normal = sub[~sub["in_hc"]]
                hc_pts = sub[sub["in_hc"]]
                ax.scatter(
                    normal[wcol], normal[pz], c="steelblue", alpha=0.4,
                    s=22, edgecolors="none", label="Hors épisode",
                )
                ax.scatter(
                    hc_pts[wcol], hc_pts[pz], c="red", alpha=0.85,
                    s=46, edgecolors="darkred", zorder=5, label="Hors de contrôle",
                )
                ax.set_xlabel(f"Cumul {wlabel} (mm)", fontsize=10)
                ax.set_ylabel("Prof. nappe (m)", fontsize=10)
                ax.set_title(f"{pz} — {wlabel}", fontsize=11, fontweight="bold")
                ax.invert_yaxis()
                ax.grid(True, alpha=0.25)
                if r == 0 and c == len(piezos) - 1:
                    ax.legend(fontsize=9)
        fig.suptitle(
            "Cumuls de pluie (7/14/28/56 j) vs profondeur de nappe — "
            "rouge = réseau hors de contrôle",
            fontsize=14, fontweight="bold", y=1.005,
        )
        fig.tight_layout()
        return fig

    _scatter()
    return


if __name__ == "__main__":
    app.run()

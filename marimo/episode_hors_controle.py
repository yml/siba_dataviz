import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    import numpy as np
    import pandas as pd
    import duckdb
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import seaborn as sns
    from scipy import stats

    from siba.db.config import DB_PATH

    plt.style.use("seaborn-v0_8-whitegrid")
    return DB_PATH, duckdb, mdates, mo, np, pd, plt, sns, stats


@app.cell
def _(mo):
    mo.md("""
    # Épisode « hors de contrôle » — nappe vs pluie

    Version réactive inspirée de `notebooks/analyse_nappe_pluie_2026.ipynb`, lisant
    `siba.duckdb` (`v_nappe_pluie_events` + `hc_period`).

    Choisir un épisode « hors de contrôle » (HC) du réseau EU ci-dessous : les
    graphiques (timelines, superposition, nuage) et la comparaison statistique
    (boxplots + Mann-Whitney) se recalculent pour la fenêtre sélectionnée.

    **ECPP vs ECPM** — si les infiltrations étaient météoriques (ECPM), le réseau
    reviendrait à la normale peu après l'arrêt des pluies ; si elles viennent de la
    nappe (ECPP), la surcharge dure tant que la nappe est haute. Le nuage RR7 ↔
    nappe et l'écart des médianes aident à trancher.
    """)
    return


@app.cell
def _(DB_PATH, duckdb, pd):
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute(
        'SELECT "date", "Blagon", "Piraillan", rr AS "RR", rr_7d AS "RR7", in_hc '
        "FROM v_nappe_pluie_events ORDER BY \"date\""
    ).df()
    episodes = con.execute(
        "SELECT start_date, end_date, label FROM hc_period ORDER BY start_date"
    ).df()
    con.close()

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    episodes["start_date"] = pd.to_datetime(episodes["start_date"])
    episodes["end_date"] = pd.to_datetime(episodes["end_date"])

    NAPPE_COLS = ["Blagon", "Piraillan"]
    return NAPPE_COLS, df, episodes


@app.cell
def _(episodes, mo):
    labels = list(episodes["label"])
    episode = mo.ui.dropdown(
        options=labels, value=labels[-1], label="Épisode « hors de contrôle »"
    )
    margin = mo.ui.slider(
        1, 6, value=3, step=1, label="Marge de contexte (mois)", show_value=True
    )
    mo.hstack([episode, margin], justify="start", gap=2)
    return episode, margin


@app.cell
def _(episode, episodes, margin, pd):
    _row = episodes[episodes["label"] == episode.value].iloc[0]
    hc_start = _row["start_date"]
    hc_end = _row["end_date"]
    _off = pd.DateOffset(months=int(margin.value))
    ctx_start = hc_start - _off
    ctx_end = hc_end + _off
    return ctx_end, ctx_start, hc_end, hc_start


@app.cell
def _(NAPPE_COLS, ctx_end, ctx_start, df, hc_end, hc_start, mdates, plt):
    def _plot():
        d = df.loc[ctx_start:ctx_end]
        colors = ["#0066cc", "#cc6600"]
        fig, axes = plt.subplots(len(NAPPE_COLS), 1, figsize=(14, 7), sharex=True)
        for ax, (col, color) in zip(axes, zip(NAPPE_COLS, colors)):
            s = d[col].dropna()
            ax.plot(s.index, s.values, color=color, linewidth=1.5, label=col)
            ax.axvspan(hc_start, hc_end, alpha=0.15, color="red",
                       label="Hors de contrôle")
            ax.set_ylabel("Prof. nappe (m)", fontsize=11)
            ax.set_title(f"Piézomètre {col}", fontsize=12, fontweight="bold")
            ax.invert_yaxis()
            ax.legend(loc="upper right")
            ax.grid(True, alpha=0.3)
        axes[-1].set_xlabel("Date", fontsize=11)
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        fig.suptitle("Timeline nappe — épisode sélectionné", fontsize=14,
                     fontweight="bold", y=1.01)
        fig.tight_layout()
        return fig

    _plot()
    return


@app.cell
def _(ctx_end, ctx_start, df, hc_end, hc_start, mdates, plt):
    def _plot():
        d = df.loc[ctx_start:ctx_end]
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.bar(d.index, d["RR"].fillna(0), width=1, alpha=0.5,
               color="steelblue", label="Pluie journalière (RR)")
        ax.plot(d.index, d["RR7"], color="darkblue", linewidth=2,
                label="Cumul 7 jours (RR7)")
        ax.axhline(70, color="orange", linestyle="--", linewidth=1.5,
                   label="Seuil SIBA (70 mm/7j)")
        ax.axvspan(hc_start, hc_end, alpha=0.15, color="red",
                   label="Hors de contrôle")
        ax.set_ylabel("Précipitation (mm)", fontsize=11)
        ax.set_title("Timeline pluie — Cap-Ferret", fontsize=13, fontweight="bold")
        ax.legend(loc="upper right")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        fig.tight_layout()
        return fig

    _plot()
    return


@app.cell
def _(NAPPE_COLS, ctx_end, ctx_start, df, hc_end, hc_start, plt):
    def _plot():
        d = df.loc[ctx_start:ctx_end]
        colors = ["#0066cc", "#cc6600"]
        fig, ax1 = plt.subplots(figsize=(14, 6))
        for col, color in zip(NAPPE_COLS, colors):
            s = d[col].dropna()
            ax1.plot(s.index, s.values, color=color, linewidth=1.5, label=f"Nappe {col}")
        ax1.set_ylabel("Profondeur nappe (m)", fontsize=11, color="#0066cc")
        ax1.invert_yaxis()
        ax1.tick_params(axis="y", labelcolor="#0066cc")

        ax2 = ax1.twinx()
        ax2.plot(d.index, d["RR7"], color="green", linewidth=2, alpha=0.7, label="RR7")
        ax2.axhline(70, color="orange", linestyle="--", linewidth=1, alpha=0.7)
        ax2.set_ylabel("Cumul 7 jours (mm)", fontsize=11, color="green")
        ax2.tick_params(axis="y", labelcolor="green")

        ax1.axvspan(hc_start, hc_end, alpha=0.15, color="red", label="Hors de contrôle")
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")
        ax1.set_title("Superposition nappe + RR7", fontsize=13, fontweight="bold")
        fig.tight_layout()
        return fig

    _plot()
    return


@app.cell
def _(NAPPE_COLS, df, hc_end, hc_start, plt):
    def _plot():
        dd = df.dropna(subset=["RR7"]).copy()
        dd["sel_hc"] = (dd.index >= hc_start) & (dd.index <= hc_end)
        fig, axes = plt.subplots(1, len(NAPPE_COLS), figsize=(14, 5))
        for ax, col in zip(axes, NAPPE_COLS):
            sub = dd.dropna(subset=[col])
            normal = sub[~sub["sel_hc"]]
            hc = sub[sub["sel_hc"]]
            ax.scatter(normal["RR7"], normal[col], c="steelblue", alpha=0.4,
                       s=26, edgecolors="none", label="Hors épisode")
            ax.scatter(hc["RR7"], hc[col], c="red", alpha=0.85, s=52,
                       edgecolors="darkred", zorder=5, label="Épisode sélectionné")
            ax.set_xlabel("Cumul 7 jours RR7 (mm)", fontsize=11)
            ax.set_ylabel("Profondeur nappe (m)", fontsize=11)
            ax.set_title(col, fontsize=12, fontweight="bold")
            ax.invert_yaxis()
            ax.grid(True, alpha=0.25)
            ax.legend()
        fig.suptitle("RR7 vs profondeur de nappe (record complet, épisode en rouge)",
                     fontsize=14, fontweight="bold", y=1.02)
        fig.tight_layout()
        return fig

    _plot()
    return


@app.cell
def _(NAPPE_COLS, df, hc_end, hc_start, np, plt, sns):
    def _plot():
        a = df.copy()
        a["periode"] = np.where(
            (a.index >= hc_start) & (a.index <= hc_end),
            "Hors de contrôle", "Normal",
        )
        variables = NAPPE_COLS + ["RR7"]
        palette = {"Normal": "steelblue", "Hors de contrôle": "red"}
        fig, axes = plt.subplots(1, len(variables), figsize=(5 * len(variables), 5))
        for ax, var in zip(axes, variables):
            data = a[[var, "periode"]].dropna()
            sns.boxplot(data=data, x="periode", y=var, hue="periode",
                        palette=palette, legend=False, ax=ax)
            ax.set_ylabel("Profondeur nappe (m)" if var in NAPPE_COLS
                          else "Cumul 7j (mm)", fontsize=11)
            ax.set_xlabel("")
            ax.set_title(var, fontsize=12, fontweight="bold")
            if var in NAPPE_COLS:
                ax.invert_yaxis()
        fig.suptitle("Épisode « hors de contrôle » vs reste du record",
                     fontsize=14, fontweight="bold", y=1.02)
        fig.tight_layout()
        return fig

    _plot()
    return


@app.cell
def _(NAPPE_COLS, df, hc_end, hc_start, mo, np, stats):
    def _table():
        a = df.copy()
        a["periode"] = np.where(
            (a.index >= hc_start) & (a.index <= hc_end),
            "Hors de contrôle", "Normal",
        )
        rows = []
        for var in NAPPE_COLS + ["RR7"]:
            data = a[[var, "periode"]].dropna()
            g_hc = data[data["periode"] == "Hors de contrôle"][var]
            g_no = data[data["periode"] == "Normal"][var]
            if len(g_hc) > 1 and len(g_no) > 1:
                u, p = stats.mannwhitneyu(g_hc, g_no, alternative="two-sided")
                rows.append(
                    f"| {var} | {g_hc.median():.2f} | {g_no.median():.2f} "
                    f"| {u:.0f} | {p:.4f} | {'Oui' if p < 0.05 else 'Non'} |"
                )
        head = (
            "| Variable | Médiane HC | Médiane Normal | U | p-value | Signif. (5%) |\n"
            "|---|---|---|---|---|---|\n"
        )
        return mo.md(
            "### Test de Mann-Whitney U (épisode vs reste)\n\n"
            + head + "\n".join(rows)
            + "\n\np < 0.05 ⇒ distributions significativement différentes."
        )

    _table()
    return


@app.cell
def _(mo):
    mo.md("""
    ## Risque joint : nappe (Blagon) × pluie (RR7)

    Part de jours « hors de contrôle » (`in_hc`, tout le record) selon la profondeur
    de nappe Blagon **et** le cumul de pluie 7 jours, en grille 2D. Nappe haute en
    haut, pluie croissante vers la droite ; les cellules de moins de 5 jours sont
    masquées. Le risque se concentre en **haut à droite** (nappe haute + pluie
    élevée) : une nappe haute est nécessaire, la pluie amplifie.
    """)
    return


@app.cell
def _(df, pd, plt, sns):
    def _heat():
        d = df.dropna(subset=["Blagon", "RR7"]).copy()
        depth_edges = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]
        rr7_edges = [0, 20, 40, 60, 80, 100, 120, 160]
        d["dbin"] = pd.cut(d["Blagon"], depth_edges)
        d["rbin"] = pd.cut(d["RR7"], rr7_edges)
        g = d.groupby(["dbin", "rbin"], observed=False)["in_hc"]
        prob = (g.mean() * 100).unstack().sort_index(ascending=True)
        cnt = g.count().unstack().sort_index(ascending=True)

        fig, ax = plt.subplots(figsize=(11, 7))
        sns.heatmap(
            prob, mask=cnt < 5, annot=True, fmt=".0f", cmap="Reds",
            vmin=0, vmax=100, linewidths=0.5, linecolor="white",
            annot_kws={"fontsize": 9},
            cbar_kws={"label": "P(hors de contrôle) %"}, ax=ax,
        )
        ax.set_xlabel("Cumul pluie 7 jours RR7 (mm)", fontsize=11)
        ax.set_ylabel("Profondeur nappe Blagon (m) — haut = nappe haute", fontsize=11)
        ax.set_title(
            "Risque « hors de contrôle » : nappe (Blagon) × pluie (RR7)\n"
            "(cellules < 5 jours masquées ; % = part de jours HC)",
            fontsize=13, fontweight="bold",
        )
        fig.tight_layout()
        return fig

    _heat()
    return


if __name__ == "__main__":
    app.run()

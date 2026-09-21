import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    import duckdb
    import math
    import plotly.express as px

    from html import escape as escape_html

    from siba.data.config import DB_PATH

    return DB_PATH, duckdb, escape_html, math, mo, px


@app.cell
def _(DB_PATH, mo):
    mo.md(f"""
    # Carte des points chauds — *E. coli*

    Un cercle par point de prélèvement, positionné sur ses coordonnées réelles.
    Taille et couleur suivent le **maximum annuel** d'*E. coli* (UFC/100 mL) :
    c'est la queue de distribution qui signale les épisodes de pollution.

    Source : `analyse_bacterio` dans `{DB_PATH}` (portail Enki). Les mesures
    chiffrées commencent en **2014** ; 2012 et 2013 ne contiennent que des
    prélèvements sans résultat exploitable.

    Seuls les points dépassant le **seuil d'affichage** sont tracés (900
    UFC/100 mL par défaut) : la carte montre les points chauds, pas
    l'ensemble du réseau de surveillance. Les tableaux plus bas, eux,
    restent complets.

    L'échelle de couleur est **logarithmique**, du bleu (seuil) au rouge
    (maximum toutes années confondues). Son plafond est figé : un cercle
    rouge en 2016 et un cercle rouge en 2026 valent la même chose. Sans
    cela, faire glisser le curseur comparerait des échelles différentes.
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
        # Les coordonnées sont stables par point (vérifié : aucun point n'a
        # deux couples lat/lon), any_value est donc sans risque ici.
        agg = _con.execute(
            """
            SELECT annee,
                   point,
                   any_value(latitude)              AS lat,
                   any_value(longitude)             AS lon,
                   count(ecoli)                     AS n,
                   max(ecoli)                       AS ecoli_max,
                   arg_max(ecoli_censure, ecoli)    AS cens,
                   arg_max(date_prelevement, ecoli) AS jour_max,
                   round(median(ecoli), 1)          AS ecoli_med,
                   count(*) FILTER (WHERE ecoli > 2000) AS n_sup_2000,
                   log10(max(ecoli))                AS log_max
            FROM analyse_bacterio
            WHERE ecoli IS NOT NULL
            GROUP BY annee, point
            ORDER BY annee, ecoli_max DESC
            """
        ).df()
    finally:
        _con.close()

    mo.stop(
        agg.empty,
        mo.md(
            "**Aucune analyse bactério en base.** Récupérer les exports Enki :\n"
            "`uv run python scripts/fetch_enki.py --all`, puis `make update`."
        ),
    )
    return (agg,)


@app.cell
def _(agg, mo):
    annees = sorted(agg["annee"].unique().tolist())
    annee = mo.ui.slider(
        steps=annees, value=annees[-1], label="Année", show_value=True
    )
    # Uniquement des fonds Carto : le style "open-street-map" de plotly tape
    # directement sur tile.openstreetmap.org, ce que la politique d'usage
    # d'OSM interdit — les tuiles reviennent en « access blocked ».
    fond = mo.ui.dropdown(
        options={
            "Clair (Carto Positron)": "carto-positron",
            "Sombre (Carto Dark Matter)": "carto-darkmatter",
            "Routier (Carto Voyager)": "carto-voyager",
            "Sans fond": "white-bg",
        },
        value="Clair (Carto Positron)",
        label="Fond de carte",
    )
    seuil = mo.ui.slider(
        steps=[100, 250, 500, 900, 1000, 2000, 5000],
        value=900,
        label="Seuil d'affichage (UFC/100 mL)",
        show_value=True,
    )
    mo.vstack(
        [
            mo.hstack([annee, fond], justify="start", gap=2),
            seuil,
        ]
    )
    return annee, fond, seuil


@app.cell
def _(agg, annee, escape_html, fond, math, mo, px, seuil):
    # Hauteur unique pour la figure ET l'iframe. Si les deux divergent,
    # l'iframe affiche une barre de défilement.
    HAUTEUR = 520

    def _carte():
        an = agg[
            (agg["annee"] == annee.value) & (agg["ecoli_max"] > seuil.value)
        ]
        if an.empty:
            return mo.md(
                f"**Aucun point au-dessus de {seuil.value:,} UFC/100 mL en "
                f"{annee.value}.** Baisser le seuil.".replace(",", " ")
            )

        # Le bas d'échelle suit le seuil, le haut reste celui de TOUTES les
        # années : une couleur donnée représente la même concentration quelle
        # que soit l'année affichée.
        cmin, cmax = math.log10(seuil.value), agg["log_max"].max()

        fig = px.scatter_map(
            an,
            lat="lat",
            lon="lon",
            size="log_max",
            color="log_max",
            range_color=[cmin, cmax],
            # Bleu → rouge. On ne passe jamais par un ton clair : sur fond
            # de carte clair, un milieu d'échelle blanc rendrait invisibles
            # les valeurs intermédiaires. La saturation reste haute de bout
            # en bout, seule la teinte se déplace du froid vers le chaud.
            color_continuous_scale=[
                "#2c5fd4", "#6a4fc4", "#9a41ab",
                "#c33787", "#dc3a5c", "#e4402f", "#c1121f",
            ],
            size_max=26,
            # Centre = milieu de la boîte englobante, pas la moyenne : la
            # moyenne est tirée vers le sud-est par les points de la Leyre.
            zoom=10.0,
            center={
                "lat": (agg["lat"].min() + agg["lat"].max()) / 2,
                "lon": (agg["lon"].min() + agg["lon"].max()) / 2,
            },
            map_style=fond.value,
            hover_name="point",
            custom_data=["ecoli_max", "cens", "jour_max", "ecoli_med", "n",
                         "n_sup_2000"],
            height=HAUTEUR,
        )
        fig.update_traces(
            # Les points du fond de bassin se recouvrent : sans semi-opacité,
            # le cercle du dessus masque purement et simplement ses voisins.
            marker={"opacity": 0.78},
            hovertemplate=(
                "<b>%{hovertext}</b><br>"
                "Max : %{customdata[1]}%{customdata[0]:,.0f} UFC/100 mL"
                " le %{customdata[2]|%d/%m/%Y}<br>"
                "Médiane : %{customdata[3]:,.0f}<br>"
                "%{customdata[4]} prélèvements, dont %{customdata[5]} > 2 000"
                "<extra></extra>"
            )
        )
        # Échelle log : on réétiquette la barre avec les vraies concentrations.
        _ticks = [
            t for t in range(math.ceil(cmin), math.floor(cmax) + 1)
        ]
        fig.update_layout(
            title={
                "text": f"<i>Escherichia coli</i> max {annee.value}",
                "x": 0.01,
                "xanchor": "left",
                "font": {"size": 16},
            },
            # Le titre a besoin de place en haut ; les autres marges restent
            # nulles pour que la carte occupe toute la largeur.
            margin={"l": 0, "r": 0, "t": 38, "b": 0},
            coloraxis_colorbar={
                "title": "E. coli max<br>(UFC/100 mL)",
                # Crans aux puissances de 10 contenues dans l'échelle
                # courante : le bas bouge avec le seuil choisi.
                "tickvals": _ticks,
                "ticktext": [f"{10 ** t:,.0f}".replace(",", " ") for t in _ticks],
            },
        )
        # Rendu dans une iframe plutôt que renvoi direct de la figure.
        # Quand on change `map_style`, marimo met la figure à jour en place
        # et MapLibre perd les couches de données : la carte se repeint,
        # correctement stylée, mais vide. Une iframe dont le contenu change
        # force un remontage complet, donc un tracé neuf.
        page = fig.to_html(include_plotlyjs="cdn", full_html=True)
        # Sans cela, les marges par défaut du <body> ajoutent ~16 px sous la
        # figure et l'iframe se met à défiler.
        page = page.replace(
            "</head>", "<style>html,body{margin:0;padding:0;overflow:hidden}"
            "</style></head>", 1)
        # `srcdoc` plutôt que mo.iframe : celui-ci publie le HTML comme
        # fichier virtuel servi sur /@file/…. À chaque réexécution l'ancien
        # est supprimé alors que le navigateur le redemande encore, d'où un
        # 404 en pleine réponse et une pile d'erreurs côté serveur. Intégré
        # en srcdoc, le document vit dans la page : rien à resservir, et le
        # changement de contenu force quand même un remontage complet.
        return mo.Html(
            f'<iframe srcdoc="{escape_html(page, quote=True)}" '
            f'style="width:100%;height:{HAUTEUR}px;border:0" '
            f'loading="lazy"></iframe>'
        )

    _carte()
    return


@app.cell
def _(agg, annee, mo, seuil):
    def _stats():
        an = agg[agg["annee"] == annee.value]
        pire = an.loc[an["ecoli_max"].idxmax()]
        n_affiches = int((an["ecoli_max"] > seuil.value).sum())
        return mo.hstack(
            [
                mo.stat(
                    value=f"{len(an)}",
                    label="Points suivis",
                    caption=f"{int(an['n'].sum())} prélèvements",
                ),
                mo.stat(
                    value=f"{n_affiches}",
                    label="Points sur la carte",
                    caption=f"max > {seuil.value:,} UFC".replace(",", " "),
                ),
                mo.stat(
                    value=f"{pire['ecoli_max']:,.0f}".replace(",", " "),
                    label="Pire mesure",
                    caption=f"{pire['point']} — {pire['jour_max']:%d/%m/%Y}",
                ),
                mo.stat(
                    value=f"{int(an['n_sup_2000'].sum())}",
                    label="Dépassements > 2 000",
                    caption=f"sur {int(an['n'].sum())} prélèvements",
                ),
            ],
            justify="start",
            gap=2,
        )

    _stats()
    return


@app.cell
def _(mo):
    mo.md("""
    ## Classement de l'année

    Les points de l'année sélectionnée, du plus au moins contaminé.
    `cens` vaut `>` quand le laboratoire a atteint son plafond de
    quantification : la vraie valeur est alors **supérieure** au maximum affiché.
    """)
    return


@app.cell
def _(agg, annee):
    agg[agg["annee"] == annee.value][
        ["point", "n", "ecoli_med", "ecoli_max", "cens", "jour_max", "n_sup_2000"]
    ].reset_index(drop=True)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Points chauds récurrents

    Un point isolé peut déraper une fois. Ce qui compte pour cibler le réseau,
    c'est le point qui dérape **année après année** : nombre d'années où le
    maximum a dépassé 2 000 UFC/100 mL, et pire mesure jamais relevée.
    """)
    return


@app.cell
def _(agg):
    def _recurrents():
        base = (
            agg.assign(depasse=agg["ecoli_max"] > 2000)
            .groupby("point", as_index=False)
            .agg(
                annees_suivi=("annee", "count"),
                annees_sup_2000=("depasse", "sum"),
                pire_max=("ecoli_max", "max"),
            )
        )
        # L'année du pire maximum, pas celle de la première ligne du groupe.
        quand = (
            agg.loc[agg.groupby("point")["ecoli_max"].idxmax(), ["point", "annee"]]
            .rename(columns={"annee": "pire_annee"})
        )
        return (
            base.merge(quand, on="point")
            .sort_values(["annees_sup_2000", "pire_max"], ascending=False)
            .reset_index(drop=True)
        )

    _recurrents()
    return


if __name__ == "__main__":
    app.run()

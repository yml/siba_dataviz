import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    import duckdb
    import math
    import plotly.express as px
    from plotly.subplots import make_subplots

    from html import escape as escape_html

    from siba.data.config import DB_PATH, PIEZOMETERS

    return (
        DB_PATH,
        PIEZOMETERS,
        duckdb,
        escape_html,
        make_subplots,
        math,
        mo,
        px,
    )


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


@app.cell
def _(mo):
    mo.md("""
    ## Nappe et *E. coli* dans le temps

    En haut, la profondeur du piézomètre choisi (axe inversé : nappe haute en
    haut). En bas, chaque prélèvement *E. coli* des points sélectionnés, en
    échelle **logarithmique**. Les deux panneaux partagent l'axe des dates.
    Les valeurs censurées ont leur propre symbole : ▲ pour `>` (plafond du
    laboratoire, la vraie valeur est supérieure), ▼ pour `<` (sous le seuil
    de détection).
    """)
    return


@app.cell
def _(DB_PATH, PIEZOMETERS, duckdb):
    _con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        ecoli_pts = _con.execute(
            """
            SELECT point, date_prelevement AS date, ecoli, ecoli_censure AS cens
            FROM analyse_bacterio
            WHERE ecoli IS NOT NULL
            ORDER BY point, date_prelevement
            """
        ).df()
        # Mesures brutes (depuis 2010) plutôt que nappe_pluie_daily (2015 →) :
        # les premiers résultats E. coli datent de 2014.
        nappe_brute = _con.execute(
            "SELECT code_bss, date_mesure AS date, profondeur_nappe "
            "FROM nappe_mesure ORDER BY date_mesure"
        ).df()
    finally:
        _con.close()
    # Colonne courte (Blagon, Biganos…) → code BSS du piézomètre.
    CODE_PIEZO = {p["col"]: p["code_bss"] for p in PIEZOMETERS}
    return CODE_PIEZO, ecoli_pts, nappe_brute


@app.cell
def _(CODE_PIEZO, ecoli_pts, mo):
    _points = sorted(ecoli_pts["point"].unique().tolist())
    _defaut = [p for p in ("0302-LEBETEY", "0407-LEMASSURAT", "0805-RDB") if p in _points]
    piezo_ecoli = mo.ui.dropdown(
        options=list(CODE_PIEZO),
        value="Biganos" if "Biganos" in CODE_PIEZO else list(CODE_PIEZO)[0],
        label="Piézomètre",
    )
    points_ecoli = mo.ui.multiselect(
        options=_points, value=_defaut, label="Points de prélèvement"
    )
    mo.hstack([piezo_ecoli, points_ecoli], justify="start", gap=2)
    return piezo_ecoli, points_ecoli


@app.cell
def _(
    CODE_PIEZO,
    ecoli_pts,
    make_subplots,
    mo,
    nappe_brute,
    piezo_ecoli,
    points_ecoli,
):
    mo.stop(
        not points_ecoli.value,
        mo.md("Choisir au moins un point de prélèvement."),
    )

    def _figure():
        # Couleur fixe par point : sa place dans la liste complète des points,
        # pour qu'un point garde sa couleur quand la sélection change. Les
        # trois points par défaut ont des teintes réservées, bien distinctes.
        palette = ["#0066cc", "#cc6600", "#8a3ffc", "#1f9e89", "#d4237a",
                   "#6b8e23", "#b8860b", "#5f6b7a", "#e4402f", "#008b8b"]
        reserves = {"0302-LEBETEY": "#d4237a", "0407-LEMASSURAT": "#1f9e89",
                    "0805-RDB": "#cc6600"}
        tous = sorted(ecoli_pts["point"].unique())
        libres = [c for c in palette if c not in reserves.values()]
        couleur = {p: reserves.get(p, libres[i % len(libres)])
                   for i, p in enumerate(tous)}

        sel = ecoli_pts[ecoli_pts["point"].isin(points_ecoli.value)]
        debut, fin = sel["date"].min(), sel["date"].max()
        code = CODE_PIEZO[piezo_ecoli.value]
        nappe = nappe_brute[
            (nappe_brute["code_bss"] == code)
            & (nappe_brute["date"] >= debut)
            & (nappe_brute["date"] <= fin)
        ]

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
            row_heights=[0.35, 0.65],
        )
        fig.add_scatter(
            x=nappe["date"], y=nappe["profondeur_nappe"], mode="lines",
            line={"color": "#5f6b7a", "width": 1.5},
            name=f"Nappe {piezo_ecoli.value}",
            hovertemplate="%{x|%d/%m/%Y} : %{y:.2f} m<extra></extra>",
            row=1, col=1,
        )
        for p in points_ecoli.value:
            d = sel[sel["point"] == p]
            # « = » : valeur exacte ; « > » / « < » : censurée.
            cens = d["cens"].fillna("=")
            symbole = {">": "triangle-up", "<": "triangle-down"}
            fig.add_scatter(
                x=d["date"], y=d["ecoli"], mode="lines+markers", name=p,
                line={"color": couleur[p], "width": 1},
                marker={
                    "color": couleur[p], "size": 7,
                    "symbol": [symbole.get(c, "circle") for c in cens],
                },
                customdata=cens.replace("=", ""),
                hovertemplate=(f"<b>{p}</b><br>%{{x|%d/%m/%Y}} : "
                               "%{customdata}%{y:,.0f} UFC/100 mL<extra></extra>"),
                row=2, col=1,
            )
        fig.update_yaxes(title_text="Profondeur (m)", autorange="reversed",
                         row=1, col=1)
        fig.update_yaxes(title_text="E. coli (UFC/100 mL)", type="log",
                         row=2, col=1)
        fig.update_layout(
            height=620, hovermode="x unified",
            title={"text": f"Nappe {piezo_ecoli.value} et <i>E. coli</i>",
                   "x": 0.01, "xanchor": "left"},
            legend={"orientation": "h", "y": -0.08},
            margin={"l": 60, "r": 20, "t": 50, "b": 40},
        )
        return fig

    _figure()
    return


if __name__ == "__main__":
    app.run()

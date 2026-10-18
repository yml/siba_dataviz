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

    # Mêmes couleurs que le notebook STEP / nappe.
    C_STEP = "#eb6834"
    C_NAPPE = "#2a78d6"
    C_PLUIE = "#1baf7a"
    return (
        C_NAPPE,
        C_PLUIE,
        C_STEP,
        DB_PATH,
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
    # Postes de pompage et nappe

    Le classeur des postes de pompage 2025 donne, pour chaque poste et chaque
    mois, les heures de fonctionnement des pompes. Quand des eaux claires
    parasites entrent dans le réseau, les pompes tournent plus longtemps :
    les heures sont la meilleure trace de ces apports dans ce fichier (la
    puissance des pompes, elle, ne varie pas avec la saison). On utilise la
    vue nettoyée `postes_pompage_mois_clean` de `refere.duckdb`.

    La nappe de référence est par défaut celle de Blagon, pour toutes les
    communes. Le sélecteur ci-dessous la remplace par Piraillan (Lège) ou
    Biganos dans tout le notebook : profils, corrélations, TAUSSAT GARE et
    graphiques. Piraillan suit les mêmes variations que Blagon (corrélation
    journalière de 0,83) mais avec une amplitude quatre fois plus faible ;
    Biganos, dans la même nappe que Blagon, le suit de près. La Teste n'est
    pas proposé : le classeur ne couvre que les communes de la rive nord.
    Le lien entre le débit de la STEP de Biganos et la nappe est étudié dans
    le notebook `step_biganos_nappe.py`.
    """)
    return


@app.cell
def _(mo):
    nappe_ref = mo.ui.dropdown(
        options=["Blagon", "Piraillan", "Biganos"],
        value="Blagon",
        label="Piézomètre de référence",
    )
    nappe_ref
    return (nappe_ref,)


@app.cell
def _(DB_PATH, REFERE_DB, REFERE_DIR, duckdb, mo, nappe_ref):
    mo.stop(
        not REFERE_DB.exists(),
        mo.md(
            f"**Base des classeurs SIBA introuvable** : `{REFERE_DB}`.\n\n"
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
        pp_mois = _con.execute(
            """
            SELECT commune, poste, month(mois) AS m, day(last_day(mois)) AS nj,
                   heures, kwh, volume_m3, heures_clean, volume_m3_clean
            FROM postes_pompage_mois_clean
            """
        ).df()
        # Contexte mensuel : nappe choisie et pluie au pluviomètre de la STEP.
        # nappe_ref.value vient d'une liste fermée, pas d'une saisie libre.
        contexte_mois = _con.execute(
            f"""
            SELECT month(s.date)                            AS m,
                   round(median(n."{nappe_ref.value}"), 2) AS nappe_m,
                   round(sum(s.pluie_mm))     AS pluie_mm,
                   sum(s.q_eau_brute_m3j)     AS volume_step_m3
            FROM step_biganos_jour s
            JOIN siba.nappe_pluie_daily n USING (date)
            GROUP BY 1
            ORDER BY 1
            """
        ).df()
    finally:
        _con.close()
    return contexte_mois, pp_mois


@app.cell
def _(contexte_mois, pp_mois):
    # TAUSSAT GARE (Lanton), le plus gros poste du réseau : ses heures sont
    # fausses six mois sur douze, mais les erreurs vont par paires qui se
    # compensent (février/mars, mai/juin, août/septembre). La somme de chaque
    # paire reste juste : on la répartit entre les deux mois au prorata des
    # kWh, puis des volumes (deux compteurs indépendants), et on garde la
    # moyenne des deux répartitions.
    _t = pp_mois[pp_mois["poste"] == "TAUSSAT GARE"].set_index("m").sort_index()
    _h = _t["heures"].copy()
    for _a, _b in [(2, 3), (5, 6), (8, 9)]:
        _tot = _t.loc[_a, "heures"] + _t.loc[_b, "heures"]
        _part = (
            _t.loc[_a, "kwh"] / (_t.loc[_a, "kwh"] + _t.loc[_b, "kwh"])
            + _t.loc[_a, "volume_m3"] / (_t.loc[_a, "volume_m3"] + _t.loc[_b, "volume_m3"])
        ) / 2
        _h.loc[_a] = round(_tot * _part)
        _h.loc[_b] = round(_tot * (1 - _part))

    taussat = (
        _t.assign(heures_reconstituees=_h)
        .join(contexte_mois.set_index("m"))
        .assign(
            volume_jour_m3=lambda x: (x["volume_m3"] / x["nj"]).round(),
            m3_par_heure=lambda x: (x["volume_m3"] / x["heures_reconstituees"]).round(),
            part_step_pct=lambda x: (100 * x["volume_m3"] / x["volume_step_m3"]).round(),
        )
        .reset_index()
    )

    # Table des postes avec les heures corrigées : la vue nettoyée, sauf pour
    # TAUSSAT GARE où l'on prend les heures reconstituées.
    pp_corr = pp_mois.merge(
        taussat[["m", "heures_reconstituees"]].assign(poste="TAUSSAT GARE"),
        on=["poste", "m"], how="left",
    )
    pp_corr["h"] = pp_corr["heures_reconstituees"].fillna(pp_corr["heures_clean"])
    pp_corr.loc[pp_corr["poste"] == "TAUSSAT GARE", "h"] = pp_corr["heures_reconstituees"]
    return pp_corr, taussat


@app.cell
def _(contexte_mois, np, pd, pp_corr):
    # Indicateurs par poste. Heures ramenées à un nombre par jour (les mois
    # n'ont pas la même longueur), puis comparées à la base de septembre-
    # octobre (nappe basse, hors pic touristique).
    _HIVER, _BASE = [1, 2, 12], [9, 10]
    _NAPPE_HAUTE = [1, 2, 3, 4, 5, 12]
    _d = pp_corr.merge(contexte_mois[["m", "nappe_m"]], on="m")
    _d["hj"] = _d["h"] / _d["nj"]
    _d["vj"] = _d["volume_m3_clean"] / _d["nj"]

    _lignes = []
    for (_c, _p), _g in _d.groupby(["commune", "poste"]):
        _g = _g.set_index("m")
        # Juillet-août exclus de la corrélation : la population estivale
        # gonfle les heures sans rapport avec la nappe.
        _hors_ete = _g.drop([7, 8], errors="ignore").dropna(subset=["hj"])
        if len(_hors_ete) < 8 or _g["h"].sum() < 50:
            continue
        if _g.loc[_BASE + _HIVER, "hj"].isna().any():
            continue
        _base = _g.loc[_BASE, "hj"].mean()
        if _base <= 0:
            continue
        _vb = _g.loc[_BASE, "vj"].mean()
        _vh = _g.loc[_NAPPE_HAUTE, "vj"]
        _lignes.append({
            "commune": _c,
            "poste": _p,
            "spearman_nappe": round(_hors_ete["hj"].corr(_hors_ete["nappe_m"], method="spearman"), 2),
            "heures_hiver_x": round(_g.loc[_HIVER, "hj"].mean() / _base, 2),
            "novembre_x": round(_g.loc[11, "hj"] / _base, 2) if pd.notna(_g.loc[11, "hj"]) else None,
            "decembre_x": round(_g.loc[12, "hj"] / _base, 2),
            "ete_x": round(_g.loc[[7, 8], "hj"].mean() / _base, 2),
            "volume_exces_m3": (
                round(float(((_vh - _vb) * _g.loc[_NAPPE_HAUTE, "nj"]).sum()), -2)
                if pd.notna(_vb) and _vh.notna().all() else np.nan
            ),
        })
    pp_profils = pd.DataFrame(_lignes)

    def _profil(x):
        _nov = x["novembre_x"] if x["novembre_x"] is not None else np.nan
        if x["spearman_nappe"] <= -0.6 and x["heures_hiver_x"] >= 1.3 and x["decembre_x"] > _nov:
            return "nappe"
        if _nov >= 1.3 and _nov >= x["decembre_x"]:
            return "pluie"
        if x["ete_x"] >= 1.5 and x["heures_hiver_x"] < 1.3:
            return "été (tourisme)"
        return "peu sensible"

    pp_profils["profil"] = pp_profils.apply(_profil, axis=1)
    return (pp_profils,)


@app.cell
def _(mo):
    # Couleurs du classeur du SIBA : orange = postes en cascade sur le
    # collecteur principal, jaune = postes qui injectent les effluents des
    # communes dans le collecteur. Pointillés = position non confirmée.
    _schema = """
    flowchart LR
        BOURGEON["BOURGEON<br/>Lège"]
        JDB["JANE DE BOY<br/>Lège"]
        BREM["BREMONTIER<br/>Arès"]
        PDA["PORT D'ARES<br/>Arès"]
        STB["ST BRICE<br/>Arès"]
        AG["ARES GARE<br/>Arès"]
        BETEY["BETEY<br/>Andernos"]
        COULIN["COULIN_2<br/>Andernos"]
        MARCHE["MARCHE<br/>Andernos"]
        MASSURAT["MASSURAT<br/>Andernos"]
        P52["POINT 52<br/>Lanton"]
        VP["VIEUX PORT<br/>Lanton"]
        TG["TAUSSAT GARE<br/>Lanton"]
        CASSY["PORT DE CASSY<br/>Lanton"]
        PDM["PLACE DU MARCHE<br/>Audenge"]
        AUTRES["Biganos, sud de Lanton…<br/>(hors classeur)"]
        STEP[("STEP de Biganos")]

        BOURGEON --> JDB
        JDB ==> AG
        BREM --> AG
        PDA --> AG
        STB --> AG
        AG ==> TG
        BETEY --> TG
        COULIN --> TG
        MARCHE --> TG
        MASSURAT --> TG
        P52 -.-> TG
        VP -.-> TG
        TG ==> STEP
        CASSY --> STEP
        PDM --> STEP
        AUTRES --> STEP

        classDef cascade fill:#FFC000,stroke:#7a5c00,color:#000
        classDef injection fill:#FFFF00,stroke:#7a7a00,color:#000
        classDef incertain fill:#FFFF00,stroke:#7a7a00,color:#000,stroke-dasharray:4 3
        classDef step fill:#2a78d6,stroke:#1a4f91,color:#fff
        classDef autre fill:#f0efec,stroke:#9a9893,color:#000,stroke-dasharray:4 3
        class JDB,AG,TG cascade
        class BOURGEON,BREM,PDA,STB,BETEY,COULIN,MARCHE,MASSURAT,CASSY,PDM injection
        class P52,VP incertain
        class STEP step
        class AUTRES autre
    """
    mo.vstack([
        mo.md("""
    ## Le réseau : le collecteur de ceinture

    Le collecteur principal fait le tour du Bassin : il part de
    Lège-Cap-Ferret, passe par Arès, Andernos, Lanton (Taussat est un
    quartier de Lanton) et Audenge, et arrive à la STEP de Biganos. Trois
    postes en cascade (en orange) relèvent les effluents le long du
    collecteur : JANE DE BOY, ARES GARE et TAUSSAT GARE. Les postes en
    jaune injectent les effluents de chaque commune dans le collecteur ; les
    autres postes du classeur sont en amont de ces derniers.

    Ce découpage vient du SIBA. Deux points restent à confirmer (en
    pointillés) : POINT 52 et VIEUX PORT se jettent-ils en amont de TAUSSAT
    GARE ? Le bilan des volumes ci-dessous le suggère. PORT DE CASSY est en
    aval de TAUSSAT GARE (confirmé).
    """),
        mo.mermaid(_schema),
    ])
    return


@app.cell
def _(contexte_mois, mo, pp_mois):
    # Bilan des volumes mensuels le long du collecteur (milliers de m³).
    # Volumes nettoyés ; TAUSSAT GARE a un débitmètre, ARES GARE et JANE DE
    # BOY ont des volumes probablement calculés à partir des heures.
    _inj = {
        "injections_ares": ("Arès", ["BREMONTIER", "PORT D ARES", "ST BRICE"]),
        "injections_andernos": ("Andernos", ["BETEY", "COULIN_2", "MARCHE", "MASSURAT"]),
        "point_52_vieux_port": ("Lanton", ["POINT 52", "VIEUX PORT"]),
        "port_de_cassy": ("Lanton", ["PORT DE CASSY"]),
        "place_du_marche": ("Audenge", ["PLACE DU MARCHE"]),
    }
    _v = pp_mois.pivot_table(index="m", columns="poste", values="volume_m3_clean",
                             aggfunc="sum", dropna=False)
    _b = contexte_mois.set_index("m")[["volume_step_m3"]].rename(
        columns={"volume_step_m3": "step"})
    _b["jane_de_boy"] = _v["JANE DE BOY"]
    _b["ares_gare"] = _v["ARES GARE"]
    _b["taussat_gare"] = _v["TAUSSAT GARE"]
    for _col, (_commune, _postes) in _inj.items():
        _b[_col] = _v[_postes].sum(axis=1, min_count=1)
    # Ce qui arrive à TAUSSAT GARE en plus d'ARES GARE, moins les injections
    # connues entre les deux (Andernos, et POINT 52 + VIEUX PORT s'ils sont
    # bien en amont) : proche de zéro si le bilan se ferme.
    _b["reste_avant_taussat"] = (
        _b["taussat_gare"] - _b["ares_gare"] - _b["injections_andernos"]
        - _b["point_52_vieux_port"]
    )
    _b["step_moins_taussat"] = _b["step"] - _b["taussat_gare"]
    _b["hors_classeur"] = _b["step_moins_taussat"] - _b["port_de_cassy"] - _b["place_du_marche"].fillna(0)
    bilan_collecteur = (_b / 1000).round().reset_index()

    _cols = ["m", "jane_de_boy", "injections_ares", "ares_gare", "injections_andernos",
             "point_52_vieux_port", "taussat_gare", "reste_avant_taussat",
             "port_de_cassy", "place_du_marche", "hors_classeur", "step"]

    def _k(v):
        return f"{v:,.0f}".replace(",", " ").replace("-", "−")

    _noms = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]

    _r = bilan_collecteur.set_index("m")["reste_avant_taussat"]
    _hc = bilan_collecteur.set_index("m")["hors_classeur"]
    _hc_sans_juin = _hc.drop(6)
    _mois_max = " et ".join(_noms[m - 1] for m in _hc[_hc == _hc.max()].index)

    mo.vstack([
        mo.md(f"""
    ### Bilan des volumes le long du collecteur

    Volumes mensuels en milliers de m³, de l'amont (à gauche) vers la STEP
    (à droite). Dans un collecteur, l'eau ne disparaît pas : un poste doit
    relever au moins ce qui lui arrive.

    - **ARES GARE relève parfois moins que ce qui lui arrive** (JANE DE BOY
      plus les injections d'Arès). Son volume, probablement calculé à partir
      des heures, est sous-estimé. JANE DE BOY a aussi des mois
      invraisemblables (janvier, novembre).
    - **Avant TAUSSAT GARE, le bilan se ferme à peu près** si POINT 52 et
      VIEUX PORT sont en amont : le reste vaut entre {_k(_r.drop(8).min())} et
      {_k(_r.drop(8).max())} milliers de m³ selon les mois (août exclu, le
      volume de POINT 52 y manque). Le reste le plus fort est en février, le
      mois où TAUSSAT GARE tournait presque en continu : infiltration directe
      dans le collecteur, ou ARES GARE sous-estimé.
    - **En aval de TAUSSAT GARE, PORT DE CASSY et PLACE DU MARCHE pèsent
      peu.** Il reste de {_k(_hc_sans_juin.min())} à {_k(_hc.max())} milliers
      de m³ par mois qui arrivent à la STEP par des branches absentes du
      classeur (Biganos, sud de Lanton). Le maximum est en {_mois_max}. En
      janvier, la STEP a plafonné alors que TAUSSAT GARE n'était pas
      saturé : ces branches ont beaucoup apporté. Juin est exclu de la
      fourchette : TAUSSAT GARE y représente 95 % de la STEP, une part
      douteuse.
    - PLACE DU MARCHE déclare 0 m³ de juin à décembre : compteur
      probablement arrêté.
    """),
        mo.ui.table(bilan_collecteur[_cols], selection=None, page_size=12),
    ])
    return


@app.cell
def _(
    C_NAPPE,
    C_PLUIE,
    C_STEP,
    contexte_mois,
    nappe_ref,
    plt,
    pp_corr,
    pp_profils,
):
    def _reseau():
        # Rapport heures / base de sept.-oct., médiane des postes analysés
        # (ceux du tableau des profils), mois par mois.
        _d = pp_corr.merge(pp_profils[["commune", "poste"]], on=["commune", "poste"])
        _d = _d.dropna(subset=["h"]).assign(hj=lambda x: x["h"] / x["nj"])
        _base = _d[_d["m"].isin([9, 10])].groupby(["commune", "poste"])["hj"].mean()
        _d = _d.join(_base.rename("base"), on=["commune", "poste"])
        _d = _d[_d["base"] > 0]
        _med = (_d["hj"] / _d["base"]).groupby(_d["m"]).median()

        _mois = ["jan", "fév", "mars", "avr", "mai", "juin", "juil", "août",
                 "sept", "oct", "nov", "déc"]
        fig, (ax_h, ax_p, ax_n) = plt.subplots(
            3, 1, figsize=(10, 7), sharex=True, constrained_layout=True,
            gridspec_kw={"height_ratios": [2, 1, 1.4]},
        )
        ax_h.bar(_med.index, _med.values, color=C_STEP, width=0.7)
        ax_h.axhline(1, color="#52514e", linewidth=1, linestyle="--")
        for _m in (11, 12):
            ax_h.annotate(f"× {_med[_m]:.2f}".replace(".", ","), (_m, _med[_m]),
                          xytext=(0, 3), textcoords="offset points",
                          ha="center", fontsize=9, color="#52514e")
        ax_h.set_title(f"Heures de pompage / base sept.-oct. (médiane des {len(pp_profils)} postes)",
                       loc="left", fontsize=11)
        _c = contexte_mois.set_index("m")
        ax_p.bar(_c.index, _c["pluie_mm"], color=C_PLUIE, width=0.7)
        ax_p.set_title("Pluie mensuelle à la STEP (mm)", loc="left", fontsize=11)
        ax_n.plot(_c.index, _c["nappe_m"], color=C_NAPPE, linewidth=2, marker="o")
        ax_n.invert_yaxis()
        ax_n.set_title(f"Profondeur médiane de la nappe à {nappe_ref.value} (m, axe inversé)",
                       loc="left", fontsize=11)
        ax_n.set_xticks(range(1, 13), _mois)
        for ax in (ax_h, ax_p, ax_n):
            ax.grid(axis="y", color="#e5e4e0", linewidth=0.8)
            ax.set_axisbelow(True)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
        return fig

    _reseau()
    return


@app.cell
def _(mo, pp_profils):
    _n = len(pp_profils)
    _nov = pp_profils["novembre_x"].median()
    _dec = pp_profils["decembre_x"].median()
    _dec_sup = int((pp_profils["decembre_x"] > pp_profils["novembre_x"]).sum())
    _comptes = (
        pp_profils.groupby(["commune", "profil"]).size().unstack(fill_value=0)
        .reset_index()
    )
    _top = (
        pp_profils[pp_profils["profil"] == "nappe"]
        .sort_values("volume_exces_m3", ascending=False)
        .head(15)
    )
    _pluie = pp_profils[pp_profils["profil"] == "pluie"].sort_values(
        "volume_exces_m3", ascending=False
    )

    def _x(v):
        return f"× {v:.2f}".replace(".", ",")

    mo.vstack([
        mo.md(f"""
    ## La nappe, pas la pluie

    Novembre et décembre 2025 permettent de séparer les deux effets.
    **Novembre** est le mois le plus pluvieux de l'année, avec une nappe
    encore basse : les heures de pompage restent au niveau de la base
    (**{_x(_nov)}** en médiane). **Décembre** est moins pluvieux, mais la
    nappe est remontée : les heures augmentent de **{_x(_dec)}**. Pour
    **{_dec_sup} postes sur {_n}**, décembre dépasse novembre. C'est la
    hauteur de la nappe, plus que la pluie, qui fait tourner les pompes
    l'hiver.

    ## Profil des postes

    Chaque poste est classé selon le comportement de ses heures :

    - **nappe** : heures corrélées à la nappe (Spearman ≤ −0,6, hors
      juillet-août), au moins 1,3 fois la base en hiver, et décembre au-dessus
      de novembre ;
    - **pluie** : novembre au moins 1,3 fois la base, et au-dessus de
      décembre ;
    - **été (tourisme)** : juillet-août au moins 1,5 fois la base, sans
      hausse d'hiver ;
    - **peu sensible** : aucun des cas précédents.
    """),
        mo.ui.table(_comptes, selection=None),
        mo.md("""
    ## Les postes les plus touchés par les eaux claires parasites

    Postes au profil « nappe », classés par volume en excès sur les mois de
    nappe haute (janvier à mai et décembre) par rapport au niveau de
    septembre-octobre. Les colonnes « × » donnent les heures de pompage par
    jour rapportées à cette base.

    Attention : les postes sont en cascade, l'eau relevée par un petit poste
    repasse dans les postes en aval. Les volumes en excès servent à classer
    les postes, pas à faire un total.
    """),
        mo.ui.table(_top, selection=None, page_size=15),
        mo.md("**Postes au profil « pluie »**"),
        mo.ui.table(_pluie, selection=None),
    ])
    return


@app.cell
def _(DB_PATH, duckdb, mo):
    mo.stop(not DB_PATH.exists())
    _con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        # Profondeur médiane du mois aux trois piézomètres de la rive nord et
        # de Biganos (La Teste, rive sud, n'a pas de poste dans le classeur).
        nappes_mois = _con.execute(
            """
            SELECT month("date")       AS m,
                   median("Blagon")    AS "Blagon",
                   median("Piraillan") AS "Piraillan",
                   median("Biganos")   AS "Biganos"
            FROM nappe_pluie_daily
            WHERE year("date") = 2025
            GROUP BY 1
            ORDER BY 1
            """
        ).df()
    finally:
        _con.close()
    return (nappes_mois,)


@app.cell
def _(nappes_mois, pd, pp_corr, pp_profils):
    # Mêmes règles que les profils : heures par jour, juillet-août exclus,
    # seulement les postes retenus dans pp_profils.
    _NAPPES = ["Blagon", "Piraillan", "Biganos"]
    _ORDRE = ["Lège", "Arès", "Andernos", "Lanton", "Audenge"]
    _d = (
        pp_corr.merge(pp_profils[["commune", "poste"]], on=["commune", "poste"])
        .merge(nappes_mois, on="m")
        .query("m not in [7, 8]")
        .assign(hj=lambda x: x["h"] / x["nj"])
        .dropna(subset=["hj"])
    )
    _lignes = []
    for (_c, _p), _g in _d.groupby(["commune", "poste"]):
        _lignes.append({"commune": _c, "poste": _p} | {
            _n: round(_g["hj"].corr(_g[_n], method="spearman"), 2) for _n in _NAPPES
        })
    spearman_piezos = pd.DataFrame(_lignes).dropna(subset=_NAPPES, how="all")
    # Le plus négatif gagne : les heures montent quand la nappe remonte.
    spearman_piezos["meilleur"] = spearman_piezos[_NAPPES].idxmin(axis=1)
    piezo_par_commune = (
        spearman_piezos.groupby("commune")[_NAPPES].median().round(2)
        .join(spearman_piezos.groupby("commune")["meilleur"]
              .agg(lambda s: s.value_counts().idxmax()))
        .join(spearman_piezos.groupby("commune").size().rename("postes"))
        .reindex(_ORDRE)
        .reset_index()
    )
    return (piezo_par_commune,)


@app.cell
def _(mo, nappes_mois, piezo_par_commune):
    _r = nappes_mois[["Blagon", "Piraillan", "Biganos"]].corr(method="spearman")

    def _n(v):
        return f"{v:+.2f}".replace(".", ",").replace("-", "−")

    mo.vstack([
        mo.md(f"""
    ### Quel piézomètre pour quelle commune ?

    Blagon sert de repère pour tout le réseau. Avec Piraillan (Lège) et
    Biganos, on peut tester si chaque commune suit plutôt la nappe la plus
    proche. Pour chaque poste : corrélation de Spearman entre les heures de
    pompage par jour et la profondeur médiane du mois, juillet et août exclus.
    Le tableau donne la médiane par commune et le piézomètre qui gagne le plus
    souvent.

    Prudence : dix mois seulement, et les trois nappes bougent ensemble
    (Spearman mensuel Blagon–Piraillan {_n(_r.loc["Blagon", "Piraillan"])},
    Blagon–Biganos {_n(_r.loc["Blagon", "Biganos"])}). Un écart de quelques
    centièmes entre colonnes n'a pas de sens ; seul un écart net et cohérent
    avec la géographie (Lège → Piraillan, Audenge → Biganos) en aurait un.
    """),
        mo.ui.table(piezo_par_commune, selection=None),
    ])
    return


@app.cell
def _(mo, pp_profils, taussat):
    _ts = pp_profils[pp_profils["poste"] == "TAUSSAT GARE"].iloc[0]
    _rang = int(
        pp_profils["volume_exces_m3"].rank(ascending=False)[
            pp_profils["poste"] == "TAUSSAT GARE"
        ].iloc[0]
    )
    _part = 100 * taussat["volume_m3"].sum() / taussat["volume_step_m3"].sum()

    def _fmt(v):
        return f"{v:,.0f}".replace(",", " ")

    def _x(v):
        return f"× {v:.2f}".replace(".", ",")

    mo.vstack([
        mo.md(f"""
    ## TAUSSAT GARE (Lanton)

    C'est le plus gros poste du réseau ({_fmt(taussat["volume_m3"].sum())} m³
    en 2025), mais ses heures sont fausses six mois sur douze. Les erreurs
    vont par paires qui se compensent (février/mars, mai/juin,
    août/septembre) : la somme de chaque paire reste juste. On la répartit
    entre les deux mois au prorata des kWh et des volumes. Le total
    reconstitué retombe exactement sur celui du classeur
    ({_fmt(taussat["heures_reconstituees"].sum())} h).

    Contrairement à la plupart des postes, son volume n'est pas calculé à
    partir des heures (le débit horaire varie de
    {_fmt(taussat["m3_par_heure"].min())} à
    {_fmt(taussat["m3_par_heure"].max())} m³/h) : le poste semble équipé d'un
    vrai débitmètre. Plusieurs mois dépassent 744 h, il a donc au moins deux
    pompes dont les heures s'additionnent.

    **Résultat** : profil « {_ts["profil"]} », Spearman heures/nappe
    {f"{_ts['spearman_nappe']:+.2f}".replace(".", ",").replace("-", "−")}, heures d'hiver {_x(_ts["heures_hiver_x"])}
    la base, décembre {_x(_ts["decembre_x"])} contre novembre
    {_x(_ts["novembre_x"])}. Volume en excès sur les mois de nappe haute :
    **{_fmt(_ts["volume_exces_m3"])} m³**, le {_rang}{"er" if _rang == 1 else "e"} du
    réseau. C'est d'autant plus notable que l'épisode HC de 2026 touchait
    Lanton et Taussat.

    TAUSSAT GARE est la pompe de relevage du collecteur principal qui
    alimente la STEP de Biganos (confirmé par le SIBA). Son volume représente
    **{_part:.0f} %** du volume entrant à la STEP sur l'année. Sa capacité
    pourrait donc expliquer le plafond de débit observé à la STEP vers 28 000
    à 30 000 m³/j (voir le notebook `step_biganos_nappe.py`).
    """),
        mo.ui.table(
            taussat[["m", "heures", "heures_reconstituees", "kwh", "volume_m3",
                     "volume_jour_m3", "m3_par_heure", "nappe_m", "pluie_mm",
                     "part_step_pct"]],
            selection=None, page_size=12,
        ),
    ])
    return


@app.cell
def _(taussat):
    # Nombre de pompes de TAUSSAT GARE : au moins 2 (plusieurs mois dépassent
    # 744 h). Hypothèse à confirmer par le SIBA.
    N_POMPES_TAUSSAT = 2

    # Taux de marche : part du temps où les pompes tournent, toutes pompes
    # comptées (heures de pompage / heures disponibles).
    # Capacité estimée : toutes les pompes en continu, au débit horaire
    # médian de l'année (m³ par heure de pompe).
    _q_med = float(taussat["m3_par_heure"].median())
    capacite_taussat_m3j = N_POMPES_TAUSSAT * 24 * _q_med
    marche_taussat = taussat.assign(
        heures_par_jour=lambda x: (x["heures_reconstituees"] / x["nj"]).round(1),
        taux_marche_pct=lambda x: (
            100 * x["heures_reconstituees"] / (N_POMPES_TAUSSAT * 24 * x["nj"])
        ).round(0),
        volume_sur_capacite_pct=lambda x: (
            100 * x["volume_jour_m3"] / capacite_taussat_m3j
        ).round(0),
    )
    return N_POMPES_TAUSSAT, capacite_taussat_m3j, marche_taussat


@app.cell
def _(C_STEP, N_POMPES_TAUSSAT, marche_taussat, plt):
    def _marche():
        _mois = ["jan", "fév", "mars", "avr", "mai", "juin", "juil", "août",
                 "sept", "oct", "nov", "déc"]
        fig, ax = plt.subplots(figsize=(10, 3.8), constrained_layout=True)
        ax.bar(marche_taussat["m"], marche_taussat["taux_marche_pct"],
               color=C_STEP, width=0.7)
        ax.axhline(100, color="#52514e", linewidth=1, linestyle="--")
        ax.annotate("toutes les pompes en continu", (0.6, 100), xytext=(0, 3),
                    textcoords="offset points", fontsize=9, color="#52514e")
        _max = marche_taussat.loc[marche_taussat["taux_marche_pct"].idxmax()]
        ax.annotate(f"{_max['taux_marche_pct']:.0f} %", (_max["m"], _max["taux_marche_pct"]),
                    xytext=(0, 3), textcoords="offset points", ha="center",
                    fontsize=9, color="#52514e")
        ax.set_ylim(0, 110)
        ax.set_xticks(range(1, 13), _mois)
        ax.set_title(
            f"Taux de marche de TAUSSAT GARE (%, hypothèse {N_POMPES_TAUSSAT} pompes)",
            loc="left", fontsize=11,
        )
        ax.grid(axis="y", color="#e5e4e0", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        return fig

    _marche()
    return


@app.cell
def _(N_POMPES_TAUSSAT, capacite_taussat_m3j, marche_taussat, mo):
    def _fmt(v):
        return f"{v:,.0f}".replace(",", " ")

    _max = marche_taussat.loc[marche_taussat["taux_marche_pct"].idxmax()]
    _mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]
    _dec = marche_taussat.set_index("m").loc[12]

    mo.vstack([
        mo.md(f"""
    ## Taux de marche de TAUSSAT GARE

    Le taux de marche est la part du temps où les pompes tournent. Avec
    l'hypothèse de **{N_POMPES_TAUSSAT} pompes**, il vaut 100 % quand elles
    tournent toutes en continu : le poste ne peut alors plus relever
    davantage, et le surplus doit partir ailleurs.

    En **{_mois[int(_max["m"]) - 1]} 2025**, les pompes ont tourné
    **{str(_max["heures_par_jour"]).replace(".", ",")} h par jour** en moyenne, soit un taux de
    marche de **{_max["taux_marche_pct"]:.0f} %**. Le poste a fonctionné
    presque en continu pendant tout le mois. Au débit horaire médian de
    l'année, {N_POMPES_TAUSSAT} pompes en continu relèvent environ
    **{_fmt(round(capacite_taussat_m3j, -2))} m³/j**.

    **Limites.**

    - **Tout dépend du nombre de pompes.** Avec 3 pompes, tous les taux
      seraient multipliés par 2/3.
    - **Ce sont des moyennes mensuelles.** En décembre, le taux moyen n'est
      que de {_dec["taux_marche_pct"]:.0f} %, alors que la STEP a atteint son
      débit maximal de l'année ce mois-là. Le poste peut être saturé pendant
      quelques jours d'épisode sans que la moyenne du mois le montre. Les
      débits journaliers ou horaires du poste (télégestion) permettraient de
      le vérifier.
    - **Le débit horaire varie** d'un mois à l'autre (de 278 à 561 m³ par
      heure de pompe), la capacité estimée n'est donc qu'un ordre de grandeur.
    """),
        mo.ui.table(
            marche_taussat[["m", "heures_reconstituees", "heures_par_jour",
                            "taux_marche_pct", "volume_jour_m3",
                            "volume_sur_capacite_pct", "nappe_m"]],
            selection=None, page_size=12,
        ),
    ])
    return


@app.cell
def _(DB_PATH, REFERE_DB, duckdb, nappe_ref, np, pd, taussat):
    # Débits journaliers estimés de TAUSSAT GARE (méthode proposée par le
    # SIBA) : débit journalier de la STEP × part de TAUSSAT GARE dans le
    # volume de la STEP. La part est connue par mois ; on l'interpole entre
    # les milieux de mois pour éviter une marche au 1er de chaque mois, puis
    # on renormalise pour que chaque mois retombe sur le volume du classeur.
    _con = duckdb.connect(str(REFERE_DB), read_only=True)
    try:
        _con.execute(f"ATTACH '{DB_PATH}' AS siba (READ_ONLY)")
        _j = _con.execute(
            f"""
            SELECT s.date, s.q_eau_brute_m3j AS q_step, s.pluie_mm,
                   n."{nappe_ref.value}" AS nappe_m
            FROM step_biganos_jour s
            JOIN siba.nappe_pluie_daily n USING (date)
            ORDER BY s.date
            """
        ).df()
    finally:
        _con.close()

    _j["m"] = _j["date"].dt.month
    _part = taussat.set_index("m")["volume_m3"] / _j.groupby("m")["q_step"].sum()
    _milieux = pd.to_datetime([f"2025-{_m:02d}-15" for _m in range(1, 13)])
    _j["part_taussat"] = np.interp(
        _j["date"].values.astype("int64"),
        _milieux.values.astype("int64"),
        _part.sort_index().values,
    )
    _j["q_taussat_m3j"] = _j["q_step"] * _j["part_taussat"]
    _corr = taussat.set_index("m")["volume_m3"] / _j.groupby("m")["q_taussat_m3j"].sum()
    _j["q_taussat_m3j"] = (_j["q_taussat_m3j"] * _j["m"].map(_corr)).round()
    taussat_jour = _j
    part_mensuelle_taussat = (100 * _part).round()
    return part_mensuelle_taussat, taussat_jour


@app.cell
def _(
    C_NAPPE,
    C_STEP,
    N_POMPES_TAUSSAT,
    capacite_taussat_m3j,
    mdates,
    nappe_ref,
    plt,
    taussat_jour,
):
    def _jour():
        fig, (ax_q, ax_n) = plt.subplots(
            2, 1, figsize=(11, 6), sharex=True, constrained_layout=True,
            gridspec_kw={"height_ratios": [2, 1.2]},
        )
        ax_q.plot(taussat_jour["date"], taussat_jour["q_step"], color="#9a9893",
                  linewidth=1, label="STEP de Biganos (mesuré)")
        ax_q.plot(taussat_jour["date"], taussat_jour["q_taussat_m3j"], color=C_STEP,
                  linewidth=1.8, label="TAUSSAT GARE (estimé)")
        ax_q.axhline(capacite_taussat_m3j, color="#52514e", linestyle="--", linewidth=1,
                     label=f"Capacité estimée, {N_POMPES_TAUSSAT} pompes en continu")
        ax_q.set_ylim(bottom=0)
        ax_q.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " "))
        )
        ax_q.set_title("Débit journalier (m³/j)", loc="left", fontsize=11)
        ax_q.legend(loc="upper center", fontsize=9, frameon=False, ncol=3)
        ax_n.plot(taussat_jour["date"], taussat_jour["nappe_m"], color=C_NAPPE, linewidth=2)
        ax_n.invert_yaxis()
        ax_n.set_title(f"Profondeur de la nappe à {nappe_ref.value} (m, axe inversé)",
                       loc="left", fontsize=11)
        ax_n.xaxis.set_major_locator(mdates.MonthLocator())
        ax_n.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        for ax in (ax_q, ax_n):
            ax.grid(axis="y", color="#e5e4e0", linewidth=0.8)
            ax.set_axisbelow(True)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
        return fig

    _jour()
    return


@app.cell
def _(
    N_POMPES_TAUSSAT,
    capacite_taussat_m3j,
    marche_taussat,
    mo,
    part_mensuelle_taussat,
    taussat_jour,
):
    def _fmt(v):
        return f"{v:,.0f}".replace(",", " ")

    _max = taussat_jour.loc[taussat_jour["q_taussat_m3j"].idxmax()]
    _au_dessus = taussat_jour[taussat_jour["q_taussat_m3j"] > capacite_taussat_m3j]
    # Capacité au débit horaire de février (mois le plus chargé).
    _fev = marche_taussat.set_index("m").loc[2]
    _cap_fev = N_POMPES_TAUSSAT * 24 * _fev["m3_par_heure"]
    _parts = ", ".join(
        f"{_m} : {_v:.0f} %" for _m, _v in zip(
            ["jan", "fév", "mars", "avr", "mai", "juin", "juil", "août",
             "sept", "oct", "nov", "déc"],
            part_mensuelle_taussat.sort_index().values,
        )
    )
    _jours = (
        taussat_jour.nlargest(10, "q_taussat_m3j")
        .assign(date=lambda x: x["date"].dt.date)
        [["date", "q_step", "part_taussat", "q_taussat_m3j", "nappe_m", "pluie_mm"]]
        .round(2)
    )

    mo.vstack([
        mo.md(f"""
    ## Débits journaliers estimés de TAUSSAT GARE

    Le SIBA ne dispose pas des débits journaliers de TAUSSAT GARE. Faute de
    mieux, on les estime à partir de la STEP : débit journalier de la STEP
    multiplié par la part de TAUSSAT GARE dans le volume de la STEP ce
    mois-là. Cette part varie selon les mois ({_parts}).

    **Ce que cette estimation ne peut pas montrer.** La courbe estimée a la
    même forme que celle de la STEP, à un facteur près. Si le poste
    plafonnait les jours de pointe, l'estimation ne le verrait pas : elle
    supposerait au contraire que TAUSSAT GARE suit la STEP.

    **Ce qu'elle montre quand même.** Le débit estimé monte jusqu'à
    **{_fmt(_max["q_taussat_m3j"])} m³/j** le
    {_max["date"]:%d/%m/%Y}, et dépasse la capacité estimée de
    {_fmt(round(capacite_taussat_m3j, -2))} m³/j ({N_POMPES_TAUSSAT} pompes en
    continu au débit horaire médian) pendant **{len(_au_dessus)} jours**,
    presque tous en février. Au débit horaire de février
    ({_fmt(_fev["m3_par_heure"])} m³ par heure de pompe), la capacité ne
    serait même que d'environ {_fmt(round(_cap_fev, -2))} m³/j. Un poste à
    {N_POMPES_TAUSSAT} pompes ne peut pas relever ces volumes : soit
    l'hypothèse sur le poste est fausse, soit l'estimation l'est. Trois
    explications possibles :

    1. le poste a **plus de {N_POMPES_TAUSSAT} pompes** ;
    2. sa **part du débit de la STEP baisse les jours de pointe** : le poste
       est saturé, et le surplus arrivant à la STEP vient des autres branches
       du réseau. C'est cohérent avec le plafond observé à la STEP ;
    3. son débit horaire est plus élevé les jours de pointe que la moyenne
       du mois.

    Seuls les débits journaliers réels du poste, ou son nombre de pompes et
    leur débit nominal, permettront de trancher.

    La part de juin (95 %) est étonnamment élevée et mérite d'être vérifiée.
    """),
        mo.md("**Les 10 jours de débit estimé le plus fort**"),
        mo.ui.table(_jours, selection=None),
    ])
    return


@app.cell
def _(mo):
    mo.md("""
    ## Limites et questions ouvertes

    - **Une seule année, des données mensuelles.** Un effet limité à
      quelques jours d'épisode est noyé dans la moyenne du mois.
    - **Blagon sert de repère pour toutes les communes.** Piraillan (Lège) et
      Biganos sont comparés dans « Quel piézomètre pour quelle commune ? ».
    - **Les volumes de la plupart des postes sont calculés** à partir des
      heures (débit horaire constant à 2 % près pour la majorité des postes) :
      ils n'apportent pas d'information indépendante.
    - **Questions pour le SIBA** :
        - Quelle est la capacité de TAUSSAT GARE (nombre de pompes, débit
          nominal de chacune, débit maximal du poste) ? Le calcul du taux de
          marche suppose 2 pompes. Peut-on obtenir les débits journaliers ou
          horaires du poste en 2025 ?
        - À quelle date sont relevés les compteurs des postes ? Plusieurs gros
          postes de Lège ont des heures étonnamment basses en novembre, le
          mois le plus pluvieux : les « mois » du classeur sont peut-être
          décalés par rapport au calendrier.
        - Les volumes des postes sont-ils calculés (heures × débit nominal) ?
          Le compteur de kWh mesure-t-il la pompe seule ou toute l'armoire ?
        - Peut-on obtenir les relevés bruts d'index (horamètres, débitmètres)
          pour corriger les erreurs de compteur au lieu de les masquer ?
        - POINT 52 et VIEUX PORT se jettent-ils dans le collecteur en amont
          de TAUSSAT GARE ?
        - Quels postes ou réseaux alimentent le collecteur entre Audenge et la
          STEP, et existe-t-il des volumes pour Biganos ?
        - Les volumes de JANE DE BOY et d'ARES GARE sont-ils mesurés ou
          calculés ? Pourquoi PLACE DU MARCHE (Audenge) est-il à zéro de juin
          à décembre ?
    """)
    return


if __name__ == "__main__":
    app.run()

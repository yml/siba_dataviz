"""
Fusion des séries piézométriques et pluviométriques sur un index journalier.
"""

import pandas as pd


def merge_nappe_pluie(
    nappe_data: dict[str, pd.DataFrame],
    df_meteo: pd.DataFrame,
    date_min: str | pd.Timestamp = "2015-01-01",
    date_max: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Fusionne les séries de nappe (resampling journalier + interpolation)
    avec les précipitations.

    Parameters
    ----------
    nappe_data : dict  name → DataFrame avec colonnes ``date_mesure`` et ``profondeur_nappe``
    df_meteo   : DataFrame indexé par DATE, contenant au moins RR et SLIDING_RR7
    date_min, date_max : bornes temporelles

    Returns
    -------
    DataFrame indexé par date (journalier) avec colonnes : un col par piézo + RR + SLIDING_RR7
    """
    if date_max is None:
        date_max = df_meteo.index.max()

    idx = pd.date_range(date_min, date_max, freq="D")
    df_merged = pd.DataFrame(index=idx)
    df_merged.index.name = "date"

    for name, df in nappe_data.items():
        if len(df) == 0:
            continue
        ts = df.set_index("date_mesure")["profondeur_nappe"]
        ts_daily = ts.resample("D").mean()
        ts_daily = ts_daily.interpolate(method="time", limit=3)
        col_name = name.split("(")[0].strip()
        df_merged[col_name] = ts_daily

    pluie_cols = [c for c in ["RR", "SLIDING_RR7"] if c in df_meteo.columns]
    df_merged = df_merged.join(df_meteo[pluie_cols])

    return df_merged

import pandas as pd
import numpy as np
import pgeocode
import joblib
from pathlib import Path
from sklearn.neighbors import BallTree
import streamlit as st
from sklearn.metrics.pairwise import haversine_distances
from data_loader import load_Auftragsdaten

ZFILL = {"DE": 5, "AT": 4, "CH": 4}
R_EARTH_KM = 6371.0

@st.cache_resource
def nomi(country: str) -> pgeocode.Nominatim:
    return pgeocode.Nominatim(country)

@st.cache_data
def build_plz_koordinaten() -> pd.DataFrame:
    frames = []

    for c, z in ZFILL.items():
        d = nomi(c)._data[["postal_code", "latitude", "longitude"]].copy()
        d["Land"] = c
        d["PLZ_HW"] = d["postal_code"].astype(str).str.strip().str.zfill(z)
        frames.append(d[["Land", "PLZ_HW", "latitude", "longitude"]].dropna().drop_duplicates(["Land", "PLZ_HW"]))
    return pd.concat(frames, ignore_index=True)

@st.cache_resource
def build_auftrag_geo_from_df(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, BallTree]:
    df = df.copy()
    df["Land"] = df["Land"].astype(str).str.strip().str.upper()
    df["PLZ_HW"] = df["PLZ_HW"].astype(str).str.strip()

    df["PLZ_HW"] = np.where(
        df["Land"].eq("DE"),
        df["PLZ_HW"].str.zfill(5),
        df["PLZ_HW"].str.zfill(4),
    )

    dach = build_plz_koordinaten()

    auftrag_geo = (
        df.groupby("Handwerker_Name", as_index=False)[["Land", "PLZ_HW"]].first()
          .merge(dach, on=["Land", "PLZ_HW"], how="left")
    )

    plz_coords = (
        dach.rename(columns={"latitude": "lat", "longitude": "lon"})
           .set_index(["Land", "PLZ_HW"])[["lat", "lon"]]
    )

    tree = BallTree(np.radians(plz_coords.to_numpy()), metric="haversine")
    return auftrag_geo, plz_coords, tree

@st.cache_resource
def get_geo_strukturen():
    cache_dir = Path(".geo_cache")
    cache_dir.mkdir(exist_ok=True)

    f_auftrag = cache_dir / "auftrag_geo.parquet"
    f_plz     = cache_dir / "plz_coords.parquet"
    f_tree    = cache_dir / "tree.joblib"
    
    if f_auftrag.exists() and f_plz.exists() and f_tree.exists():
        auftrag_geo = pd.read_parquet(f_auftrag)

        plz_coords_df = pd.read_parquet(f_plz)
        plz_coords = plz_coords_df.set_index(["Land", "PLZ_HW"])[["lat", "lon"]]

        tree = joblib.load(f_tree)
        return auftrag_geo, plz_coords, tree

    auftrag_geo, plz_coords, tree = build_auftrag_geo_from_df(load_Auftragsdaten())

    auftrag_geo.to_parquet(f_auftrag, index=False)
    plz_coords.reset_index().to_parquet(f_plz, index=False)  # Index flach speichern
    joblib.dump(tree, f_tree)

    return auftrag_geo, plz_coords, tree

def datensaetze_im_umkreis(input_plz: str, radius_km: float, country: str, auftrag_geo: pd.DataFrame, plz_coords: pd.DataFrame,tree: BallTree) -> pd.DataFrame:

    info = nomi(country).query_postal_code(input_plz)
    if pd.isna(info.latitude) or pd.isna(info.longitude):
        raise ValueError(f"PLZ {input_plz} nicht gefunden (Land: {country})")

    coord0 = np.radians([[info.latitude, info.longitude]])
    idx = tree.query_radius(coord0, r=radius_km / R_EARTH_KM)[0]

    nearby_pairs = plz_coords.iloc[idx].reset_index()[["Land", "PLZ_HW"]].drop_duplicates()
    result = auftrag_geo.merge(nearby_pairs, on=["Land", "PLZ_HW"], how="inner")

    if result.empty:
        return result

    d_km = haversine_distances(coord0, np.radians(result[["latitude", "longitude"]].to_numpy()))[0] * R_EARTH_KM
    result = result.assign(
        **{
            "Entfernung in km": d_km,
            "Entfernungsscore": pd.cut(
                d_km, bins=[0, 5, 20, 40, 60, 80, 101],
                labels=["100", "80", "60", "40", "20", "0"],
                include_lowest=True,
            )
        }
    ).sort_values("Entfernung in km")

    return result
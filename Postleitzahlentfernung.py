import pandas as pd
import numpy as np
import pgeocode
from sklearn.neighbors import BallTree
import streamlit as st
from sklearn.metrics.pairwise import haversine_distances
from data_loader import load_Auftragsdaten

@st.cache_data
def build_plz_koordinaten() -> pd.DataFrame:
    countries = ["DE", "AT", "CH"]
    frames = []

    for c in countries:
        nomi = pgeocode.Nominatim(c)
        df_country = nomi._data.copy()

        df_country["country_code"] = c
        df_country["postal_code"] = df_country["postal_code"].astype(str).str.strip()
        if c == "DE":
            df_country["postal_code"] = df_country["postal_code"].str.zfill(5)
        else:  # AT/CH
            df_country["postal_code"] = df_country["postal_code"].str.zfill(4)

        df_country = df_country[["country_code","postal_code","latitude","longitude",]]

        df_country = df_country.rename(columns={"postal_code": "PLZ_HW","country_code": "Land"})
        
        df_country = (df_country.dropna(subset=["latitude", "longitude"]).drop_duplicates(subset=["Land","PLZ_HW"], keep="first"))

        frames.append(df_country)

    df_dach = pd.concat(frames, ignore_index=True)
    return df_dach


@st.cache_resource
def build_auftrag_geo_from_df(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, BallTree]:
    df = df.copy()
    df["Land"] = df["Land"].astype(str).str.strip().str.upper()

    df["PLZ_HW"] = df.apply(lambda r: str(r["PLZ_HW"]).strip().zfill(5) if r["Land"] == "DE" else str(r["PLZ_HW"]).strip().zfill(4), axis=1)
    df_dach = build_plz_koordinaten()

    auftrag = (df.groupby("Handwerker_Name", as_index=False).agg({"Land": "first", "PLZ_HW": "first"}))
    auftrag_geo = auftrag.merge(df_dach, on=["Land", "PLZ_HW"], how="left")

    plz_coords = (df_dach[["Land", "PLZ_HW",  "latitude", "longitude"]].dropna().drop_duplicates(subset=["Land", "PLZ_HW"]).rename(columns={"latitude": "lat", "longitude": "lon"}).set_index(["Land", "PLZ_HW"]))

    coords_rad = np.radians(plz_coords[["lat", "lon"]].to_numpy())
    tree = BallTree(coords_rad, metric="haversine")

    return auftrag_geo, plz_coords, tree

@st.cache_resource
def get_geo_strukturen():
    df = load_Auftragsdaten()

    return build_auftrag_geo_from_df(df)

def datensaetze_im_umkreis(input_plz: str, radius_km: float, country: str, auftrag_geo: pd.DataFrame, plz_coords: pd.DataFrame,tree: BallTree,) -> pd.DataFrame:

    nomi = pgeocode.Nominatim(country)
    info = nomi.query_postal_code(input_plz)

    if pd.isna(info.latitude) or pd.isna(info.longitude):
        raise ValueError(f"PLZ {input_plz} nicht gefunden (Land: {country})")

    lat0, lon0 = info.latitude, info.longitude

    coord0 = np.radians([[lat0, lon0]])
    radius = radius_km / 6371.0

    idx = tree.query_radius(coord0, r=radius)[0]
    nearby = plz_coords.iloc[idx].reset_index()
    nearby_pairs = nearby[["Land", "PLZ_HW"]].drop_duplicates()

    result = auftrag_geo.merge(nearby_pairs, on=["Land", "PLZ_HW"], how="inner")

    if not result.empty:
        coords_target = np.radians(result[["latitude", "longitude"]].to_numpy())
        coord0_rad = coord0 

        dists_rad = haversine_distances(coord0_rad, coords_target)[0]
        dists_km = dists_rad * 6371.0
        result = result.copy()
        result["Entfernung_km"] = dists_km
        
        result = result.sort_values("Entfernung_km")
        
        labels = ["1.0","0.8","0.6","0.4","0.2","0.0"]
        bins = [0,5,20,40,60,80,1001]
        result["Entfernungsscore"] = pd.cut(result["Entfernung_km"], right=True,labels = labels, bins=bins, include_lowest=True)


    return result
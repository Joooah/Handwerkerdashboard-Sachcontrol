import pandas as pd
import numpy as np
import pgeocode
from sklearn.neighbors import BallTree
import streamlit as st
from sklearn.metrics.pairwise import haversine_distances


# --------------------------------------------------------
#  Daten laden & vorbereiten (mit Caching, damit es schnell bleibt)
# --------------------------------------------------------

@st.cache_data
def load_auftrag_data(parquet_path: str) -> pd.DataFrame:
    df = pd.read_parquet('/Users/benab/Desktop/Projekt/Auftragsdaten.parquet')

    # "-" als fehlende PLZ behandeln
    df["PLZ_HW"] = df["PLZ_HW"].replace("-", np.nan)

    # Fehlende PLZ_HW mit PLZ_SO auffüllen (falls vorhanden)
    if "PLZ_SO" in df.columns:
        df = df.fillna({"PLZ_HW": df["PLZ_SO"]})

    # Zeilen ohne PLZ entfernen
    df = df.dropna(subset=["PLZ_HW"])

    # PLZ als String
    df["PLZ_HW"] = df["PLZ_HW"].astype(str)

    return df


@st.cache_data
def build_plz_koordinaten() -> pd.DataFrame:
    countries = ["DE", "AT", "CH"]
    frames = []

    for c in countries:
        nomi = pgeocode.Nominatim(c)
        df_country = nomi._data.copy()

        df_country["country_code"] = c
        df_country["postal_code"] = df_country["postal_code"].astype(str)

        df_country = df_country[[
            "country_code",
            "postal_code",
            "latitude",
            "longitude",
        ]]

        df_country = df_country.rename(columns={"postal_code": "PLZ_HW"})

        # Gültige & eindeutige Koordinaten
        df_country = (
            df_country
            .dropna(subset=["latitude", "longitude"])
            .drop_duplicates(subset="PLZ_HW", keep="first")
        )

        frames.append(df_country)

    df_dach = pd.concat(frames, ignore_index=True)
    return df_dach


@st.cache_data
def build_auftrag_geo(parquet_path: str) -> tuple[pd.DataFrame, pd.DataFrame, BallTree]:
    # Auftragsdaten
    df = load_auftrag_data(parquet_path)

    # PLZ/Koordinaten
    df_dach = build_plz_koordinaten()

    # Pro Handwerker eine PLZ
    auftrag = (
        df.groupby("Handwerker_Name", as_index=False)
          .agg({"PLZ_HW": "first"})
    )

    # Geo-Infos dazu
    auftrag_geo = auftrag.merge(
        df_dach,
        on="PLZ_HW",
        how="left"
    )

    # PLZ-Koordinatentabelle für BallTree
    plz_coords = (
        df_dach[["PLZ_HW", "latitude", "longitude"]]
        .dropna()
        .drop_duplicates(subset="PLZ_HW")
        .rename(columns={"latitude": "lat", "longitude": "lon"})
        .set_index("PLZ_HW")
    )

    # BallTree aufbauen
    coords_rad = np.radians(plz_coords[["lat", "lon"]].to_numpy())
    tree = BallTree(coords_rad, metric="haversine")

    return auftrag_geo, plz_coords, tree


# --------------------------------------------------------
#  Funktion: Datensätze im Umkreis finden
# --------------------------------------------------------

def datensaetze_im_umkreis(
    input_plz: str,
    radius_km: float,
    country: str,
    auftrag_geo: pd.DataFrame,
    plz_coords: pd.DataFrame,
    tree: BallTree,
) -> pd.DataFrame:
    """
    input_plz : eingegebene PLZ (z.B. "80331")
    radius_km : Suchradius in km
    country   : "DE", "AT", "CH", ...
    """

    # Koordinaten der Eingabe-PLZ über pgeocode holen
    nomi = pgeocode.Nominatim(country)
    info = nomi.query_postal_code(input_plz)

    if pd.isna(info.latitude) or pd.isna(info.longitude):
        raise ValueError(f"PLZ {input_plz} nicht gefunden (Land: {country})")

    lat0, lon0 = info.latitude, info.longitude

    # Koordinate in Radianten
    coord0 = np.radians([[lat0, lon0]])

    # Radius in Radiant (Erdradius ≈ 6371 km)
    radius = radius_km / 6371.0

    # Nachbarn im Umkreis via BallTree
    idx = tree.query_radius(coord0, r=radius)[0]

    # PLZ, die im Umkreis liegen
    nearby_plz = plz_coords.iloc[idx].index.tolist()

    # Handwerker im Umkreis
    result = auftrag_geo[auftrag_geo["PLZ_HW"].isin(nearby_plz)].copy()

    # Optional: Distanz zur Eingabe-PLZ mit ausrechnen
    # (haversine Distanz für jede PLZ)
    if not result.empty:
        coords_target = np.radians(result[["latitude", "longitude"]].to_numpy())
        coord0_rad = coord0  # das ist ja schon np.radians([[lat0, lon0]])

        dists_rad = haversine_distances(coord0_rad, coords_target)[0]  # shape (n,)
        dists_km = dists_rad * 6371.0
        result = result.copy()
        result["Entfernung_km"] = dists_km
        result = result.sort_values("Entfernung_km")
        def score_aus_entfernung(dist_km):
            if dist_km <= 5:
                return 1.0
            elif dist_km <= 20:
                return 0.8
            elif dist_km <= 40:
                return 0.6
            elif dist_km <= 60:
                return 0.4
            elif dist_km <= 80:
                return 0.2
            else:
                return 0.0

        result["Score"] = result["Entfernung_km"].apply(score_aus_entfernung)





    return result


# --------------------------------------------------------
#  STREAMLIT UI
# --------------------------------------------------------

def main():
    st.title("Handwerker-Suche im Umkreis per PLZ")

    st.markdown(
        "Gib eine **PLZ**, einen **Radius (km)** und ein **Land** ein, "
        "um Handwerker im Umkreis zu finden."
    )

    # Pfad zur Parquet-Datei (bei dir anpassen!)
    parquet_path = "/Users/benab/Desktop/Projekt/Auftragsdaten.parquet"

    with st.sidebar:
        st.header("Einstellungen")
        input_plz = st.text_input("PLZ", value="80331")
        radius_km = st.number_input("Radius (km)", min_value=1.0, max_value=200.0, value=20.0, step=1.0)
        country = st.selectbox("Land", options=["DE", "AT", "CH"], index=0)

        run_button = st.button("Suche starten")

    # Daten vorbereiten (einmalig, dank Cache)
    with st.spinner("Lade Daten und baue Geodaten auf..."):
        auftrag_geo, plz_coords, tree = build_auftrag_geo(parquet_path)

    if run_button:
        try:
            result = datensaetze_im_umkreis(
                input_plz=input_plz.strip(),
                radius_km=radius_km,
                country=country,
                auftrag_geo=auftrag_geo,
                plz_coords=plz_coords,
                tree=tree,
            )

            if result.empty:
                st.warning("Keine Handwerker im angegebenen Radius gefunden.")
            else:
                st.success(f"{len(result)} Handwerker im Umkreis gefunden.")
                st.dataframe(
                    result[
                        [
                            "Handwerker_Name",
                            "PLZ_HW",
                            "country_code",
                            "latitude",
                            "longitude",
                            "Entfernung_km",
                            "Score"
                        ]
                    ],
                    use_container_width=True,
                )
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Fehler bei der Berechnung: {e}")


if __name__ == "__main__":
    main()
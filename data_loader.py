import streamlit as st
import pandas as pd

@st.cache_data
def load_Auftragsdaten() -> pd.DataFrame:
    df = pd.read_parquet("/Users/benab/Desktop/Projekt/Auftragsdaten.parquet")

    df["PLZ_HW"] = (
        df["PLZ_HW"].astype(str)
        .str.replace(r"\D", "", regex=True)
        .replace("", pd.NA)
    )
    df = df.dropna(subset=["PLZ_HW"])
    
    df["Land"] = (
        df["Land"]
        .replace("-", pd.NA)
        .fillna(df["DH_ID"].map({1: "DE", 2: "AT", 4: "CH"}))
    )
    df = df[
        ~df["Handwerker_Name"].str.contains(
            r"vonovia|eigenleistung|sachcontrol|(leer)", case=False, na=False
            )
    ]

    df = df.assign(
        Gewerk_Name=df["Gewerk_Name"].replace("(leer)", "Sonstiges"),
        Schadenart_Name=df["Schadenart_Name"].replace({
            "Betriebsunterbrechnung": "Betriebsunterbrechung",
            "-": "Sonstiges"
        }),
        Falltyp_Name=df["Falltyp_Name"].replace("-", "Sonstiges"),
    )
    
    df = df[
        (df["Forderung_Netto"] >= 0) &
        (df["Einigung_Netto"] >= 0) &
        ~(
            (df["Forderung_Netto"] >= 1000) &
            (df["Einigung_Netto"] >= 2 * df["Forderung_Netto"])
        )
    ]

    return df

@st.cache_data
def load_Positionsdaten():
    return pd.read_parquet("/Users/benab/Desktop/Projekt/Positionsdaten.parquet")
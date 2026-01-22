import os
import re
import pandas as pd

from data_loader import load_Auftragsdaten, load_Positionsdaten

BASIS_ORDNER = "/Users/benab/Desktop/Projekt"
ORDNER_GEWERK = os.path.join(BASIS_ORDNER, "Auftrags_und_Positionsdaten_Gewerk")
ORDNER_SCHADENSFALL = os.path.join(BASIS_ORDNER, "Auftrags_und_Positionsdaten_Schadensfall")
ORDNER_FALLTYP = os.path.join(BASIS_ORDNER, "Auftrags_und_Positionsdaten_Falltypen")


def make_safe(value: object) -> str:
    s = str(value)
    s = re.sub(r'[\/\\\?\*\:\|\<\>"]', "_", s)
    return s.strip()


def generate_parquet_files() -> None:
    os.makedirs(ORDNER_GEWERK, exist_ok=True)
    os.makedirs(ORDNER_SCHADENSFALL, exist_ok=True)
    os.makedirs(ORDNER_FALLTYP, exist_ok=True)

    df_auftrag = load_Auftragsdaten()
    df_pos = load_Positionsdaten()

    common_cols = [c for c in df_pos.columns if c in df_auftrag.columns and c != "KvaRechnung_ID"]

    df_pos_clean = df_pos.drop(columns=common_cols)

    merged = pd.merge(df_auftrag, df_pos_clean, on="KvaRechnung_ID", how="left")

    for gewerk, grp in merged.groupby("Gewerk_Name"):
        safe_g = make_safe(gewerk)
        pfad = os.path.join(ORDNER_GEWERK, f"{safe_g}.parquet")
        grp.to_parquet(pfad, index=False)
    
    for schadenart, grp in merged.groupby("Schadenart_Name"):
        safe_s = make_safe(schadenart)
        pfad = os.path.join(ORDNER_SCHADENSFALL, f"{safe_s}.parquet")
        grp.to_parquet(pfad, index=False)

    for (schadenart, falltyp), grp in merged.groupby(["Schadenart_Name", "Falltyp_Name"]):
        safe_s = make_safe(schadenart)
        safe_f = make_safe(falltyp)

        ordner_s = os.path.join(ORDNER_FALLTYP, safe_s)
        os.makedirs(ordner_s, exist_ok=True)

        pfad = os.path.join(ordner_s, f"{safe_f}.parquet")
        grp.to_parquet(pfad, index=False)
        
def lade_subset_auftragsdaten_gewerk(gewerk_name: str):
    safe_g = make_safe(gewerk_name)
    pfad = os.path.join(ORDNER_GEWERK, f"{safe_g}.parquet")

    df = pd.read_parquet(pfad)

    relevante_spalten = [
        "Handwerker_Name",
        "PLZ_HW",
        "Land",
        "gewerk_name",
        "Schadenart_Name",
        "Falltyp_Name",
        "Einigung_Netto",
        "Forderung_Netto"
    ]

    vorhandene = [c for c in relevante_spalten if c in df.columns]
    return df[vorhandene].copy()


def lade_subset_auftragsdaten(schadenart: str, falltyp: str | None = None):
    safe_s = make_safe(schadenart)

    if not falltyp or falltyp == "Alle":
        pfad = os.path.join(ORDNER_SCHADENSFALL, f"{safe_s}.parquet")
    else:
        safe_f = make_safe(falltyp)
        pfad = os.path.join(ORDNER_FALLTYP, safe_s, f"{safe_f}.parquet")


    df = pd.read_parquet(pfad)

    relevante_spalten = ["Handwerker_Name", "PLZ_HW", "Land", "Schadenart_Name", "Falltyp_Name", "Einigung_Netto", "Forderung_Netto"]

    vorhandene = [c for c in relevante_spalten if c in df.columns]

    return df[vorhandene].copy()

def read_first_value_from_parquet(pfad: str, possible_cols: list[str]):
    df = pd.read_parquet(pfad)
    

    for c in possible_cols:
        if c in df.columns and len(df) > 0:
            v = df[c].iloc[0]
            if pd.notna(v):
                return str(v)
    return None

def list_gewerke():
    if not os.path.isdir(ORDNER_GEWERK):
        return []

    result = set()
    for fname in os.listdir(ORDNER_GEWERK):
        if not fname.endswith(".parquet"):
            continue

        pfad = os.path.join(ORDNER_GEWERK, fname)
        val = read_first_value_from_parquet(pfad, ["gewerk", "Gewerk_Name"])
        if val:
            result.add(val)

    return sorted(result)



def list_schadensarten():

    result = set()
    for fname in os.listdir(ORDNER_SCHADENSFALL):
        if not fname.endswith(".parquet"):
            continue

        pfad = os.path.join(ORDNER_SCHADENSFALL, fname)

        val = read_first_value_from_parquet(pfad, ["schadenart_name", "Schadenart_Name"])
        if val:
            result.add(val)

    return sorted(result)


def list_falltypen_for_schadensart(schadensart: str):
    safe_s = make_safe(schadensart)
    ordner_s = os.path.join(ORDNER_FALLTYP, safe_s)

    if not os.path.isdir(ordner_s):
        return []

    result = set()
    for fname in os.listdir(ordner_s):
        if not fname.endswith(".parquet"):
            continue

        pfad = os.path.join(ordner_s, fname)
        val = read_first_value_from_parquet(pfad, ["falltyp_name", "Falltyp_Name"])
        if val:
            result.add(val)
        else:
            result.add(fname[:-8])  # fallback: Dateiname ohne .parquet

    return sorted(result)


if __name__ == "__main__":
    generate_parquet_files()
    print("Fertig.")
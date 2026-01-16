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
        
        pfad = os.path.join(ORDNER_FALLTYP, f"{safe_s}_{safe_f}.parquet")
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
        pfad = os.path.join(ORDNER_FALLTYP, f"{safe_s}_{safe_f}.parquet")

    df = pd.read_parquet(pfad)

    relevante_spalten = ["Handwerker_Name", "PLZ_HW", "Land", "Schadenart_Name", "Falltyp_Name", "Einigung_Netto", "Forderung_Netto"]

    vorhandene = [c for c in relevante_spalten if c in df.columns]

    return df[vorhandene].copy()

def list_gewerke():
    if not os.path.isdir(ORDNER_GEWERK):
        return []
    return sorted(
        fname[:-8]
        for fname in os.listdir(ORDNER_GEWERK)
        if fname.endswith(".parquet")
    )


def list_schadensarten():
    if not os.path.isdir(ORDNER_SCHADENSFALL):
        return []
    
    return sorted(fname[:-8] for fname in os.listdir(ORDNER_SCHADENSFALL)if fname.endswith(".parquet"))


def list_falltypen_for_schadensart(schadenart: str):
    safe_s = make_safe(schadenart)
    prefix = f"{safe_s}_"
    result = []

    if not os.path.isdir(ORDNER_FALLTYP):
        return []

    for fname in os.listdir(ORDNER_FALLTYP):
        if fname.startswith(prefix) and fname.endswith(".parquet"):
            falltyp = fname[len(prefix):-8]
            result.append(falltyp)

    return sorted(result)


if __name__ == "__main__":
    generate_parquet_files()
    print("Fertig.")
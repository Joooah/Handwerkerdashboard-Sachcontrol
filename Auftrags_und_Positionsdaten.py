import os
import re
import pandas as pd

from Postleitzahlentfernung import build_plz_koordinaten
from data_loader import load_Auftragsdaten, load_Positionsdaten

BASIS_ORDNER = "/Users/benab/Desktop/Projekt"

ORDNER_SCHADENSFALL = os.path.join(
    BASIS_ORDNER, "Auftrags_und_Positionsdaten_Schadensfall"
)
ORDNER_FALLTYP = os.path.join(
    BASIS_ORDNER, "Auftrags_und_Positionsdaten_Falltypen"
)

def make_safe(value: object) -> str:
    """Erlaubt fast alle Zeichen, ersetzt nur Dateisystem-Problemzeichen."""
    s = str(value)
    s = re.sub(r'[\/\\\?\*\:\|\<\>"]', "_", s)
    return s.strip()

def add_geo_to_rows(df: pd.DataFrame) -> pd.DataFrame:
    if "PLZ_HW" not in df.columns:
        raise KeyError("Spalte 'PLZ_HW' fehlt.")

    df_dach = build_plz_koordinaten()

    df_geo = df.copy()
    df_geo["PLZ_HW"] = df_geo["PLZ_HW"].astype(str)
    df_dach["PLZ_HW"] = df_dach["PLZ_HW"].astype(str)

    df_geo = df_geo.merge(
        df_dach[["PLZ_HW", "latitude", "longitude"]],
        on="PLZ_HW",
        how="left",
    )
    return df_geo


def generate_parquet_files() -> None:
    """Erzeugt Dateien in zwei Ordnern:
    - ORDNER_SCHADENSFALL: <Schadenart>.parquet
    - ORDNER_FALLTYP: <Schadenart>_Falltyp_<Falltyp>.parquet
    """

    os.makedirs(ORDNER_SCHADENSFALL, exist_ok=True)
    os.makedirs(ORDNER_FALLTYP, exist_ok=True)

    df_auftrag = load_Auftragsdaten()
    df_pos = load_Positionsdaten()

    common_cols = [
    c for c in df_pos.columns
    if c in df_auftrag.columns and c != "KvaRechnung_ID"
    ]

    df_pos_clean = df_pos.drop(columns=common_cols)

    merged = pd.merge(df_auftrag, df_pos_clean, on="KvaRechnung_ID", how="left")
    merged = add_geo_to_rows(merged)

    # prüfen
    if "Schadenart_Name" not in merged or "Falltyp_Name" not in merged:
        raise KeyError("Schadenart_Name oder Falltyp_Name fehlt.")

    #Nur Schadenarten
    for schadenart, grp in merged.groupby("Schadenart_Name"):
        safe_s = make_safe(schadenart)
        pfad = os.path.join(ORDNER_SCHADENSFALL, f"{safe_s}.parquet")
        grp.to_parquet(pfad, index=False)

    #Schadenart + Falltyp
    for (schadenart, falltyp), grp in merged.groupby(
        ["Schadenart_Name", "Falltyp_Name"]
    ):
        safe_s = make_safe(schadenart)
        safe_f = make_safe(falltyp)
        pfad = os.path.join(
            ORDNER_FALLTYP, f"{safe_s}_{safe_f}.parquet"
        )
        grp.to_parquet(pfad, index=False)


def lade_subset_auftragsdaten(schadenart: str, falltyp: str | None = None):
    safe_s = make_safe(schadenart)

    if not falltyp or falltyp == "Alle":
        pfad = os.path.join(ORDNER_SCHADENSFALL, f"{safe_s}.parquet")
    else:
        safe_f = make_safe(falltyp)
        pfad = os.path.join(
            ORDNER_FALLTYP, f"{safe_s}_Falltyp_{safe_f}.parquet"
        )

    df = pd.read_parquet(pfad)

    # reduz der spalten
    relevante_spalten = [
        "Handwerker_Name",
        "PLZ_HW",
        "Schadenart_Name",
        "Falltyp_Name",
        "Einigung_Netto",
        "Forderung_Netto",
    ]

    vorhandene = [c for c in relevante_spalten if c in df.columns]

    return df[vorhandene].copy()

def list_schadensarten():
    """Liest alle <Schadenart>.parquet aus ORDNER_SCHADENSFALL"""
    if not os.path.isdir(ORDNER_SCHADENSFALL):
        return []
    return sorted(
        fname[:-8] for fname in os.listdir(ORDNER_SCHADENSFALL)
        if fname.endswith(".parquet")
    )


def list_falltypen_for_schadensart(schadenart: str):
    """Liest alle <Schadenart>_Falltyp_<Falltyp>.parquet aus ORDNER_FALLTYP"""
    safe_s = make_safe(schadenart)
    prefix = f"{safe_s}_Falltyp_"
    result = []

    if not os.path.isdir(ORDNER_FALLTYP):
        return []

    for fname in os.listdir(ORDNER_FALLTYP):
        if fname.startswith(prefix) and fname.endswith(".parquet"):
            falltyp = fname[len(prefix):-8]
            result.append(falltyp)

    return sorted(result)


if __name__ == "__main__":
    print("Erzeuge Parquet-Dateien…")
    generate_parquet_files()

    print("Fertig.")

import re, json
from pathlib import Path
import pandas as pd
import streamlit as st
from data_loader import load_Auftragsdaten, load_Positionsdaten

BASIS_ORDNER = Path("/Users/benab/Desktop/Projekt")
ORDNER_GEWERK = BASIS_ORDNER / "Auftrags_und_Positionsdaten_Gewerk"
ORDNER_SCHADENSFALL = BASIS_ORDNER / "Auftrags_und_Positionsdaten_Schadensfall"
ORDNER_FALLTYP = BASIS_ORDNER / "Auftrags_und_Positionsdaten_Falltypen"
INDEX_FILE = BASIS_ORDNER / "index_lists.json"

SAFE_RE = re.compile(r'[\/\\\?\*\:\|\<\>"]')
RELEVANTE_SPALTEN = [
    "Handwerker_Name", "PLZ_HW", "Land",
    "Gewerk_Name", "Schadenart_Name", "Falltyp_Name",
    "Einigung_Netto", "Forderung_Netto",
]

def make_safe(x) -> str:
    return SAFE_RE.sub("_", str(x)).strip()

def load_index() -> dict:
    return json.loads(INDEX_FILE.read_text("utf-8")) if INDEX_FILE.exists() else \
        {"gewerke": [], "schadensarten": [], "falltypen_by_schadensart": {}}

def write_index(gewerke, schadensarten, falltypen_map) -> None:
    INDEX_FILE.write_text(json.dumps({
        "gewerke": sorted(set(gewerke)),
        "schadensarten": sorted(set(schadensarten)),
        "falltypen_by_schadensart": {k: sorted(set(v)) for k, v in falltypen_map.items()},
    }, ensure_ascii=False, indent=2), "utf-8")

def subset(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in RELEVANTE_SPALTEN if c in df.columns]
    return df[cols].copy()

def generate_parquet_files() -> None:
    for d in (ORDNER_GEWERK, ORDNER_SCHADENSFALL, ORDNER_FALLTYP):
        d.mkdir(parents=True, exist_ok=True)

    auftrag, pos = load_Auftragsdaten(), load_Positionsdaten()
    drop_cols = [c for c in pos.columns if c in auftrag.columns and c != "KvaRechnung_ID"]
    merged = auftrag.merge(pos.drop(columns=drop_cols), on="KvaRechnung_ID", how="left")

    gewerke, schadensarten, falltypen_map = [], [], {}
    
    def dump_groups(group_cols, out_dir: Path, collect=None):
        for key, grp in merged.groupby(group_cols):
            if (isinstance(key, tuple) and any(pd.isna(k) for k in key)) or pd.isna(key):
                continue

            if not isinstance(key, tuple):
                grp.to_parquet(out_dir / f"{make_safe(key)}.parquet", index=False)
                if collect is not None:
                    collect.append(str(key))
            else:
                s, f = map(str, key)
                falltypen_map.setdefault(s, []).append(f)
                d = out_dir / make_safe(s)
                d.mkdir(exist_ok=True)
                grp.to_parquet(d / f"{make_safe(f)}.parquet", index=False)

    dump_groups("Gewerk_Name", ORDNER_GEWERK, gewerke)
    dump_groups("Schadenart_Name", ORDNER_SCHADENSFALL, schadensarten)
    dump_groups(["Schadenart_Name", "Falltyp_Name"], ORDNER_FALLTYP)

    write_index(gewerke, schadensarten, falltypen_map)

INDEX = load_index()
GEWERKE_LISTE = INDEX["gewerke"]
SCHADENSARTEN_LISTE = INDEX["schadensarten"]
FALLTYPEN_BY_SCHADENSART = INDEX["falltypen_by_schadensart"]

@st.cache_data
def list_gewerke(): return GEWERKE_LISTE

@st.cache_data
def list_schadensarten(): return SCHADENSARTEN_LISTE

@st.cache_data
def list_falltypen_for_schadensart(s: str): return FALLTYPEN_BY_SCHADENSART.get(s, [])

def lade_subset_auftragsdaten_gewerk(gewerk: str) -> pd.DataFrame:
    return subset(pd.read_parquet(ORDNER_GEWERK / f"{make_safe(gewerk)}.parquet"))

def lade_subset_auftragsdaten(schaden: str, falltyp: str | None = None) -> pd.DataFrame:
    s = make_safe(schaden)
    p = (ORDNER_SCHADENSFALL / f"{s}.parquet") if (not falltyp or falltyp == "Alle") \
        else (ORDNER_FALLTYP / s / f"{make_safe(falltyp)}.parquet")
    return subset(pd.read_parquet(p))

if __name__ == "__main__":
    generate_parquet_files()
    print("Fertig.")
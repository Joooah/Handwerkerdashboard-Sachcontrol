import pandas as pd 
import polars as pl


def filter_handwerker_plz (df): 
    "Gibt einen DataFrame mit einzigartigen Handwerker_Namen und deren PLZ zurück."
    return (
        df[["Handwerker_Name", "PLZ_HW"]]
        .drop_duplicates(subset =  "Handwerker_Name")
        .reset_index(drop = True)
    )



# Preis Differenz Spalten in Auftragsdaten
def add_differences_cols (df):
    df = df.copy()

    df["Differenz_absolut"] = df["Forderung_Netto"] - df["Einigung_Netto"]

    df["Differenz_quotient"] = (
        df["Differenz_absolut"] / df["Forderung_Netto"]
    ).replace([float("inf"), -float("inf")], 0).fillna(0)

    df["Differenz_prozentual"] = df["Differenz_quotient"].apply(lambda x: f"{x * 100:.2f}%")

    return df


# Filter mit Preis
def filter_preis (df) : 
    df = df [[
        "Handwerker_Name", "Forderung_Netto", "Einigung_Netto",
        "Differenz_absolut", "Differenz_prozentual"
    ]]

    df = df.drop_duplicates(subset= "Handwerker_Name").reset_index(drop = True)
    return df




def filter_Dashboard (df):
    cols = [
        "Handwerker_Name", "PLZ_HW", "Gewerk_Name",
        "Schadenart_Name", "Falltyp_Name", "Differenz_quotient"
    ]

    base = df[cols].copy()

    avg_diff = (
        base.groupby(["Handwerker_Name", "Falltyp_Name"])["Differenz_quotient"]
        .mean()
        .reset_index()
        .rename(columns={"Differenz_quotient" : "Durchschnitt_Differenz_prozent"})
    )

    avg_diff["Durchschnitt_Differenz_prozent"] = avg_diff["Durchschnitt_Differenz_prozent"].apply(
        lambda x: f"{x*100:.2f}%"
    )

    dashboard = (
        base.drop_duplicates(subset=["Handwerker_Name", "Falltyp_Name"])
        .sort_values("Handwerker_Name")
        .reset_index(drop=True)
    )

    dashboard = dashboard.merge(
        avg_diff,
        on=["Handwerker_Name", "Falltyp_Name"],
        how="left"
    )

    return dashboard
   

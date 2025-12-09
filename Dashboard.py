import streamlit as st
import pandas as pd

from Zuverlässigkeit import berechne_zuverlaessigkeit

from Auftrags_und_Positionsdaten import (
    list_schadensarten,
    list_falltypen_for_schadensart,
    lade_subset_auftragsdaten
)
from Postleitzahlentfernung import (
    build_auftrag_geo_from_df,
    datensaetze_im_umkreis,
)

st.set_page_config(layout="wide")

AUFTRAGSDATEN_PATH = "/Users/benab/Desktop/Projekt/Auftragsdaten.parquet"  # ggf. anpassen


@st.cache_data
def get_geo_strukturen():
    auftrag_geo, plz_coords, tree = build_auftrag_geo_from_df(AUFTRAGSDATEN_PATH)
    return auftrag_geo, plz_coords, tree


def main():
    st.title("Handwerker-Dashboard")

    st.markdown(
        "Wähle eine **Schadensart** und optional einen **Falltyp**. "
        "Alle Daten stammen aus vorgesplitteten Parquet-Dateien."
    )

    col1, col2, col3, col4 = st.columns(4)

    #Umkreisauswahl (neue v) in Spalte 1
    with col1:
        use_umkreis = st.checkbox("Umkreissuche", value=False)
        radius_km = st.number_input(
            "Radius (km)",
            min_value=1.0,
            max_value=200.0,
            value=30.0,
            step=5.0,
            disabled=not use_umkreis,
        )
    #PLZ spalte 2
    with col2:
        plz_input = st.text_input(
            "PLZ",
            label_visibility="collapsed",
            placeholder="PLZ eingeben",
        )
        country = st.selectbox(
        "Land",
        options=["DE", "AT", "CH"],
        index=0,
        label_visibility="visible",
    )

    #Schadensart
    schadensarten = list_schadensarten()
    schadensarten = [""] + schadensarten  # leere Auswahl

    with col3:
        schadensart_input = st.selectbox(
            "Schadenart",
            schadensarten,
            label_visibility="collapsed",
            format_func=lambda x: "Schadenart auswählen" if x == "" else x,
        )

    # Falltypen
    if schadensart_input:
        falltypen = list_falltypen_for_schadensart(schadensart_input)
    else:
        falltypen = []

    falltypen = ["", "Alle"] + falltypen

    with col4:
        falltyp_input = st.selectbox(
            "Falltyp",
            falltypen,
            label_visibility="collapsed",
            format_func=lambda x: "Falltyp auswählen" if x == "" else x,
        )

    st.markdown("---")

    #Suchen button maybe noch rausnehmen?
    if st.button("Suchen"):
        if schadensart_input == "":
            st.warning("Bitte zuerst eine Schadenart wählen.")
            return

        #Daten laden (kleine Datei je nach Schadenart/Falltyp)
        try:
            df_raw = lade_subset_auftragsdaten(schadensart_input, falltyp_input)
        except FileNotFoundError:
            st.error("Für diese Auswahl existiert keine Datei.")
            return

        if df_raw.empty:
            st.warning("Keine Daten für diese Auswahl vorhanden.")
            return

        #Basis-Dashboard: 1 Zeile je Handwerker + PLZ
        dashboard = (
            df_raw[["Handwerker_Name", "PLZ_HW"]]
            .drop_duplicates()
            .reset_index(drop=True)
        )

        #Zuverlässigkeitsscore berechnen und anhängen
        #ergänzung der berechnung muss noch
        df_zuv = berechne_zuverlaessigkeit(df_raw)
        dashboard = dashboard.merge(df_zuv, on="Handwerker_Name", how="left")
        
        #Umkreissuche oder einfache PLZ-Filterung
        #einfache PLZ Filterung maybe durch einfache Liste ersetzen
        if use_umkreis:
            if not plz_input:
                st.warning("Bitte für die Umkreissuche eine PLZ eingeben.")
                return

            with st.spinner("Berechne Umkreis..."):
                # Geo-Strukturen nur aus den Handwerkern im Dashboard bauen
                auftrag_geo, plz_coords, tree = build_auftrag_geo_from_df(dashboard)

                geo_result = datensaetze_im_umkreis(
                    input_plz=plz_input.strip(),
                    radius_km=radius_km,
                    country=country,
                    auftrag_geo=auftrag_geo,
                    plz_coords=plz_coords,
                    tree=tree,
                )

            if geo_result.empty:
                st.warning("Keine Handwerker im gewünschten Umkreis gefunden.")
                return

            #Entfernungen/Score ins Dashboard mergen
            geo_small = geo_result[["Handwerker_Name", "Entfernung_km", "Entfernungsscore"]]
            dashboard = dashboard.merge(geo_small, on="Handwerker_Name", how="inner")

        else:
            #klassische PLZ-Filterung (optional)
            if plz_input:
                dashboard = dashboard[
                    dashboard["PLZ_HW"].astype(str).str.startswith(plz_input.strip())
                ]

        if dashboard.empty:
            st.warning("Keine Ergebnisse gefunden.")
            return

        dashboard["Gesamtscore"] = 0.5* dashboard["Entfernungsscore"]+0.5* dashboard["Zuverlaessigkeit_Score"]
        dashboard = dashboard.sort_values(by="Gesamtscore", ascending=False)
        #Anzeigen lassen
        st.subheader("Handwerkervorschläge")

        shown_cols = [
            "Handwerker_Name",
            "PLZ_HW",
            "Zuverlaessigkeit_Score",
            "Entfernung_km",               # nur vorhanden bei Umkreissuche
            "Entfernungsscore",            # nur vorhanden bei Umkreissuche
            "Gesamtscore"
        ]

        available_cols = [c for c in shown_cols if c in dashboard.columns]

        st.dataframe(
            dashboard[available_cols],
            use_container_width=True,
            height=600,
        )
if __name__ == "__main__":
    main()

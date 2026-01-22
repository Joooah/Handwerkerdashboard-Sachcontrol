import streamlit as st
import pandas as pd
from Wilsonzuverlässigkeit import berechne_zuverlaessigkeit_variante_b
from Auftrags_und_Positionsdaten import (
    list_schadensarten,
    list_falltypen_for_schadensart,
    lade_subset_auftragsdaten,
    list_gewerke,
    lade_subset_auftragsdaten_gewerk,
)
from Postleitzahlentfernung import datensaetze_im_umkreis, get_geo_strukturen
import urllib.parse

AUFTRAGSDATEN_PATH = "/Users/benab/Desktop/Projekt/Auftragsdaten.parquet"

st.set_page_config(layout="wide")

SCORE_COLS = ["Entfernungsscore", "Zuverlaessigkeit_Score"]


def google_maps_url(Handwerker_Name: str, PLZ_HW: str, Land: str) -> str:
    q = f"{Handwerker_Name} {PLZ_HW} {Land}"
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(q)


def _normalize_weights(weights: dict) -> dict:
    s = float(sum(weights.values()))
    if s == 0:
        return {k: 0.0 for k in weights}
    return {k: float(v) / s for k, v in weights.items()}


def main():
    st.title("Handwerker-Dashboard")

    # -------------------- Filterbereich (wie im Original: dynamisch) --------------------
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        use_umkreis = st.checkbox("Umkreissuche", value=False)
        # wie im Original: editierbar (nicht disabled)
        radius_km = st.number_input(
            "Radius (km)",
            min_value=1.0,
            max_value=1000.0,
            value=20.0,
            step=5.0,
        )

    with col2:
        plz_input = st.text_input("PLZ", label_visibility="collapsed", placeholder="PLZ eingeben")
        country = st.selectbox("Land", options=["DE", "AT", "CH"], index=0, label_visibility="visible")

    with col3:
        filter_mode = st.radio(
            "Filtermodus",
            options=["Gewerk", "Schadenart/Falltyp"],
            horizontal=True,
            key="filter_mode",
        )

    # Defaults
    gewerk_input = ""
    schadensart_input = ""
    falltyp_input = "Alle"

    # Wichtig: Das bleibt wie im Original dynamisch beim Umschalten
    if filter_mode == "Gewerk":
        gewerke = [""] + list_gewerke()
        with col3:
            gewerk_input = st.selectbox(
                "Gewerk",
                gewerke,
                format_func=lambda x: "Gewerk auswählen" if x == "" else x,
                key="gewerk_input",
            )

        with col4:
            st.selectbox("Falltyp", ["(Filtermodus: Gewerk)"], disabled=True, key="falltyp_disabled")

    else:
        schadensarten = [""] + list_schadensarten()
        with col3:
            schadensart_input = st.selectbox(
                "Schadenart",
                schadensarten,
                format_func=lambda x: "Schadenart auswählen" if x == "" else x,
                key="schadensart_input",
            )

        if schadensart_input:
            falltypen_list = list_falltypen_for_schadensart(schadensart_input)
        else:
            falltypen_list = []

        falltypen = ["", "Alle"] + falltypen_list
        with col4:
            falltyp_input = st.selectbox(
                "Falltyp",
                falltypen,
                format_func=lambda x: "Falltyp auswählen" if x == "" else x,
                key="falltyp_input",
            )

    st.markdown("---")

    # -------------------- Gewichtung oben (nicht Sidebar) --------------------
    st.subheader("Gewichtung der Scores (0 erlaubt)")

    w1, w2 = st.columns(2)
    default_w = 0.5

    with w1:
        w_entf = st.number_input(
            "Entfernung",
            min_value=0.0,
            max_value=1.0,
            value=default_w,
            step=0.05,
            key="weight_Entfernungsscore",
        )
    with w2:
        w_zuv = st.number_input(
            "Zuverlässigkeit",
            min_value=0.0,
            max_value=1.0,
            value=default_w,
            step=0.05,
            key="weight_Zuverlaessigkeit_Score",
        )

    weights_raw = {"Entfernungsscore": w_entf, "Zuverlaessigkeit_Score": w_zuv}
    weights_norm = _normalize_weights(weights_raw)

    if sum(weights_raw.values()) == 0:
        st.caption("Gewichte (normalisiert): **alle 0** → Gesamtscore = 0")
    else:
        st.caption(
            "Gewichte (normalisiert): "
            + ", ".join([f"{k}: **{weights_norm[k]:.2f}**" for k in SCORE_COLS])
        )

    st.markdown("---")

    # -------------------- Suche / Berechnung --------------------
    if st.button("Suchen"):
        if plz_input == "":
            st.warning("Bitte zuerst eine PLZ eingeben.")
            return

        if filter_mode == "Gewerk":
            if gewerk_input == "":
                st.warning("Bitte zuerst ein Gewerk wählen.")
                return
            df_raw = lade_subset_auftragsdaten_gewerk(gewerk_input)
        else:
            if schadensart_input == "":
                st.warning("Bitte zuerst eine Schadenart wählen.")
                return
            df_raw = lade_subset_auftragsdaten(schadensart_input, falltyp_input)

        if df_raw.empty:
            st.warning("Keine Handwerker für diese Auswahl vorhanden.")
            return

        dashboard = df_raw[["Handwerker_Name", "PLZ_HW", "Land"]].drop_duplicates().reset_index(drop=True)

        df_zuv = berechne_zuverlaessigkeit_variante_b(df_raw)
        dashboard = dashboard.merge(df_zuv[["Handwerker_Name", "Zuverlaessigkeit_Score"]], on="Handwerker_Name", how="left")

        if use_umkreis:
            with st.spinner("Berechne Umkreis..."):
                auftrag_geo, plz_coords, tree = get_geo_strukturen()
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

            geo_small = geo_result[["Handwerker_Name", "Land", "PLZ_HW", "Entfernung_km", "Entfernungsscore"]]
            dashboard = dashboard.merge(geo_small, on=["Handwerker_Name", "Land", "PLZ_HW"], how="inner")
            dashboard["Entfernungsscore"] = pd.to_numeric(dashboard["Entfernungsscore"], errors="coerce")
            dashboard["Entfernung_km"] = pd.to_numeric(dashboard["Entfernung_km"], errors="coerce")

        else:
            # PLZ-Prefix Filter (wie original)
            dashboard = dashboard[dashboard["Land"] == country]
            dashboard = dashboard[dashboard["PLZ_HW"].astype(str).str.startswith(plz_input.strip())]
            # Stabil: Distanz-Spalten existieren trotzdem
            dashboard["Entfernung_km"] = 0.0
            dashboard["Entfernungsscore"] = 1.0

        if dashboard.empty:
            st.warning("Keine Ergebnisse gefunden.")
            return

        # Score-Spalten absichern
        for sc in SCORE_COLS:
            if sc not in dashboard.columns:
                dashboard[sc] = 0.0

        # Gesamtscore
        if sum(weights_raw.values()) == 0:
            dashboard["Gesamtscore"] = 0.0
        else:
            dashboard["Gesamtscore"] = 0.0
            for sc, w in weights_norm.items():
                dashboard["Gesamtscore"] += dashboard[sc].fillna(0) * w

        dashboard = dashboard.sort_values(by="Gesamtscore", ascending=False).reset_index(drop=True)
        for col in ["Zuverlaessigkeit_Score", "Entfernung_km", "Entfernungsscore", "Gesamtscore"]:
            if col in dashboard.columns:
                dashboard[col] = pd.to_numeric(dashboard[col], errors="coerce").round(2)

        dashboard["Maps-Link"] = dashboard.apply(
            lambda r: google_maps_url(
                str(r.get("Handwerker_Name", "")),
                str(r.get("PLZ_HW", "")),
                str(r.get("Land", "")),
            ),
            axis=1,
        )

        # -------------------- Übersicht --------------------
        st.subheader("Übersicht")

        if filter_mode == "Gewerk":
            filter_text = f"**Filtermodus:** Gewerk · **Gewerk:** {gewerk_input}"
        else:
            ft = falltyp_input if falltyp_input else "—"
            filter_text = f"**Filtermodus:** Schadenart/Falltyp · **Schadenart:** {schadensart_input} · **Falltyp:** {ft}"

        filter_text += f" · **PLZ:** {plz_input} · **Land:** {country}"
        filter_text += f" · **Umkreis:** {radius_km:.0f} km" if use_umkreis else " · **Umkreis:** nein"
        st.markdown(filter_text)

        if sum(weights_raw.values()) == 0:
            st.caption("**Gewichte (normalisiert):** alle 0 → Gesamtscore = 0")
        else:
            st.caption(
                "**Gewichte (normalisiert):** "
                + ", ".join([f"{k}: **{weights_norm[k]:.2f}**" for k in SCORE_COLS])
            )

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Ergebnisse", f"{len(dashboard):,}".replace(",", "."))
        with k2:
            st.metric("Ø Gesamtscore", f"{dashboard['Gesamtscore'].fillna(0).mean():.2f}")
        with k3:
            st.metric("Ø Zuverlässigkeit", f"{dashboard['Zuverlaessigkeit_Score'].fillna(0).mean():.2f}")
        with k4:
            if use_umkreis:
                avg_km = dashboard["Entfernung_km"].dropna()
                st.metric("Ø Entfernung (km)", f"{avg_km.mean():.1f}" if len(avg_km) else "—")
            else:
                st.metric("Ø Entfernung (km)", "0.00")

        st.divider()

        # -------------------- Anzeige (Progress Bars) --------------------
        st.subheader("Handwerkervorschläge")

        shown_cols = [
            "Handwerker_Name",
            "PLZ_HW",
            "Land",
            "Zuverlaessigkeit_Score",
            "Entfernung_km",
            "Entfernungsscore",
            "Gesamtscore",
            "Maps-Link",
        ]
        available_cols = [c for c in shown_cols if c in dashboard.columns]

        column_config = {
            "Maps-Link": st.column_config.LinkColumn("Maps-Link", display_text="Öffnen in Google Maps"),
        }
        if "Zuverlaessigkeit_Score" in available_cols:
            column_config["Zuverlaessigkeit_Score"] = st.column_config.ProgressColumn(
                "Preiszuverlässigkeitsscore", min_value=0.0, max_value=1.0, format="%.2f"
            )
        if "Entfernungsscore" in available_cols:
            column_config["Entfernungsscore"] = st.column_config.ProgressColumn(
                "Entfernungsscore", min_value=0.0, max_value=1.0, format="%.2f"
            )
        if "Gesamtscore" in available_cols:
            column_config["Gesamtscore"] = st.column_config.ProgressColumn(
                "Gesamtscore", min_value=0.0, max_value=1.0, format="%.2f"
            )

        st.dataframe(
            dashboard[available_cols],
            use_container_width=True,
            height=600,
            hide_index=True,
            column_config=column_config,
        )
        if len(dashboard) > 0:
            with st.expander("Erklärung zur Score-Zusammensetzung"):
                st.markdown("""
                Der dargestellte **Gesamtscore** setzt sich aus mehreren gewichteten Teilkomponenten zusammen.
                In diesem Dashboard werden insbesondere der **Entfernungsscore** und der **Zuverlässigkeitsscore**
                berücksichtigt.

                - **Zuverlässigkeitsscore:** spiegelt die Verlässlichkeit basierend auf den vorhandenen Auftrags-/Positionsdaten wider.
                - **Entfernungsscore:** bewertet die räumliche Nähe (bei Umkreissuche anhand der Distanz; ohne Umkreissuche als Standardwert).

                Die Teilwerte werden anschließend gemäß der oben eingestellten **Gewichtung** normalisiert und zu einem
                einheitlichen Gesamtscore zusammengeführt. So entsteht eine objektive und vergleichbare Reihenfolge der Vorschläge.
                """)

if __name__ == "__main__":
    main()

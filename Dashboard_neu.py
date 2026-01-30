import streamlit as st
import pandas as pd
import sys
from urllib.parse import quote
from GooglePlaces import load_cache, get_handwerker_data, CACHE_FILE_PATH
from Preiszuverlaessigkeit import berechne_zuverlaessigkeit
from Auftrags_und_Positionsdaten import (
    list_schadensarten, list_falltypen_for_schadensart, lade_subset_auftragsdaten,
    list_gewerke, lade_subset_auftragsdaten_gewerk,
)
from Postleitzahlentfernung import datensaetze_im_umkreis, get_geo_strukturen, nomi, ZFILL

st.set_page_config(page_title="SOLERA Dashboard", layout="wide")

SCORE_COLS = ["Entfernungsscore", "Preiszuverlässigkeitsscore"]

if "geo_struct" not in st.session_state:
    with st.spinner("Lade Geo-Daten …"):
        st.session_state.geo_struct = get_geo_strukturen()

auftrag_geo, plz_coords, tree = st.session_state.geo_struct

def norm_weights(w: dict) -> dict:
    s = sum(w.values()) or 0.0
    return {k: (v / s if s else 0.0) for k, v in w.items()}

def pick_df(filter_mode, gewerk, schaden, falltyp):
    if filter_mode == "Gewerk":
        return lade_subset_auftragsdaten_gewerk(gewerk) if gewerk else None
    return lade_subset_auftragsdaten(schaden, falltyp) if schaden else None



def main():
    if "google_cache" not in st.session_state:
        st.session_state.google_cache = load_cache()
    h1, h2 = st.columns([4,2], vertical_alignment="bottom")
    with h1:
        st.markdown("<div style='height:100%; display:flex; align-items:flex-end;'>"
                "<h1 style='margin:0'>Handwerker-Dashboard</h1>"
                "</div>", unsafe_allow_html=True)

    with h2:
        st.image("/Users/roberthendrich/Desktop/AAD/Handwerkerdashboard-Sachcontrol-main_26_01_26/Solera.png", width='stretch')

    st.markdown("<div class='top-divider'></div>", unsafe_allow_html=True)

    st.markdown(
        """
        <style>
          .card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            padding: 16px 16px 10px 16px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.18);
            margin-bottom: 12px;
        }
        .card h3 {
            margin: 0 0 10px 0;
            font-size: 1.05rem;
            font-weight: 700;
        }
        .muted {
            opacity: 0.75;
            font-size: 0.9rem;
            margin-top: -6px;
        }
        .pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.03);
            margin-right: 8px;
            margin-top: 8px;
            font-size: 0.85rem;
            opacity: 0.95;
            white-space: nowrap;
        }
        .top-divider {
            width: 100%;
            height: 1px;
            background: #ffffff;
            opacity: 0.9;
            margin: 16px 0 24px 0;
        }
        .v-divider {
            width: 1px;
            min-height: 240px;
            height: 100%;
            background: rgba(255,255,255,0.35);
            margin: 0 auto;
        }
        div[data-testid="stToggle"][data-key="placeholder_toggle"] {
            visibility: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div id='sc-row-marker'></div>", unsafe_allow_html=True)
    
    row1_left, row1_mid, row1_right = st.columns([1.35, 0.04, 1.0], gap="large")

    with row1_left:
        h_left, h_right = st.columns([0.6, 0.4], vertical_alignment="top")
        with h_left:
            st.markdown("### Suche")
        with h_right:
            st.markdown("&nbsp;", unsafe_allow_html=True)

        a, b = st.columns([1.0, 1.0], gap="medium")
        with a:
            plz_input = st.text_input("PLZ").strip()
        with b:
            country = st.selectbox("Land", options=["DE", "AT", "CH"], index=0)

        use_umkreis = st.toggle("Umkreissuche aktiv", value=False)
        radius_km = st.number_input(
            "Radius (km)",
            min_value=1.0,
            max_value=500.0,
            value=20.0,
            step=5.0,
            disabled=not use_umkreis,
            help="Wenn die Umkreissuche deaktiviert ist, wird nur nach Handwerkern mit der genauen PLZ gefiltert (Entfernungsscore = 100)."
        )


    with row1_mid:
        st.markdown("<div class='v-divider'></div>", unsafe_allow_html=True)

    with row1_right:
        header_left, header_right = st.columns([0.4, 0.6], vertical_alignment="bottom")
        with header_left:
            st.markdown("### Filter")
        with header_right:
            filter_mode = st.radio(
                " ",
                ["Gewerk", "Schadensart/Falltyp"],
                horizontal=True,
                label_visibility="collapsed",
            )


        gewerk_input, schadensart_input, falltyp_input = "", "", ""

        if filter_mode == "Gewerk":
            gewerk_input = st.selectbox(
                "Gewerk",
                [""] + list_gewerke(),
                format_func=lambda x: "Gewerk auswählen" if x == "" else x,
            )
            st.markdown("<div style='height: 2.5rem'></div>", unsafe_allow_html=True)

            st.selectbox("Falltyp", ["—"], disabled=True)
        else:
            schadensart_input = st.selectbox(
                "Schadensart",
                [""] + list_schadensarten(),
                format_func=lambda x: "Schadensart auswählen" if x == "" else x,
            )
            falltypen_list = [""] + (
                list_falltypen_for_schadensart(schadensart_input)
                if schadensart_input else []
            )
            st.markdown("<div style='height: 2.5rem'></div>", unsafe_allow_html=True)

            falltyp_input = st.selectbox(
                "Falltyp",
                falltypen_list,
                format_func=lambda x: "Falltyp auswählen" if x == "" else x,
            )
        


    with st.expander("Gewichtung der Scores", expanded=False):
        w1, w2 = st.columns(2, gap="large")
        with w1:
            w_entf = st.number_input("Entfernung", 0.0, 1.01, 0.5, 0.05)
        with w2:
            w_zuv = st.number_input("Zuverlässigkeit", 0.0, 1.01, 0.5, 0.05)

        w_raw = {"Entfernungsscore": w_entf, "Preiszuverlässigkeitsscore": w_zuv}
        w = norm_weights(w_raw)

        st.caption(
            "Gewichte (normalisiert): **alle 0** → Gesamtscore = 0"
            if sum(w_raw.values()) == 0
            else "Gewichte (normalisiert): " + ", ".join(f"{k}: **{w[k]:.2f}**" for k in SCORE_COLS)
        )

    btn_col1, btn_col2 = st.columns([1.0, 0.35])
    with btn_col2:
        do_search = st.button("Suchen", type="primary", use_container_width=True)

    st.divider()
    
    if do_search:
        # Nur beim aktiven Klick auf "Suchen" validieren & neu berechnen
        if not plz_input:
            st.warning("Bitte zuerst eine PLZ eingeben.")
            return

        plz_input = plz_input.replace(" ", "")
        if not plz_input.isdigit():
            st.warning("Bitte gültige PLZ eingeben.")
            return

        ziel_len = ZFILL.get(country, 5)
        if len(plz_input) != ziel_len:
            st.warning("Bitte gültige PLZ eingeben.")
            return

        info = nomi(country).query_postal_code(plz_input)
        if pd.isna(info.latitude) or pd.isna(info.longitude):
            st.warning("Bitte gültige PLZ eingeben.")
            return
        
        df_raw = pick_df(filter_mode, gewerk_input, schadensart_input, falltyp_input)
        if df_raw is None:
            st.warning("Bitte zuerst einen gültigen Filter auswählen.")
            return

        # Such-Kontext merken (damit bei Checkbox-Rerun die Anzeige stabil bleibt)
        st.session_state.search_ctx = {
            "filter_mode": filter_mode,
            "gewerk_input": gewerk_input,
            "schadensart_input": schadensart_input,
            "falltyp_input": falltyp_input,
            "plz_input": plz_input,
            "country": country,
            "use_umkreis": use_umkreis,
            "radius_km": radius_km,
            "w_raw": w_raw,   # optional: falls du später Gewichtung/Anzeige stabil halten willst
            "w": w,
        }
    
    else:
        # Kein neuer Suchklick (z.B. Checkbox wurde geklickt):
        # Wenn wir bereits ein Ergebnis haben, zeigen wir es wieder.
        if "dashboard_result" not in st.session_state or "search_ctx" not in st.session_state:
            return  # es gab noch nie eine Suche -> nichts anzeigen

        # Kontext wiederherstellen, damit die UI-Ausgabe (Filtertext etc.) konsistent bleibt
        ctx = st.session_state.search_ctx
        filter_mode = ctx["filter_mode"]
        gewerk_input = ctx["gewerk_input"]
        schadensart_input = ctx["schadensart_input"]
        falltyp_input = ctx["falltyp_input"]
        plz_input = ctx["plz_input"]
        country = ctx["country"]
        use_umkreis = ctx["use_umkreis"]
        radius_km = ctx["radius_km"]
        w_raw = ctx["w_raw"]
        w = ctx["w"]

    # Dashboard-Result laden und danach NICHT mehr neu berechnen
        dashboard = st.session_state.dashboard_result.copy()
    
    

    df_raw = pick_df(filter_mode, gewerk_input, schadensart_input, falltyp_input)
    if df_raw is None:
        st.warning("Bitte zuerst einen gültigen Filter auswählen.")
        return

    if do_search:
        dashboard = df_raw[["Handwerker_Name", "PLZ_HW", "Land"]].drop_duplicates().reset_index(drop=True)
        dashboard = dashboard.merge(
            berechne_zuverlaessigkeit(df_raw)[["Handwerker_Name", "Preiszuverlässigkeitsscore"]],
            on="Handwerker_Name", how="left")
    
        if use_umkreis:
            with st.spinner("Berechne Umkreis..."):
                auftrag_geo, plz_coords, tree = st.session_state.geo_struct
                relevante_hw = set(dashboard["Handwerker_Name"].unique())
                auftrag_geo_sub = auftrag_geo[auftrag_geo["Handwerker_Name"].isin(relevante_hw)]
                
            try:
                geo_result = datensaetze_im_umkreis(
                plz_input,
                radius_km,
                country,
                auftrag_geo_sub,
                plz_coords,
                tree,
                )
            except ValueError:
                st.warning(f"Bitte gültige PLZ eingeben.")
                st.stop()
            
            if geo_result.empty:
                st.warning("Keine Handwerker im gewünschten Umkreis gefunden.")
                return

            geo = geo_result[["Handwerker_Name", "Land", "PLZ_HW", "Entfernung in km", "Entfernungsscore"]]
            dashboard = dashboard.merge(geo, on=["Handwerker_Name", "Land", "PLZ_HW"], how="inner")
            dashboard[["Entfernung in km", "Entfernungsscore"]] = dashboard[["Entfernung in km", "Entfernungsscore"]].apply(pd.to_numeric, errors="coerce")

        else:
            dashboard = dashboard[(dashboard["Land"] == country) & (dashboard["PLZ_HW"].astype(str).str.startswith(plz_input))]
            dashboard = dashboard.assign(**{"Entfernung in km": 0.0, "Entfernungsscore": 100.0})

        if dashboard.empty:
            st.warning("Keine Ergebnisse gefunden.")
            return

        for c in SCORE_COLS:
            if c not in dashboard: dashboard[c] = 0.0


        if sum(w_raw.values()) == 0:
            dashboard["Gesamtscore"] = 0.0
        else:
            dashboard["Gesamtscore"] = sum(dashboard[c].fillna(0) * w[c] for c in SCORE_COLS)

        num_cols = ["Preiszuverlässigkeitsscore", "Entfernung in km", "Entfernungsscore", "Gesamtscore"]
        for c in num_cols:
            if c in dashboard: dashboard[c] = pd.to_numeric(dashboard[c], errors="coerce").round(2)
        dashboard = dashboard.sort_values("Gesamtscore", ascending=False).reset_index(drop=True)

        dashboard["Maps-Link"] = (
            "https://www.google.com/maps/search/?api=1&query=" +
            (dashboard["Handwerker_Name"].astype(str) + " " + dashboard["PLZ_HW"].astype(str) + " " + dashboard["Land"].astype(str)).map(quote)
        )
        
    if do_search:
        st.session_state.dashboard_result = dashboard.copy()

    st.subheader("Übersicht")
    ft = falltyp_input if (filter_mode != "Gewerk" and falltyp_input) else "—"
    filter_text = (f"**Filtermodus:** {filter_mode}"
                   + (f" · **Gewerk:** {gewerk_input}" if filter_mode == "Gewerk" else f" · **Schadenart:** {schadensart_input} · **Falltyp:** {ft}")
                   + f" · **PLZ:** {plz_input} · **Land:** {country}"
                   + (f" · **Umkreis:** {radius_km:.0f} km" if use_umkreis else " · **Umkreis:** nein"))
    
    st.markdown(filter_text)
       
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.metric("Ergebnisse", f"{len(dashboard):,}".replace(",", "."))
    with k2: st.metric("Ø Entfernung in km", 
                       f"{dashboard['Entfernung in km'].dropna().mean():.1f}" if use_umkreis and dashboard["Entfernung in km"].notna().any() else "0.00")

    with k3: st.metric("Ø Zuverlässigkeit", f"{dashboard['Preiszuverlässigkeitsscore'].fillna(0).mean():.2f}")
    with k4: st.metric("Ø Gesamtscore", f"{dashboard['Gesamtscore'].fillna(0).mean():.2f}")

    st.divider()
    
    st.subheader("Handwerkervorschläge")
    
    # Google Reviews aus Cache vorbelegen
    df_cache = st.session_state.google_cache

    # WICHTIG: last_updated kommt aus CSV und kann String / NaT / Timestamp sein.
    # Für Vergleiche MUSS die Spalte explizit in datetime konvertiert werden.
    df_cache["last_updated"] = pd.to_datetime(
        df_cache["last_updated"],
        errors="coerce",
        utc=True
    )

    cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=30)

    n_total = len(df_cache)
    n_expired = df_cache["last_updated"].lt(cutoff).sum()

    print(f"[CACHE] geladen:{n_total} Einträge, davon abgelaufen: {n_expired}", file=sys.stderr)

    def _norm_plz(plz_val, ctry):
        s = str(plz_val).strip() if plz_val is not None else ""
        target_len = ZFILL.get(str(ctry), len(s) if len(s) > 0 else 5)
        return s.zfill(target_len)

    cache_all = df_cache.copy()

    cache_all["plz_norm"] = cache_all.apply(
        lambda r: _norm_plz(r.get("plz"), r.get("country")),
        axis=1
    )

    cache_all["key"] = (
        cache_all["name_original"].astype(str).str.lower().str.strip() + "|" +
        cache_all["plz_norm"] + "|" +
        cache_all["country"].astype(str)
    )

    cache_all = (
        cache_all
        .sort_values("last_updated")
        .drop_duplicates(subset="key", keep="last")
    )

    cache_map = cache_all.set_index("key")[["rating", "user_ratings_total", "last_updated", "status"]].to_dict("index")

    dashboard["plz_norm"] = dashboard.apply(
        lambda r: _norm_plz(r["PLZ_HW"], r["Land"]),
        axis=1
    )

    dashboard["key"] = (
        dashboard["Handwerker_Name"].astype(str).str.lower().str.strip() + "|" +
        dashboard["plz_norm"] + "|" +
        dashboard["Land"].astype(str)
    )

    print(
        f"[DASHBOARD] key-Spalte erzeugt, Beispiel: {dashboard['key'].iloc[0] if len(dashboard) else '—'}",
        file=sys.stderr
    )

    def fmt_review(row):
        key = row["key"]

        if key not in cache_map:
            return "Noch nicht abgefragt"
        
        entry = cache_map[key]

        if entry.get("status") != "OK":
            return "Fehler bei Abfrage"
        
        rating = entry.get("rating")
        total = entry.get("user_ratings_total")
        last_updated = entry.get("last_updated")

        base = f"{rating} ({int(total) if not pd.isna(total) else 0})"
        
        print(
            f"[CACHE-CHECK] {key} last_updated={last_updated}", file = sys.stderr
        )

        if pd.notna(last_updated) and last_updated < cutoff:
            return f"({base}) - vor über 30 Tagen abgefragt"
        
        return base

    dashboard["Google Reviews"] = dashboard.apply(fmt_review, axis=1)

    
    # Checkbox nur aktiv, wenn noch nicht abgefragt
    #dashboard["Google Reviews laden"] = dashboard["Google Reviews"] == "Noch nicht abgefragt"

    if "Google Reviews laden" not in dashboard.columns:
        dashboard["Google Reviews laden"] = False

    shown_cols = ["Handwerker_Name", "PLZ_HW", "Land", "Entfernung in km",
            "Entfernungsscore", "Preiszuverlässigkeitsscore", "Gesamtscore", "Maps-Link", "Google Reviews", "Google Reviews laden"]
    cols = [c for c in shown_cols if c in dashboard.columns]

    column_config = {
            "Handwerker_Name": st.column_config.TextColumn("Handwerker"),
            "PLZ_HW": st.column_config.TextColumn("PLZ"),
            "Land": st.column_config.TextColumn("Land"),
            "Entfernung in km": st.column_config.NumberColumn("Entfernung in km"),
            "Maps-Link": st.column_config.LinkColumn("Maps-Link", display_text="In Google Maps öffnen"),
            "Google Reviews": st.column_config.TextColumn("Google Reviews"),
            "Google Reviews laden": st.column_config.CheckboxColumn("Google Reviews laden"),
    }
    for k, title in [("Preiszuverlässigkeitsscore","Preiszuverlässigkeitsscore"),
                     ("Entfernungsscore","Entfernungsscore"),
                     ("Gesamtscore","Gesamtscore")]:
        if k in cols:
            column_config[k] = st.column_config.ProgressColumn(label=title, min_value=0.0, max_value=100.0, format="%.0f%%")

    def on_hw_table_change():
        """
        Wird bei jeder Änderung im data_editor aufgerufen (Checkbox-Klick).
        Wir lesen den Editor-State aus st.session_state["hw_table"] (dict) aus
        und laden für neu angehakte Zeilen die Google Reviews.
        """
        state = st.session_state.get("hw_table")
        if not isinstance(state, dict):
            return

        edited_rows = state.get("edited_rows", {})
        if not edited_rows:
            return

        df_cache_local = st.session_state.google_cache

        # "edited_rows" ist ein dict: {row_index: {"Spaltenname": neuerWert, ...}, ...}
        # Wir reagieren nur auf Änderungen an der Checkbox-Spalte.
        for row_idx, changes in edited_rows.items():
            if changes.get("Google Reviews laden") is True:
                # Die Zeile aus der aktuell angezeigten Tabelle holen:
                row = st.session_state.hw_table_df.iloc[int(row_idx)]

                try:
                    _, df_cache_local = get_handwerker_data(
                        name=row["Handwerker_Name"],
                        plz=row["PLZ_HW"],
                        country=row["Land"],
                        df_cache=df_cache_local,
                        force_api= True
                    )
                except Exception as e:
                    # WICHTIG: nicht schlucken, sonst sieht man nie Key/Budget-Probleme
                    st.session_state.last_google_error = str(e)
                finally:
                    # Checkbox wieder aus (sonst löst jeder Rerun erneut aus)
                    st.session_state.hw_table_df.at[int(row_idx), "Google Reviews laden"] = False

        st.session_state.google_cache = df_cache_local

    st.session_state.hw_table_df = dashboard[cols].copy()

    edited = st.data_editor(
        #dashboard[cols], 
        st.session_state.hw_table_df,
        use_container_width=True, 
        height=600, 
        hide_index=True, 
        column_config=column_config,
        disabled=[c for c in cols if c!= "Google Reviews laden"],
        key="hw_table",
        on_change=on_hw_table_change,
    )
    
    if "last_google_error" in st.session_state:
        st.error(f"Google Places Fehler: {st.session_state.last_google_error}")
        del st.session_state["last_google_error"]
    
    #st.dataframe(dashboard[cols], use_container_width=True, height=600, 
    #                 hide_index=True, column_config=column_config)
    if len(dashboard):
        with st.expander("Erklärung zur Score-Zusammensetzung"):
            st.markdown("""

    Der dargestellte Gesamtscore setzt sich aus den beiden Teilkomponenten Entfernungsscore und Preiszuverlässigkeitsscore zusammen.

    Der Preiszuverlässigkeitsscore bewertet die Verlässlichkeit eines Handwerkers sowohl aus Preissicht als auch aus auftragsbezogener Sicht. Dabei wird berücksichtigt, wie angemessen die abgegebenen Kostenvoranschläge waren und wie häufig der Handwerker von Kunden beauftragt wurde. Grundlage hierfür bilden die vorhandenen Auftrags- und Positionsdaten.<br>
    Der Entfernungsscore bewertet die räumliche Nähe des Handwerkers zum jeweiligen Schadensort und klassifiziert diese in definierte Entdernungskategorien.

    Die beiden Teilwerte werden standardmäßig gleichgewichtet (50:50) oder abhängig von der eingestellten Gewichtung kombiniert und zu einem
    einheitlichen Gesamtscore zusammengeführt.
            """)

if __name__ == "__main__":
    main()

import pandas as pd
from datetime import datetime
import os
import streamlit as st
import requests
import sys


# Konfiguration
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
MAX_CALLS_PER_MONTH = 1000
CACHE_FILE_PATH = os.path.join(os.path.dirname(__file__), "cache.csv")
CACHE_TTL_DAYS = 30 

if not GOOGLE_API_KEY:
    raise RuntimeError(
        "GOOGLE_PLACES_API_KEY ist nicht gesetzt. "
        "Bitte als Environment Variable definieren."
    )

print("GooglePlaces geladen aus:", __file__, file=sys.stderr)
print("CACHE_FILE_PATH:", CACHE_FILE_PATH, file=sys.stderr)

# Cache laden / speichern
def load_cache():
    if os.path.exists(CACHE_FILE_PATH):
        df =  pd.read_csv(CACHE_FILE_PATH)

        if "last_updated" in df.columns:
            df["last_updated"] = pd.to_datetime(df.get("last_updated"), errors="coerce", utc = True)


        # Normalisieren für zuverlässiges Matching
        if "plz" in df.columns:
            df["plz"] = df["plz"].astype(str)
        if "name" in df.columns:
            df["name"] = df["name"].astype(str)
        if "country" in df.columns:
            df["country"] = df["country"].astype(str)
        if "name_original" in df.columns:
            df["name_original"] = df["name_original"].astype(str)

        # # Cache auf 30 Tage begrenzen
        # cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=CACHE_TTL_DAYS)

        # # WICHTIG:
        # # last_updated kommt aus CSV und kann String / NaT / Timestamp sein.
        # # Für Vergleiche mit cutoff MUSS die Spalte explizit in datetime konvertiert werden.
        # df["last_updated"] = pd.to_datetime(
        #     df["last_updated"],
        #     errors="coerce",
        #     utc=True
        # )

        # if "last_updated" in df.columns:
        #     df = df[df["last_updated"].isna() | (df["last_updated"] >= cutoff)].copy()


        return df

    return pd.DataFrame(columns=[
        "name_original","name", "plz", "country", "place_id",
        "rating", "user_ratings_total",
        "formatted_address", "website",
        "formatted_phone_number", "opening_hours",
        "types", "last_updated", "source",
        "status", "error_message"
    ])

def save_cache(df_cache):
    df_cache.to_csv(CACHE_FILE_PATH, index=False)



#--------------------------------------------------------------------------------------------------------------------------------------------------------------

# Zentrale Google-Antwortprüfung

def check_google_status(response_json):
    status = response_json.get("status")

    if status == "OK":
        return

    if status == "OVER_QUERY_LIMIT":
        raise RuntimeError(
            "Google Places API Quota überschritten. "
            "Weitere Abfragen wurden gestoppt."
        )

    if status == "REQUEST_DENIED":
        raise RuntimeError(
            f"Request denied: {response_json.get('error_message')}"
        )

    if status == "ZERO_RESULTS":
        raise ValueError("Kein Google-Eintrag gefunden.")

    raise RuntimeError(f"Unbekannter Google API Fehler: {status}")

#--------------------------------------------------------------------------------------------------------------------------------------------------------------

# Monatliches Abfragen Limit im Code erzwingen

def google_calls_this_month(df_cache):
    now = pd.Timestamp.now(tz="UTC")
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    df_cache["last_updated"] = pd.to_datetime(df_cache["last_updated"], errors="coerce", utc = True)
    return len(df_cache[
        (df_cache["source"] == "google") &
        (pd.to_datetime(df_cache["last_updated"]) >= month_start)
    ])

def check_google_limit(df_cache):
    if google_calls_this_month(df_cache) >= MAX_CALLS_PER_MONTH:
        raise RuntimeError(
            "Monatliches Google-API-Limit erreicht (1000)."
        )

#--------------------------------------------------------------------------------------------------------------------------------------------------------------

# Google Places: Text Search (Place finden)

def text_search_place(name, plz, country):
    query = f"{name} {plz} {country}"

    response = requests.get(
        "https://maps.googleapis.com/maps/api/place/textsearch/json",
        params={"query": query, "key": GOOGLE_API_KEY},
        timeout=10
    )

    response.raise_for_status()
    data = response.json()

    check_google_status(data)

    return data["results"][0]["place_id"]



#--------------------------------------------------------------------------------------------------------------------------------------------------------------

# Place Details 

def place_details(place_id):
    response = requests.get(
        "https://maps.googleapis.com/maps/api/place/details/json",
        params={
            "place_id": place_id,
            "fields": (
                "rating,"
                "user_ratings_total,"
                "formatted_address,"
                "website,"
                "formatted_phone_number,"
                "name,"
                "formatted_address,"
                "formatted_phone_number,"
                "opening_hours,"               # gibt ein Dict mit 'weekday_text'
                "website,"
                "types"  
            ),
            "key": GOOGLE_API_KEY
        },
        timeout=10
    )

    response.raise_for_status()
    data = response.json()

    check_google_status(data)

    result = data["result"]

    opening_hours = None
    if "opening_hours" in result and "weekday_text" in result["opening_hours"]:
        opening_hours = "\n".join(result["opening_hours"]["weekday_text"])

    return {
        "name": result.get("name"),
        "formatted_address": result.get("formatted_address"),
        "formatted_phone_number": result.get("formatted_phone_number"),
        "international_phone_number": result.get("international_phone_number"),
        "website": result.get("website"),
        "types": ", ".join(result.get("types", [])),
        "rating": result.get("rating"),
        "user_ratings_total": result.get("user_ratings_total"),
        "opening_hours": opening_hours 
    }


#--------------------------------------------------------------------------------------------------------------------------------------------------------------

# Zentrale Abfragen- Funktion (cache -> API)

def get_handwerker_data(name, plz, country, df_cache, force_api: bool = False):
    print("get_handwerker_data() called with:", name, plz, country,"force_api=", force_api, file=sys.stderr)

    plz = str(plz)
    name = str(name)
    country = str(country)

    # WICHTIG:
    # df_cache kann aus CSV / Session / Concat stammen und enthält evtl. Strings.
    # Vor jedem Datetime-Vergleich MUSS last_updated sauber typisiert werden.
    df_cache["last_updated"] = pd.to_datetime(
        df_cache.get("last_updated"),
        errors="coerce",
        utc=True
    )


    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days = CACHE_TTL_DAYS)
    
    # Prüfen ob im Cache schon ein erfolgreicher Eintrag existiert
    cached = df_cache[
        (df_cache["name_original"].str.lower().str.strip() == name.lower().strip()) &
        (df_cache["plz"] == plz) &
        (df_cache["country"] == country) &
        (df_cache["status"] == "OK")&
        (df_cache["last_updated"].isna() | (df_cache["last_updated"] >= cutoff))
    ]

    if (not force_api) and (not cached.empty):
        row = cached.iloc[0].to_dict()
        row["source"] = "cache"
        return row, df_cache


    # if not cached.empty:
    #     row = cached.iloc[0].to_dict()
    #     row["source"] = "cache"
    #     return row, df_cache

    # Google API Abfrage
    try:
        # Limit prüfen
        if google_calls_this_month(df_cache) >= MAX_CALLS_PER_MONTH:
            raise RuntimeError("Monatliches Google-API-Limit erreicht")

        # Place ID suchen
        place_id = text_search_place(name, plz, country)
        details = place_details(place_id)

        # Alten Eintrag, falls vorhanden löschen
        df_cache = df_cache[
        ~(
            (df_cache["name_original"].str.lower().str.strip() == name.lower().strip()) &
            (df_cache["plz"] == plz) &
            (df_cache["country"] == country)
        )
    ]

        # neues Ergebnis als Dataframe hinzufügen
        new_row = {
            "name_original": name,
            "name" : details.get("name"),
            "plz": plz,
            "country": country,
            "place_id": place_id,
            **details,
            "last_updated": pd.Timestamp.now(tz="UTC"),
            "source": "google",
            "status": "OK",
            "error_message": ""
        }

        df_cache = pd.concat([df_cache, pd.DataFrame([new_row])], ignore_index=True)
        save_cache(df_cache)

        return new_row, df_cache

    except Exception as e:
        print("GOOGLE ERROR for:", name, plz, country, file=sys.stderr)
        print("ERROR MESSAGE:", repr(e), file=sys.stderr)
        # Fehler werden nicht im Cache gespeichert
        error_row = {
            "name_original": name,
            "name": None,
            "plz": plz,
            "country": country,
            "place_id": None,
            "rating": None,
            "user_ratings_total": None,
            "formatted_address": None,
            "website": None,
            "formatted_phone_number": None,
            "opening_hours": None,
            "types": None,
            "last_updated": pd.Timestamp.now(tz="UTC"),
            "source": "google",
            "status": "ERROR",
            "error_message": str(e),
        }

        df_cache = df_cache[
            ~(
                (df_cache["name_original"].str.lower().str.strip() == name.lower().strip()) &
                (df_cache["plz"] == plz) &
                (df_cache["country"] == country)
            )
        ]

        df_cache = pd.concat(
            [df_cache, pd.DataFrame([error_row])],
            ignore_index=True
        )

        save_cache(df_cache)

        return error_row, df_cache

    

    



#--------------------------------------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------------------------------------





# # Dashboard - Button
# from GooglePlaces import load_cache, get_handwerker_data, google_calls_this_month
# # df_input -> Dataframe mit Spalten zu PLZ, Name, Land

# # in main() nach st.title !!!

# df_cache = load_cache()

# #--------------------------------------------------------------------------------------------------------------------------------------------------------------

# st.subheader("Google Places Infos")

# # Auswahl des Handwerkers aus dem Dashboard
# selected_name = st.selectbox("Handwerker auswählen", dashboard["Handwerker_Name"].unique())
# selected_row = dashboard[dashboard["Handwerker_Name"] == selected_name].iloc[0]

# # Limit prüfen (DEAKTIVIERUNG)
# if google_calls_this_month(df_cache) >= MAX_CALLS_PER_MONTH:
#     st.warning("Monatliches API-Limit erreicht. Keine weiteren Google-Abfragen möglich.")
#     st.stop()  # stoppt die Ausführung, Button wird nicht angezeigt

# if st.button("Handwerker-Infos laden"):
#     try:

#         with st.spinner("Lade Daten von Google Places..."):
#             data, df_cache = get_handwerker_data(
#                 name=selected_row["Handwerker_Name"],
#                 plz=selected_row["PLZ_HW"],
#                 country=selected_row["Land"],
#                 df_cache=df_cache
#             )

#         st.success(
#             "Daten geladen "
#             f"({ 'Cache' if data['source'] == 'cache' else 'Google API' })"
#         )

#         st.json(data)

#     except RuntimeError as e:
#         # z. B. Quota überschritten, API-Key ungültig
#         st.error(str(e))

#     except ValueError as e:
#         # z. B. kein Google-Eintrag gefunden
#         st.warning(str(e))

#     except Exception:
#         # absoluter Fallback
#         st.error(
#             "Unerwarteter Fehler. "
#             "Bitte später erneut versuchen."
#         )





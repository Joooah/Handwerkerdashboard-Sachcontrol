import streamlit as st
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

def entfernung_plz(plz1, plz2):
    geolocator = Nominatim(user_agent="plz_distance_app")

    ort1 = geolocator.geocode(f"{plz1}, Deutschland")
    ort2 = geolocator.geocode(f"{plz2}, Deutschland")

    if not ort1 or not ort2:
        return None

    koord1 = (ort1.latitude, ort1.longitude)
    koord2 = (ort2.latitude, ort2.longitude)

    return geodesic(koord1, koord2).kilometers


# ---------- STREAMLIT UI ----------
st.title("📍 Entfernung zwischen zwei Postleitzahlen")

plz1 = st.text_input("Erste PLZ eingeben", "")
plz2 = st.text_input("Zweite PLZ eingeben", "")

if st.button("Entfernung berechnen"):
    if not plz1.isdigit() or not plz2.isdigit():
        st.error("Bitte gültige deutsche Postleitzahlen eingeben (nur Zahlen).")
    else:
        dist = entfernung_plz(plz1, plz2)
        if dist is None:
            st.error("Eine der PLZs konnte nicht gefunden werden.")
        else:
            st.success(f"Die Entfernung beträgt: **{dist:.2f} km**")

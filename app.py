import streamlit as st
import pandas as pd

from data_loader import load_Auftragsdaten, load_Positionsdaten
from utils.filter import filter_handwerker_plz, filter_Dashboard, add_differences_cols, filter_preis, add_distance_col



st.set_page_config(layout="wide")

# ZUM AUSFÜHREN:  streamlit run app.py


# DF erstellen
df_auftrag = load_Auftragsdaten()
df_position = load_Positionsdaten()

# Differenzen hinzufügen
df_auftrag = add_differences_cols(df_auftrag)

#Entfernung hinzufügen


# Filter
Filter_Handwerker_Plz =  filter_handwerker_plz(df_auftrag)
Filter_Dashboard = filter_Dashboard(df_auftrag)
Filter_Preis = filter_preis(df_auftrag)

# ------------------------------------------------------------------
#           Inputs Dashboard
# ------------------------------------------------------------------



col1, col2, col3, col4 = st.columns(4)

with col2: 
    plz_input = st.text_input("PLZ", label_visibility= "collapsed", placeholder= "PLZ eingeben")


# Schadensarten Oberfilter
with col3: 
    schadensarten = df_auftrag["Schadenart_Name"].dropna().sort_values().unique().tolist()
    schadensarten.insert(0, "")
    schadensart_input = st.selectbox("Schadensart", options= schadensarten, 
                                     label_visibility="collapsed", 
                                     format_func=lambda x: "Schadensart auswählen" if x == "" else x) 
    
#Falltypen Unterfilter
with col4:
    falltypen = df_auftrag[df_auftrag["Schadenart_Name"] == schadensart_input]["Falltyp_Name"].dropna().sort_values().unique().tolist()
    falltypen.insert(0, "Alle")
    falltypen.insert(0, "")
    falltyp_input = st.selectbox("Falltyp", options = falltypen, 
                                 label_visibility="collapsed", 
                                 format_func= lambda x : "Falltyp auswählen" if x == "" else x)


#------------------------------------------------------------------
# Daten filtern nach Inputs
#------------------------------------------------------------------

mask = (
    (Filter_Dashboard["Schadenart_Name"] == schadensart_input) &
    (Filter_Dashboard["PLZ_HW"] == plz_input)
)

if falltyp_input != "Alle":
    mask = mask & (Filter_Dashboard["Falltyp_Name"] == falltyp_input)



if st.button("Suchen"):
    inputs_filter = Filter_Dashboard[mask][[
        "Handwerker_Name",
        "PLZ_HW",
        "Gewerk_Name",
        "Schadenart_Name",
        "Falltyp_Name",
        "Durchschnitt_Differenz_prozent"
    ]]
    
    st.dataframe(
        inputs_filter,
        use_container_width= True,
        height= 600
        )




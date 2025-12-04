import pandas as pd
import streamlit as st
import polars as pl


@st.cache_data
def load_Auftragsdaten():
    return pl.read_parquet("/Users/roberthendrich/Desktop/AAPD/Daten/Auftragsdaten.parquet").to_pandas()

@st.cache_data
def load_Positionsdaten():
    return pl.read_parquet("/Users/roberthendrich/Desktop/AAPD/Daten/Positionsdaten.parquet").to_pandas()
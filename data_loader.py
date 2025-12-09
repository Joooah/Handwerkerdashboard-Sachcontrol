import streamlit as st
import polars as pl


@st.cache_data
def load_Auftragsdaten():
    return pl.read_parquet("/Users/benab/Desktop/Projekt/Auftragsdaten.parquet").to_pandas()

@st.cache_data
def load_Positionsdaten():
    return pl.read_parquet("/Users/benab/Desktop/Projekt/Positionsdaten.parquet").to_pandas()
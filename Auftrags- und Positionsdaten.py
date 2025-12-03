import pandas as pd
import os
import re

# Pfade
pfad_df1 = '/Users/benab/Desktop/Projekt/Auftragsdaten.parquet'
pfad_df2 = '/Users/benab/Desktop/Projekt/Positionsdaten.parquet'
zielordner = '/Users/benab/Desktop/Projekt/'  # Ordner, in dem die Dateien liegen sollen
# Parquet-Dateien laden
df1 = pd.read_parquet(pfad_df1)
df2 = pd.read_parquet(pfad_df2)
print(df1['Falltyp_Name'].unique())
print
# Primary Key
key = "KvaRechnung_ID"

# Gemeinsame Spalten finden (außer dem Key)
gemeinsame_spalten = df1.columns.intersection(df2.columns).tolist()
if key in gemeinsame_spalten:
    gemeinsame_spalten.remove(key)

# Gemeinsame Spalten aus df2 entfernen, damit sie nicht doppelt im Merge landen
df2_bereinigt = df2.drop(columns=gemeinsame_spalten)

# Merge durchführen (INNER JOIN)
merged = pd.merge(df1, df2_bereinigt, on=key, how="inner")

# Prüfen, ob falltyp_name existiert
if 'Falltyp_Name' not in merged.columns:
    raise KeyError("Die Spalte 'Falltyp_Name' ist im gemergten DataFrame nicht vorhanden.")

# Für jeden falltyp_name eine eigene Parquet-Datei schreiben
for falltyp, gruppe in merged.groupby('Falltyp_Name'):
    # Dateinamen etwas säubern (keine Sonderzeichen/Leerzeichen)
    safe_falltyp = re.sub(r'[^A-Za-z0-9ÄÖÜäöüß_-]+', '_', str(falltyp))
    dateiname = f'Auftrags- und Positionsdaten_{safe_falltyp}.parquet'
    zieldatei = os.path.join(zielordner, dateiname)

    gruppe.to_parquet(zieldatei, index=False)
    print(f"Geschrieben: {zieldatei}")
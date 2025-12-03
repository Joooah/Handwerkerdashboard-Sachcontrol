# Zählung der Handwerker
import pandas as pd

df = pd.read_parquet('/Users/benab/Desktop/Projekt/Auftragsdaten.parquet')

hc = df['Handwerker_Name'].value_counts().reset_index()
hc.columns = ['Handwerker_Name', 'Häufigkeit']
def faktor(x):
    if x<= 2:
        return 0.35
    elif x<= 10:
        return 0.45
    elif x<= 100:
        return 0.6
    else:
        return 0.8

hc['Faktor'] = hc['Häufigkeit'].apply(faktor)
print(hc)
zieldatei = '/Users/benab/Desktop/Projekt/haeufigkeit_handwerker.parquet'
hc.to_parquet(zieldatei, index=False)

import pandas as pd
import numpy as np
df = pd.read_parquet('/Users/benab/Desktop/Projekt/Auftragsdaten.parquet')
dfz = pd.DataFrame()
dfz["Einigung"] = df["Einigung_Netto"]
dfz["HWNAME"] = df["Handwerker_Name"]
dfz["Forderung"] = df["Forderung_Netto"]

dfz["Verhältnis"]=dfz["Einigung"].div(dfz["Forderung"]).clip(upper=1)

dfz["Verhältnis"] = dfz["Verhältnis"].replace([np.inf, -np.inf], 1)
dfz.loc[dfz["Forderung"] == 0, "Verhältnis"] = 1
result = dfz[dfz["Verhältnis"] >= 0]
result= result.groupby("HWNAME").agg({"Verhältnis":"mean"})
print(result.min())

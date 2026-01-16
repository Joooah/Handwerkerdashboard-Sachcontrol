import pandas as pd
import numpy as np

def berechne_zuverlaessigkeit(df: pd.DataFrame) -> pd.DataFrame:
    required = ["Handwerker_Name", "Einigung_Netto", "Forderung_Netto"]

    dfz = df[required].copy()

    dfz.rename(columns={"Einigung_Netto": "Einigung","Forderung_Netto": "Forderung"},inplace=True)

    dfz["Verhaeltnis"] = dfz["Einigung"].div(dfz["Forderung"]).clip(upper=1)
    dfz["Verhaeltnis"] = dfz["Verhaeltnis"].replace([np.inf, -np.inf], 1)
    dfz.loc[dfz["Forderung"] == 0, "Verhaeltnis"] = 1

    result = (dfz.groupby("Handwerker_Name", as_index=False)["Verhaeltnis"].mean().rename(columns={"Verhaeltnis": "Zuverlaessigkeit_Score"}))

    return result

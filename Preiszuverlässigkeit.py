import math
import pandas as pd
import numpy as np

def wilson_lower_bound(p: float, n: int, z: float = 1.64) -> float:
    if n <= 0 or p <= 0: 
        return 0.0
    z2 = z * z
    return max(0.0, (p + z2/(2*n) - z*math.sqrt(p*(1-p)/n + z2/(4*n*n))) / (1 + z2/n))

def berechne_zuverlaessigkeit(df: pd.DataFrame) -> pd.DataFrame:
    dfz = df[["Handwerker_Name", "Einigung_Netto", "Forderung_Netto"]].copy()
    dfz["Verhaeltnis"] = (
        dfz["Einigung_Netto"].div(dfz["Forderung_Netto"])
        .replace([np.inf, -np.inf], 1).fillna(1).clip(upper=1)
    )

    result = dfz.groupby("Handwerker_Name")["Verhaeltnis"].agg(
        Preiszuverlässigkeitsscore="mean", n_jobs="size"
    ).reset_index()

    result["Preiszuverlässigkeitsscore"] = (result["Preiszuverlässigkeitsscore"] * 100).clip(0, 100)

    p = result["Preiszuverlässigkeitsscore"].to_numpy() / 100
    n = result["n_jobs"].to_numpy()

    wilson = np.fromiter((wilson_lower_bound(pi, int(ni)) for pi, ni in zip(p, n)), float, count=len(result))
    conf = np.where(p > 0, np.minimum(1.0, wilson / p), 0.0)
    result["zuverlaessigkeit_wilson"] = result["Preiszuverlässigkeitsscore"] * conf
    
    return result

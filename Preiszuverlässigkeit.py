import math
import pandas as pd
import numpy as np

def berechne_zuverlaessigkeit(df: pd.DataFrame) -> pd.DataFrame:
    required = ["Handwerker_Name", "Einigung_Netto", "Forderung_Netto"]

    dfz = df[required].copy()

    dfz.rename(columns={"Einigung_Netto": "Einigung","Forderung_Netto": "Forderung"},inplace=True)

    dfz["Verhaeltnis"] = dfz["Einigung"].div(dfz["Forderung"]).clip(upper=1)
    dfz["Verhaeltnis"] = dfz["Verhaeltnis"].replace([np.inf, -np.inf], 1)
    dfz.loc[dfz["Forderung"] == 0, "Verhaeltnis"] = 1

    result = (dfz.groupby("Handwerker_Name", as_index=False).agg(Zuverlaessigkeit_Score=("Verhaeltnis","mean"), n_jobs=("Verhaeltnis", "count")))

    return result

def wilson_lower_bound(p: float, n: int, z: float = 1.64) -> float:
    if n <= 0 or p <= 0:
        return 0.0

    z2 = z * z
    denom = 1.0 + z2 / n
    center = p + z2 / (2.0 * n)
    margin = z * math.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n)))
    return max(0.0, (center - margin) / denom)

def berechne_zuverlaessigkeit_variante_b(*args, n_jobs: str = "n_jobs"):
  
    df = berechne_zuverlaessigkeit(*args)

    # Sicherstellen, dass numerisch
    df["Zuverlaessigkeit_Score"] = pd.to_numeric(
        df["Zuverlaessigkeit_Score"], errors="coerce"
    )
    df[n_jobs] = pd.to_numeric(df[n_jobs], errors="coerce").fillna(0).astype(int)

    def _apply(row):
        score = row["Zuverlaessigkeit_Score"]
        n = row[n_jobs]

        if score <= 0 or n <= 0:
            return pd.Series({"zuverlaessigkeit_wilson_b": 0.0, "confidence": 0.0})

        p = score / 100.0
        wlb = wilson_lower_bound(p, n)
        confidence = min(1.0, wlb / p)

        return pd.Series({
            "zuverlaessigkeit_wilson_b": score * confidence,
            "confidence": confidence
        })

    result = df.apply(_apply, axis=1)

    df["zuverlaessigkeit_wilson_b"] = result["zuverlaessigkeit_wilson_b"]
    df["confidence"] = result["confidence"]

    return df
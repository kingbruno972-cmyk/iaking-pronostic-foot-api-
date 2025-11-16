import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SRC = ROOT / "data" / "raw" / "results_international_brut.csv"  # le fichier téléchargé
DST = ROOT / "data" / "raw" / "international.csv"

def main():
    print("Lecture du fichier source :", SRC)
    df = pd.read_csv(SRC)

    # Adapter aux colonnes Kaggle classiques : date, home_team, away_team, home_score, away_score, tournament
    # Si les noms diffèrent (ex: 'home' au lieu de 'home_team'), on ajustera.
    rename_map = {}

    cols = set(df.columns)

    if "home_team" in cols:
        rename_map["home_team"] = "home"
    elif "home" in cols:
        rename_map["home"] = "home"
    else:
        raise SystemExit("Impossible de trouver la colonne home_team/home dans le CSV source.")

    if "away_team" in cols:
        rename_map["away_team"] = "away"
    elif "away" in cols:
        rename_map["away"] = "away"
    else:
        raise SystemExit("Impossible de trouver la colonne away_team/away dans le CSV source.")

    if "home_score" in cols:
        rename_map["home_score"] = "home_goals"
    elif "home_goals" in cols:
        rename_map["home_goals"] = "home_goals"
    else:
        raise SystemExit("Impossible de trouver la colonne home_score/home_goals dans le CSV source.")

    if "away_score" in cols:
        rename_map["away_score"] = "away_goals"
    elif "away_goals" in cols:
        rename_map["away_goals"] = "away_goals"
    else:
        raise SystemExit("Impossible de trouver la colonne away_score/away_goals dans le CSV source.")

    if "tournament" in cols:
        rename_map["tournament"] = "competition"
    elif "competition" in cols:
        rename_map["competition"] = "competition"
    else:
        print("⚠️ Pas de colonne tournament/competition, on mettra 'Unknown'.")
        df["competition"] = "Unknown"
        rename_map["competition"] = "competition"

    if "date" not in cols:
        raise SystemExit("Impossible de trouver la colonne date dans le CSV source.")

    df = df.rename(columns=rename_map)

    keep_cols = ["date", "home", "away", "home_goals", "away_goals", "competition"]
    df_out = df[keep_cols].copy()

    # Nettoyage basique : garder uniquement les A-matchs (tu peux filtrer + tard par tournament)
    df_out["date"] = pd.to_datetime(df_out["date"])
    df_out = df_out.sort_values("date")

    # Optionnel : filtrer sur une période récente (ex: à partir de 2000)
    # df_out = df_out[df_out["date"] >= "2000-01-01"]

    DST.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(DST, index=False)

    print("✅ Fichier international.csv écrit :", DST)
    print("Nombre de matchs :", len(df_out))

if __name__ == "__main__":
    main() 
    
import pandas as pd
import numpy as np
from pathlib import Path

RAW_BULK = Path("data/raw/bulk")
OUT_FILE = Path("data/raw/matches.csv")
ALIASES_FILE = Path("data/aliases/teams.csv")

REQ = ["league","season","date","home","away","home_goals","away_goals"]
OPT = ["home_odds","draw_odds","away_odds","round","referee","stadium"]

CANDIDATES = {
    "league": ["league","League","division","Div","liga","comp"],
    "season": ["season","Season","saison","Saison","year","Year"],
    "date":   ["date","Date","match_date","MatchDate"],
    "home":   ["home","Home","home_team","HomeTeam"],
    "away":   ["away","Away","away_team","AwayTeam"],
    "home_goals": ["home_goals","HomeGoals","FTHG","home_score","HG"],
    "away_goals": ["away_goals","AwayGoals","FTAG","away_score","AG"],
    "home_odds":  ["home_odds","B365H","odd_home","HomeOdds","H_odds"],
    "draw_odds":  ["draw_odds","B365D","odd_draw","DrawOdds","D_odds"],
    "away_odds":  ["away_odds","B365A","odd_away","AwayOdds","A_odds"],
    "round":  ["round","Round","journee","gw","matchday"],
    "referee":["referee","Referee","arb"],
    "stadium":["stadium","Stadium","venue","ground"],
}

def load_aliases():
    if ALIASES_FILE.exists():
        df = pd.read_csv(ALIASES_FILE)
        df["alias"] = df["alias"].astype(str).str.strip()
        df["canonical"] = df["canonical"].astype(str).str.strip()
        return dict(zip(df["alias"], df["canonical"]))
    return {}

def standardize_columns(df):
    new = {}
    for std, cands in CANDIDATES.items():
        for c in cands:
            if c in df.columns:
                new[std] = c
                break
    df = df.rename(columns={v:k for k,v in new.items()})
    keep = [c for c in REQ+OPT if c in df.columns]
    return df[keep]

def to_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(",", ".", regex=False), errors="coerce")

def normalize_team_names(df, aliases):
    for col in ["home","away"]:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].apply(lambda x: aliases.get(x, x))
    return df

def run():
    files = sorted(RAW_BULK.glob("*.csv"))
    if not files:
        print("Aucun CSV trouvé dans data/raw/bulk — copie tes fichiers puis relance.")
        return

    aliases = load_aliases()
    parts = []
    for f in files:
        try:
            dfi = pd.read_csv(f)
        except Exception as e:
            print(f"[SKIP] {f.name}: {e}")
            continue
        dfi = standardize_columns(dfi)

        if "date" in dfi.columns:
            dfi["date"] = pd.to_datetime(dfi["date"], errors="coerce").dt.date

        for gcol in ["home_goals","away_goals"]:
            if gcol in dfi.columns:
                dfi[gcol] = pd.to_numeric(dfi[gcol], errors="coerce").astype("Int64")
        for ocol in ["home_odds","draw_odds","away_odds"]:
            if ocol in dfi.columns:
                dfi[ocol] = to_numeric(dfi[ocol])

        dfi = dfi.dropna(subset=["league","season","date","home","away"])
        dfi = dfi.dropna(subset=["home_goals","away_goals"])
        dfi = dfi[dfi["home"] != dfi["away"]]

        dfi = normalize_team_names(dfi, aliases)
        parts.append(dfi)

    if not parts:
        print("Après nettoyage: plus aucune ligne. Vérifie tes fichiers.")
        return

    df = pd.concat(parts, ignore_index=True)
    df = df.sort_values(["league","season","date","home","away"])
    df = df.drop_duplicates(subset=["league","season","date","home","away"], keep="last")
    df = df[(df["home_goals"] >= 0) & (df["away_goals"] >= 0)]

    for ocol in ["home_odds","draw_odds","away_odds"]:
        if ocol in df.columns:
            df[ocol] = df[ocol].round(3)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_FILE, index=False)

    print("Fusion terminée ✅")
    print(f"Lignes finales: {len(df):,}")
    print("Ligues:", ", ".join(sorted(df['league'].astype(str).unique())))
    print("Saisons:", ", ".join(sorted(df['season'].astype(str).unique())))
    print(df.sample(min(5, len(df))))

if __name__ == "__main__":
    run()

import pandas as pd
import joblib
from pathlib import Path
from features.elo import compute_elo_table
from betting.kelly import kelly_fraction

FIXTURES = Path("data/fixtures/fixtures.csv")
HISTO    = Path("data/raw/matches.csv")
OUT      = Path("data/fixtures/predictions.csv")

def last_n_stats(df, team, date, n=5):
    past = df[((df["home"] == team) | (df["away"] == team)) & (df["date"] < date)].sort_values("date").tail(n)
    if past.empty:
        return {"form_goals_for": 0.0, "form_goals_against": 0.0, "form_points": 0.0}

    gf = ga = pts = 0
    for _, r in past.iterrows():
        if r["home"] == team:
            gfor, gagn = r["home_goals"], r["away_goals"]
        else:
            gfor, gagn = r["away_goals"], r["home_goals"]

        gf += float(gfor)
        ga += float(gagn)
        pts += 3 if gfor > gagn else (1 if gfor == gagn else 0)

    return {
        "form_goals_for": gf / n,
        "form_goals_against": ga / n,
        "form_points": float(pts)
    }

def main():
    if not FIXTURES.exists():
        raise SystemExit("Fichier manquant: data/fixtures/fixtures.csv")

    if not HISTO.exists():
        raise SystemExit("Fichier manquant: data/raw/matches.csv (ingestion requise)")

    model = joblib.load("models/model_1x2.pkl")
    feature_cols = joblib.load("models/feature_columns.pkl")

    histo = pd.read_csv(HISTO, parse_dates=["date"]).sort_values("date")
    elo = compute_elo_table(histo)

    fx = pd.read_csv(FIXTURES, parse_dates=["date"])
    rows = []

    for _, r in fx.iterrows():
        league, date, home, away = (
            str(r["league"]),
            pd.to_datetime(r["date"]),
            str(r["home"]),
            str(r["away"]),
        )

        def last_elo(team):
            s = elo[
                (elo["league"] == league)
                & (elo["team"] == team)
                & (elo["date"] <= date)
            ].sort_values("date").tail(1)["elo"]

            return float(s.squeeze()) if not s.empty else 1500.0

        elo_home = last_elo(home)
        elo_away = last_elo(away)

        hstats = last_n_stats(histo, home, date)
        astats = last_n_stats(histo, away, date)

        features = {
            "f_elo_diff": elo_home - elo_away,
            "home_form_goals_for": hstats["form_goals_for"],
            "home_form_goals_against": hstats["form_goals_against"],
            "home_form_points": hstats["form_points"],
            "away_form_goals_for": astats["form_goals_for"],
            "away_form_goals_against": astats["form_goals_against"],
            "away_form_points": astats["form_points"],
        }

        X = pd.DataFrame([{col: features.get(col, 0) for col in feature_cols}])
        proba = model.predict_proba(X)[0]
        classes = list(model.classes_)

        out = {"home": 0.0, "draw": 0.0, "away": 0.0}
        for i, cls in enumerate(classes):
            out[cls] = float(proba[i])

        row = {
            "league": league,
            "date": date.date(),
            "home": home,
            "away": away,
            "p_home": out["home"],
            "p_draw": out["draw"],
            "p_away": out["away"],
        }

        for k in ["home_odds", "draw_odds", "away_odds"]:
            if k in r and pd.notna(r[k]):
                row[k] = float(r[k])

        if (
            "home_odds" in row
            and "draw_odds" in row
            and "away_odds" in row
        ):
            row["value_home"] = row["p_home"] * row["home_odds"]
            row["value_draw"] = row["p_draw"] * row["draw_odds"]
            row["value_away"] = row["p_away"] * row["away_odds"]

            row["stake_home"] = kelly_fraction(row["p_home"], row["home_odds"], b_mult=0.25)
            row["stake_draw"] = kelly_fraction(row["p_draw"], row["draw_odds"], b_mult=0.25)
            row["stake_away"] = kelly_fraction(row["p_away"], row["away_odds"], b_mult=0.25)

        rows.append(row)

    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)

    print("✅ OK →", OUT, f"({len(out)} lignes)")
    print(out.head(min(10, len(out))))

if __name__ == "__main__":
    main()
    
import sys
from pathlib import Path
import pandas as pd
import joblib

# Pour pouvoir importer features.elo même sans PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from features.elo import compute_elo_table  # type: ignore
from betting.kelly import kelly_fraction    # tu l'as déjà

HISTO = ROOT / "data" / "raw" / "matches.csv"
MODEL_PATH = ROOT / "models" / "model_1x2.pkl"
FEAT_PATH = ROOT / "models" / "feature_columns.pkl"


def last_n_stats(df, team, date, n=5):
    past = df[
        ((df["home"] == team) | (df["away"] == team))
        & (df["date"] < date)
    ].sort_values("date").tail(n)

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
        "form_points": float(pts),
    }


def main():
    if not HISTO.exists():
        print("❌ Historique introuvable :", HISTO)
        sys.exit(1)

    print("=== IA Pronostic Foot – Prono simple ===")

    league = input("Ligue (ex: FRA1, ESP1…) : ").strip() or "FRA1"
    home = input("Équipe à domicile : ").strip()
    away = input("Équipe à l'extérieur : ").strip()
    date_str = input("Date du match (YYYY-MM-DD) : ").strip()

    if not home or not away or not date_str:
        print("❌ Tu dois remplir home, away et date.")
        sys.exit(1)

    try:
        date = pd.to_datetime(date_str)
    except Exception:
        print("❌ Mauvais format de date, utilise YYYY-MM-DD.")
        sys.exit(1)

    # Charge modèle + features
    model = joblib.load(MODEL_PATH)
    feature_cols = joblib.load(FEAT_PATH)

    # Charge historique + Elo
    df = pd.read_csv(HISTO, parse_dates=["date"]).sort_values("date")
    elo_tab = compute_elo_table(df)

    def last_elo(team):
        s = elo_tab[
            (elo_tab["league"] == league)
            & (elo_tab["team"] == team)
            & (elo_tab["date"] <= date)
        ].sort_values("date").tail(1)["elo"]
        return float(s.squeeze()) if not s.empty else 1500.0

    elo_home = last_elo(home)
    elo_away = last_elo(away)

    home_stats = last_n_stats(df, home, date)
    away_stats = last_n_stats(df, away, date)

    features = {
        "f_elo_diff": elo_home - elo_away,
        "home_form_goals_for": home_stats["form_goals_for"],
        "home_form_goals_against": home_stats["form_goals_against"],
        "home_form_points": home_stats["form_points"],
        "away_form_goals_for": away_stats["form_goals_for"],
        "away_form_goals_against": away_stats["form_goals_against"],
        "away_form_points": away_stats["form_points"],
    }

    X = pd.DataFrame([{col: features.get(col, 0) for col in feature_cols}])
    proba = model.predict_proba(X)[0]
    classes = list(model.classes_)

    out = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for i, cls in enumerate(classes):
        out[cls] = float(proba[i])

    p_home = out["home"]
    p_draw = out["draw"]
    p_away = out["away"]

    def pct(x): return f"{x*100:.1f}%"

    print("\n=== Résultat IA ===")
    print(f"{home} vs {away} ({league}, {date_str})")
    print(f"  Home : {pct(p_home)}")
    print(f"  Draw : {pct(p_draw)}")
    print(f"  Away : {pct(p_away)}")

    # Issue recommandée (max proba)
    best_side = max(["home", "draw", "away"], key=lambda k: out[k])
    best_label = {"home": "Victoire domicile", "draw": "Match nul", "away": "Victoire extérieur"}[best_side]
    print(f"\n👉 Issue la plus probable : {best_label}")

    # Optionnel : cotes + value + mise
    want_odds = input("\nAs-tu les cotes ? (o/n) : ").strip().lower()
    if want_odds == "o":
        try:
            home_odds = float(input("Cote domicile : ").replace(",", "."))
            draw_odds = float(input("Cote nul      : ").replace(",", "."))
            away_odds = float(input("Cote extérieur: ").replace(",", "."))
        except Exception:
            print("⚠️ Cotes invalides, on s'arrête là.")
            return

        value_home = p_home * home_odds
        value_draw = p_draw * draw_odds
        value_away = p_away * away_odds

        print("\n=== Value (p * cote) ===")
        print(f"  Home : {value_home:.3f}")
        print(f"  Draw : {value_draw:.3f}")
        print(f"  Away : {value_away:.3f}")

        # Meilleure value
        values = {"home": value_home, "draw": value_draw, "away": value_away}
        best_v_side = max(values, key=values.get)
        print(f"\n🎯 Meilleur value bet : {best_v_side} (value = {values[best_v_side]:.3f})")

        # Kelly (prudence x0.25)
        bankroll_str = input("\nBankroll (€) pour la mise (ou vide pour sauter) : ").strip()
        if bankroll_str:
            try:
                bankroll = float(bankroll_str.replace(",", "."))
            except Exception:
                print("⚠️ Bankroll invalide, pas de calcul de mise.")
                return

            stake_home = kelly_fraction(p_home, home_odds, b_mult=0.25)
            stake_draw = kelly_fraction(p_draw, draw_odds, b_mult=0.25)
            stake_away = kelly_fraction(p_away, away_odds, b_mult=0.25)

            print("\n=== Mise conseillée (Kelly x0.25) ===")
            print(f"  Home : {stake_home*100:.2f}%  (~ {stake_home*bankroll:.2f} €)")
            print(f"  Draw : {stake_draw*100:.2f}%  (~ {stake_draw*bankroll:.2f} €)")
            print(f"  Away : {stake_away*100:.2f}%  (~ {stake_away*bankroll:.2f} €)")

    print("\n✅ Prono terminé.")


if __name__ == "__main__":
    main()
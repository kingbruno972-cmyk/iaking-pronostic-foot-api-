import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import log_loss
from sklearn.linear_model import LogisticRegression
import joblib

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "raw" / "international.csv"
MODEL_PATH = ROOT / "models" / "model_international.pkl"
FEAT_PATH = ROOT / "models" / "feature_columns_international.pkl"

ALL_LABELS = ["home", "draw", "away"]

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # résultat
    target = []
    for _, r in df.iterrows():
        if r["home_goals"] > r["away_goals"]:
            target.append("home")
        elif r["home_goals"] < r["away_goals"]:
            target.append("away")
        else:
            target.append("draw")
    df["target_1x2"] = target

    # Elo simple par équipe nationale
    # On va réutiliser une logique simple interne (Elo pour sélections)
    teams = sorted(set(df["home"]).union(df["away"]))
    elo = {t: 1500.0 for t in teams}

    k = 20  # facteur K
    elo_hist = []
    for _, r in df.iterrows():
        h, a = r["home"], r["away"]
        gh, ga = r["home_goals"], r["away_goals"]
        ra, rb = elo[h], elo[a]
        ea = 1 / (1 + 10 ** ((rb - ra) / 400))
        eb = 1 / (1 + 10 ** ((ra - rb) / 400))

        if gh > ga:
            sa, sb = 1.0, 0.0
        elif gh < ga:
            sa, sb = 0.0, 1.0
        else:
            sa, sb = 0.5, 0.5

        elo[h] = ra + k * (sa - ea)
        elo[a] = rb + k * (sb - eb)

        elo_hist.append({
            "date": r["date"],
            "home": h,
            "away": a,
            "elo_home": elo[h],
            "elo_away": elo[a],
        })

    elo_df = pd.DataFrame(elo_hist)

    df = df.merge(elo_df[["date","home","elo_home"]], on=["date","home"], how="left")
    df = df.merge(elo_df[["date","away","elo_away"]], on=["date","away"], how="left")

    df["f_elo_diff"] = df["elo_home"] - df["elo_away"]

    # forme 5 derniers matchs par sélection
    def last_n_stats(df_all, team, date, n=5):
        past = df_all[
            ((df_all["home"] == team) | (df_all["away"] == team))
            & (df_all["date"] < date)
        ].sort_values("date").tail(n)
        if past.empty:
            return {"gf": 0.0, "ga": 0.0, "pts": 0.0}

        gf = ga = pts = 0
        for _, r in past.iterrows():
            if r["home"] == team:
                gfor, gagn = r["home_goals"], r["away_goals"]
            else:
                gfor, gagn = r["away_goals"], r["home_goals"]
            gf += float(gfor)
            ga += float(gagn)
            pts += 3 if gfor > gagn else (1 if gfor == gagn else 0)
        return {"gf": gf / n, "ga": ga / n, "pts": float(pts)}

    forms = []
    for _, r in df.iterrows():
        date = r["date"]
        h = r["home"]; a = r["away"]
        hs = last_n_stats(df, h, date)
        as_ = last_n_stats(df, a, date)
        forms.append({
            "home_form_goals_for": hs["gf"],
            "home_form_goals_against": hs["ga"],
            "home_form_points": hs["pts"],
            "away_form_goals_for": as_["gf"],
            "away_form_goals_against": as_["ga"],
            "away_form_points": as_["pts"],
        })
    form_df = pd.DataFrame(forms)
    df = pd.concat([df.reset_index(drop=True), form_df.reset_index(drop=True)], axis=1)

    keep = [
        "date","home","away","home_goals","away_goals","target_1x2",
        "f_elo_diff",
        "home_form_goals_for","home_form_goals_against","home_form_points",
        "away_form_goals_for","away_form_goals_against","away_form_points",
    ]
    return df[keep]

def align_proba_matrix(classes, proba):
    dfp = pd.DataFrame(proba, columns=list(classes))
    for c in ALL_LABELS:
        if c not in dfp.columns:
            dfp[c] = 1e-9
    dfp = dfp[ALL_LABELS]
    dfp = dfp.div(dfp.sum(axis=1), axis=0)
    return dfp.values

def main():
    if not DATA.exists():
        print("❌ Fichier international manquant :", DATA)
        return

    df_raw = pd.read_csv(DATA)
    df_feat = build_features(df_raw)

    features = [
        "f_elo_diff",
        "home_form_goals_for","home_form_goals_against","home_form_points",
        "away_form_goals_for","away_form_goals_against","away_form_points",
    ]

    X = df_feat[features]
    y = df_feat["target_1x2"]

    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, shuffle=True, stratify=y, random_state=42
        )
    except Exception:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, shuffle=True, random_state=42
        )

    pipe = Pipeline([
        ("scaler", StandardScaler(with_mean=False)),
        ("clf", LogisticRegression(max_iter=500, class_weight="balanced", multi_class="auto")),
    ])

    pipe.fit(X_train, y_train)

    p_train = pipe.predict_proba(X_train)
    p_test = pipe.predict_proba(X_test)
    classes = pipe.classes_

    p_train_al = align_proba_matrix(classes, p_train)
    p_test_al = align_proba_matrix(classes, p_test)

    print("Features utilisées:", features)
    print("Classes apprises:", list(classes))
    print("LogLoss train:", log_loss(y_train, p_train_al, labels=ALL_LABELS))
    print("LogLoss test:", log_loss(y_test, p_test_al, labels=ALL_LABELS))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, MODEL_PATH)
    joblib.dump(features, FEAT_PATH)
    print("✅ Saved", MODEL_PATH, "and", FEAT_PATH)

if __name__ == "__main__":
    main() 
    
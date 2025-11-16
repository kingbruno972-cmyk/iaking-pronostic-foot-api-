from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import pandas as pd
import joblib
from pathlib import Path
import sys
import math

# =====================================================================
#  Chemins & imports internes
# =====================================================================

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from features.elo import compute_elo_table  # type: ignore

# =====================================================================
#  FastAPI + CORS
# =====================================================================

app = FastAPI(title="IA Pronostic Foot (Clubs + International)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # pour dev (iPhone sur le même Wi-Fi)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================================
#  Chargement modèles & données
# =====================================================================

# --- Modèle clubs ---
MODEL_CLUB_PATH = ROOT / "models" / "model_1x2.pkl"
FEAT_CLUB_PATH = ROOT / "models" / "feature_columns.pkl"
HISTO_CLUB_PATH = ROOT / "data" / "raw" / "matches.csv"

model_club = joblib.load(MODEL_CLUB_PATH)
feature_cols_club = joblib.load(FEAT_CLUB_PATH)

HISTO_CLUB = pd.read_csv(HISTO_CLUB_PATH, parse_dates=["date"]).sort_values("date")
ELO_CLUB = compute_elo_table(HISTO_CLUB)

# --- Modèle international ---
MODEL_INT_PATH = ROOT / "models" / "model_international.pkl"
FEAT_INT_PATH = ROOT / "models" / "feature_columns_international.pkl"
INT_DATA_PATH = ROOT / "data" / "raw" / "international.csv"

model_int = joblib.load(MODEL_INT_PATH)
feature_cols_int = joblib.load(FEAT_INT_PATH)
INT_DF = pd.read_csv(INT_DATA_PATH, parse_dates=["date"]).sort_values("date")


def build_elo_table_international(df: pd.DataFrame, k: float = 20.0) -> pd.DataFrame:
    """Elo simple pour les sélections."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    teams = sorted(set(df["home"]).union(df["away"]))
    elo = {t: 1500.0 for t in teams}

    rows = []
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

        rows.append({"date": r["date"], "team": h, "elo": elo[h]})
        rows.append({"date": r["date"], "team": a, "elo": elo[a]})

    return pd.DataFrame(rows)


ELO_INT = build_elo_table_international(INT_DF)

# =====================================================================
#  Schémas Pydantic
# =====================================================================


class MatchIn(BaseModel):
    # pour l’ancien endpoint /predict
    f_elo_diff: float = 0.0


class TeamsClubIn(BaseModel):
    league: str
    home: str
    away: str
    date: str  # "YYYY-MM-DD"


class TeamsInternationalIn(BaseModel):
    home: str
    away: str
    date: str  # "YYYY-MM-DD"


class ProbaOut(BaseModel):
    p_home: float
    p_draw: float
    p_away: float


class ExtendedProbaOut(ProbaOut):
    p_over25: float
    p_under25: float
    p_btts_yes: float
    p_btts_no: float


class ScoreProb(BaseModel):
    home: int
    away: int
    prob: float


class ScoresOut(BaseModel):
    scores: List[ScoreProb]


# =====================================================================
#  Fonctions utilitaires
# =====================================================================


def last_n_stats(df: pd.DataFrame, team: str, date, n: int = 5):
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


def proba_to_dict(model, feature_cols, features: dict):
    X = pd.DataFrame([{col: features.get(col, 0) for col in feature_cols}])
    proba = model.predict_proba(X)[0]
    classes = list(model.classes_)
    out = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for i, cls in enumerate(classes):
        out[cls] = float(proba[i])
    return out


def compute_international_features(t: TeamsInternationalIn):
    """Facteur commun utilisé par /predict_international & scores."""
    d = pd.to_datetime(t.date)

    def last_elo_int(team: str) -> float:
        s = ELO_INT[
            (ELO_INT["team"] == team)
            & (ELO_INT["date"] <= d)
        ].sort_values("date").tail(1)["elo"]
        return float(s.squeeze()) if not s.empty else 1500.0

    elo_home = last_elo_int(t.home)
    elo_away = last_elo_int(t.away)

    home_stats = last_n_stats(INT_DF, t.home, d)
    away_stats = last_n_stats(INT_DF, t.away, d)

    features = {
        "f_elo_diff": elo_home - elo_away,
        "home_form_goals_for": home_stats["form_goals_for"],
        "home_form_goals_against": home_stats["form_goals_against"],
        "home_form_points": home_stats["form_points"],
        "away_form_goals_for": away_stats["form_goals_for"],
        "away_form_goals_against": away_stats["form_goals_against"],
        "away_form_points": away_stats["form_points"],
    }

    return features


def poisson(mu: float, k: int) -> float:
    """PMF Poisson simple pour les scores exacts."""
    return math.exp(-mu) * mu**k / math.factorial(k)


def derive_goal_distribution(p_home: float, p_draw: float, p_away: float):
    """
    Approximation très simple pour avoir une moyenne de buts
    à partir de la proba 1N2.
    """
    # base goals
    base_home = 1.4
    base_away = 1.1

    # avantage léger en fonction de la proba
    delta = p_home - p_away
    mu_home = base_home + 0.8 * delta
    mu_away = base_away - 0.5 * delta

    mu_home = max(0.2, mu_home)
    mu_away = max(0.2, mu_away)

    return mu_home, mu_away


# =====================================================================
#  Endpoints
# =====================================================================


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Endpoint simple : f_elo_diff seulement (clubs) ---
@app.post("/predict", response_model=ProbaOut)
def predict(item: MatchIn):
    features = {col: 0.0 for col in feature_cols_club}
    if "f_elo_diff" in features:
        features["f_elo_diff"] = item.f_elo_diff

    out = proba_to_dict(model_club, feature_cols_club, features)
    return {"p_home": out["home"], "p_draw": out["draw"], "p_away": out["away"]}


# --- Endpoint clubs détaillé : /predict_match ---
@app.post("/predict_match", response_model=ProbaOut)
def predict_match(t: TeamsClubIn):
    d = pd.to_datetime(t.date)

    def last_elo_club(team: str) -> float:
        s = ELO_CLUB[
            (ELO_CLUB["league"] == t.league)
            & (ELO_CLUB["team"] == team)
            & (ELO_CLUB["date"] <= d)
        ].sort_values("date").tail(1)["elo"]
        return float(s.squeeze()) if not s.empty else 1500.0

    elo_home = last_elo_club(t.home)
    elo_away = last_elo_club(t.away)

    home_stats = last_n_stats(HISTO_CLUB, t.home, d)
    away_stats = last_n_stats(HISTO_CLUB, t.away, d)

    features = {
        "f_elo_diff": elo_home - elo_away,
        "home_form_goals_for": home_stats["form_goals_for"],
        "home_form_goals_against": home_stats["form_goals_against"],
        "home_form_points": home_stats["form_points"],
        "away_form_goals_for": away_stats["form_goals_for"],
        "away_form_goals_against": away_stats["form_goals_against"],
        "away_form_points": away_stats["form_points"],
    }

    out = proba_to_dict(model_club, feature_cols_club, features)
    return {"p_home": out["home"], "p_draw": out["draw"], "p_away": out["away"]}


# --- Endpoint international de base ---
@app.post("/predict_international", response_model=ProbaOut)
def predict_international(t: TeamsInternationalIn):
    features = compute_international_features(t)
    out = proba_to_dict(model_int, feature_cols_int, features)
    return {"p_home": out["home"], "p_draw": out["draw"], "p_away": out["away"]}


# --- Endpoint international étendu (Over/BTTS) ---
@app.post("/predict_international_extended", response_model=ExtendedProbaOut)
def predict_international_extended(t: TeamsInternationalIn):
    features = compute_international_features(t)
    out = proba_to_dict(model_int, feature_cols_int, features)

    # Petites heuristiques pour Over/BTTS (tu peux les améliorer plus tard)
    p_home = out["home"]
    p_draw = out["draw"]
    p_away = out["away"]

    # Over/Under 2.5 très grossier
    p_over25 = min(0.95, max(0.05, 0.35 + 0.6 * (p_home + p_away)))
    p_under25 = 1.0 - p_over25

    # BTTS basé sur probabilité de match ouvert
    p_btts_yes = min(0.95, max(0.05, 0.30 + 0.7 * p_over25))
    p_btts_no = 1.0 - p_btts_yes

    return {
        "p_home": p_home,
        "p_draw": p_draw,
        "p_away": p_away,
        "p_over25": p_over25,
        "p_under25": p_under25,
        "p_btts_yes": p_btts_yes,
        "p_btts_no": p_btts_no,
    }


# --- Endpoint international : scores exacts (Premium) ---
@app.post("/predict_international_scores", response_model=ScoresOut)
def predict_international_scores(t: TeamsInternationalIn):
    """
    Utilise les probas 1N2 pour approximer un modèle de buts
    puis calcule les probas de scores exacts via Poisson.
    """
    features = compute_international_features(t)
    out = proba_to_dict(model_int, feature_cols_int, features)

    p_home = out["home"]
    p_draw = out["draw"]
    p_away = out["away"]

    mu_home, mu_away = derive_goal_distribution(p_home, p_draw, p_away)

    max_goals = 5  # 0–5 pour chaque équipe
    scores = []
    total = 0.0

    # 1) on calcule toutes les probas brutes
    for gh in range(0, max_goals + 1):
        for ga in range(0, max_goals + 1):
            prob = poisson(mu_home, gh) * poisson(mu_away, ga)
            scores.append({"home": gh, "away": ga, "prob": prob})
            total += prob

    # 2) normalisation
    for s in scores:
        s["prob"] = s["prob"] / total if total > 0 else 0.0

    # 3) tri + top 10
    scores_sorted = sorted(scores, key=lambda x: x["prob"], reverse=True)[:10]

    return {"scores": scores_sorted}
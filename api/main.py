# api/main.py

from fastapi import FastAPI, Query
from typing import Optional

from scripts.predict_one import (
    predict_one_match,
    predict_one_match_from_apisports,
)

app = FastAPI()


@app.get("/")
def home():
    return {"status": "ok", "message": "API ia-pronostic-foot active"}


# ============================
#  ENDPOINT OPTION A (teams)
# ============================
@app.get("/predict_one")
def predict_one(
    home: str,
    away: str,
    odds_home: Optional[float] = Query(None),
    odds_draw: Optional[float] = Query(None),
    odds_away: Optional[float] = Query(None),
):
    """
    Option A : prono basé sur head-to-head (H2H).
    Les cotes sont là pour plus tard si tu veux enrichir le modèle.
    """
    # Pour l'instant on ignore les cotes ici,
    # on garde ton ancien comportement H2H.
    result = predict_one_match(
        home=home,
        away=away,
    )
    return result


# ============================
#  ENDPOINT OPTION B (fixture_id)
# ============================
@app.get("/predict_one_api_fixture")
def predict_one_api_fixture(
    fixture_id: int = Query(..., description="ID du fixture API-FOOTBALL"),
):
    """
    Option B : Utilise les prédictions OFFICIELLES API-FOOTBALL (/predictions)
    pour un fixture précis.
    """
    return predict_one_match_from_apisports(fixture_id)
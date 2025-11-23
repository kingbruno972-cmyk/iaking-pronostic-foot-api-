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


# =====================================================
#  /predict_one : par noms d'équipes (+ éventuellement cotes)
# =====================================================
@app.get("/predict_one")
def predict_one(
    home: str = Query(..., description="Équipe domicile (texte libre)"),
    away: str = Query(..., description="Équipe extérieure (texte libre)"),
    odds_home: Optional[float] = Query(
        None, description="Cote 1 (domicile), optionnelle"
    ),
    odds_draw: Optional[float] = Query(
        None, description="Cote N (nul), optionnelle"
    ),
    odds_away: Optional[float] = Query(
        None, description="Cote 2 (extérieur), optionnelle"
    ),
):
    """
    - Si les 3 cotes sont fournies => prono basé sur les cotes
    - Sinon => mode démo 33/33/33
    """
    return predict_one_match(
        home=home,
        away=away,
        odds_home=odds_home,
        odds_draw=odds_draw,
        odds_away=odds_away,
    )


# =====================================================
#  /predict_one_api_fixture : Option B (API-FOOTBALL /predictions)
# =====================================================
@app.get("/predict_one_api_fixture")
def predict_one_api_fixture(
    fixture_id: int = Query(
        ..., description="ID du fixture API-FOOTBALL (v3.football.api-sports.io)"
    )
):
    """
    Utilise le endpoint /predictions de API-FOOTBALL pour un fixture précis.
    """
    return predict_one_match_from_apisports(fixture_id)
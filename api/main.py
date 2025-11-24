# api/main.py

from fastapi import FastAPI, Query
from typing import Optional, Dict, Any

from scripts.predict_one import (
    predict_one_match,
    predict_one_match_from_apisports,
)
from scripts.apisports_client import (
    get_upcoming_fixtures,
    ApiSportsError,
)

app = FastAPI(
    title="IA Pronostic Foot",
    description="API perso pour prono foot (Option A H2H + Option B API-FOOTBALL /predictions)",
    version="1.0.0",
)


# ============================
#  HOME
# ============================
@app.get("/")
def home() -> Dict[str, Any]:
    return {"status": "ok", "message": "API ia-pronostic-foot active"}


# ============================
#  ENDPOINT OPTION A (par noms d'équipes)
# ============================
@app.get("/predict_one")
def predict_one(
    home: str,
    away: str,
    odds_home: Optional[float] = Query(
        None, description="Cote 1 (domicile) - optionnel pour l'instant"
    ),
    odds_draw: Optional[float] = Query(
        None, description="Cote N (nul) - optionnel pour l'instant"
    ),
    odds_away: Optional[float] = Query(
        None, description="Cote 2 (extérieur) - optionnel pour l'instant"
    ),
) -> Dict[str, Any]:
    """
    Option A : prono basé sur les head-to-head (H2H) via RapidAPI.
    - Paramètres : noms des équipes (home, away)
    - Pour l'instant on ignore les cotes, mais elles sont déjà prêtes pour évoluer.
    """
    result = predict_one_match(
        home=home,
        away=away,
    )
    return result


# ============================
#  ENDPOINT OPTION B (par fixture_id)
# ============================
@app.get("/predict_one_api_fixture")
def predict_one_api_fixture(
    fixture_id: int = Query(..., description="ID du fixture API-FOOTBALL (v3.football.api-sports.io)"),
) -> Dict[str, Any]:
    """
    Option B : Utilise les prédictions OFFICIELLES API-FOOTBALL (/predictions)
    pour un fixture précis (ID de match).
    """
    return predict_one_match_from_apisports(fixture_id)


# ============================
#  ENDPOINT : PROCHAINS MATCHS D'UNE LIGUE
# ============================
@app.get("/upcoming_fixtures")
def upcoming_fixtures(
    league: int = Query(..., description="ID de la ligue (ex: 61 pour Ligue 1)"),
    season: int = Query(..., description="Saison (ex: 2025)"),
    next: int = Query(10, description="Nombre de prochains matchs à récupérer"),
) -> Dict[str, Any]:
    """
    Retourne une liste simplifiée des prochains matchs d'une ligue.

    Exemple d'appel :
    /upcoming_fixtures?league=61&season=2025&next=10
    """
    try:
        fixtures = get_upcoming_fixtures(
            league=league,
            season=season,
            next_n=next,
        )
        return {
            "status": "ok",
            "count": len(fixtures),
            "fixtures": fixtures,
        }
    except ApiSportsError as e:
        return {
            "status": "error",
            "message": f"Erreur API-FOOTBALL (upcoming_fixtures) : {e}",
            "fixtures": [],
        }
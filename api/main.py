# api/main.py

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from scripts.predict_one import predict_one_match

app = FastAPI(title="IA Pronostic Foot")

# CORS pour ton iPhone, ton Mac, etc.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tu pourras restreindre plus tard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "API pronostic foot en ligne",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/predict_one")
def predict_one(
    home: str = Query(..., description="Équipe domicile"),
    away: str = Query(..., description="Équipe extérieure"),
    odds_home: float | None = Query(
        None, description="Cote 1 (domicile), optionnelle"
    ),
    odds_draw: float | None = Query(
        None, description="Cote N (nul), optionnelle"
    ),
    odds_away: float | None = Query(
        None, description="Cote 2 (extérieur), optionnelle"
    ),
):
    """
    Endpoint pour un match unique.

    - Obligatoire : home, away
    - Optionnel : odds_home, odds_draw, odds_away
      Si les 3 cotes sont fournies (> 1.0), on calcule les probabilités
      à partir des cotes (plus réaliste que le mode démo fixe).
    """
    result = predict_one_match(
        home=home,
        away=away,
        odds_home=odds_home,
        odds_draw=odds_draw,
        odds_away=odds_away,
    )
    return result
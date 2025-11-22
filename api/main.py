from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "API pronostic foot en ligne ✅"
    }

# Endpoint de test pour une prédiction simple
@app.get("/predict_one")
def predict_one(home: str, away: str):
    """
    TEMPORAIRE :
    pour l’instant on renvoie juste les équipes.
    On branchera ton vrai modèle ensuite.
    """
    return {
        "status": "ok",
        "home": home,
        "away": away,
        "prediction": "TODO_brancher_modele",
        "comment": "Route /predict_one OK, modèle à connecter."
    } 
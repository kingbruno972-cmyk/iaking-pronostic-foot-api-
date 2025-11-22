from fastapi import FastAPI
from scripts.predict_one import predict_one_match  # <- on importe ta fonction

app = FastAPI()


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "API pronostic foot en ligne ✅"
    }


@app.get("/predict_one")
def predict_one_endpoint(home: str, away: str):
    """
    Endpoint HTTP qui appelle ton vrai modèle.
    """
    result = predict_one_match(home, away)

    # Optionnel : on s'assure qu'il y ait toujours un status dans la réponse
    if "status" not in result:
        result["status"] = "ok"

    return result
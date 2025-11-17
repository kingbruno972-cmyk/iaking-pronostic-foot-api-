from fastapi import FastAPI

app = FastAPI(title="Test IA Prono Foot API")


@app.get("/health")
def health():
    return {"status": "ok", "message": "API en ligne sur Railway ✅"}


@app.get("/")
def root():
    return {"message": "Bienvenue sur l'API IA Prono Foot (test minimal) 🚀"}
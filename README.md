# IA Pronostic Foot — Starter (Ultra simple)

## 0) Installer Python 3.11 et pip

## 1) Créer l'environnement et installer
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 2) Entraîner un modèle de base
```bash
python training/train_1x2.py
```

## 3) Lancer l'API
```bash
uvicorn api.main:app --reload --port 8000
# Puis ouvrir http://localhost:8000/health
```

## 4) Tester une prédiction (ex: via curl)
```bash
curl -X POST http://localhost:8000/predict \  -H "Content-Type: application/json" \  -d '{"f_elo_diff": 150.0}'
```

## 5) Ajouter vos données
Placez votre historique dans `data/raw/matches.csv` au format:
```
league,season,date,home,away,home_goals,away_goals,home_odds,draw_odds,away_odds
FRA1,2024,2024-08-18,PSG,Marseille,4,0,1.55,4.10,5.80
```
Puis relancez l'entraînement.

## Notes
- Ce starter n'utilise qu'une feature (différence Elo) pour être simple. Ajoutez-en dans `features/build_features.py`.
- Aucun gain n'est garanti. Pariez de manière responsable.

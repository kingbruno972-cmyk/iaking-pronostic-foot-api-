"""
scripts/predict_one.py

Petit script utilitaire pour faire une prédiction 1/N/2 pour un match
à partir du modèle entraîné (models/model_1x2.pkl).

Utilisation en ligne de commande :
    python scripts/predict_one.py "PSG" "Marseille"

Peut aussi être importé depuis l'API :
    from scripts.predict_one import predict_one
"""

import sys
from pathlib import Path
from typing import Dict, Any

import joblib
import numpy as np
import pandas as pd


# Chemins vers le modèle et les colonnes de features
ROOT_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT_DIR / "models"

MODEL_PATH = MODELS_DIR / "model_1x2.pkl"
FEATURE_COLS_PATH = MODELS_DIR / "feature_columns.pkl"


class ModelNotReadyError(Exception):
    """Levée si le modèle ou les colonnes de features sont introuvables."""
    pass


def load_model_and_features():
    """
    Charge le modèle 1X2 et la liste des colonnes de features.

    :return: (model, feature_columns)
    :raises ModelNotReadyError: si les fichiers n'existent pas.
    """
    if not MODEL_PATH.exists():
        raise ModelNotReadyError(
            f"Modèle introuvable : {MODEL_PATH}. "
            f"Tu dois d'abord lancer l'entraînement : python training/train_1x2.py"
        )

    if not FEATURE_COLS_PATH.exists():
        raise ModelNotReadyError(
            f"Fichier des colonnes de features introuvable : {FEATURE_COLS_PATH}. "
            f"Vérifie le script d'entraînement."
        )

    model = joblib.load(MODEL_PATH)
    feature_columns = joblib.load(FEATURE_COLS_PATH)

    if not isinstance(feature_columns, (list, tuple)):
        raise ModelNotReadyError(
            f"feature_columns.pkl ne contient pas une liste de colonnes (type: {type(feature_columns)})"
        )

    return model, list(feature_columns)


def build_feature_vector(feature_columns, home: str, away: str) -> pd.DataFrame:
    """
    Construit un vecteur de features pour un match (home, away).

    ⚠️ VERSION SIMPLE : pour l'instant, on met toutes les features à 0.
    Quand on branchera vraiment ton pipeline de features (Elo, etc.),
    c'est ici qu'on utilisera features/build_features.py ou elo.py.

    :param feature_columns: liste des colonnes attendues par le modèle
    :param home: nom de l'équipe à domicile
    :param away: nom de l'équipe à l'extérieur
    :return: DataFrame avec une seule ligne de features
    """
    row = {col: 0.0 for col in feature_columns}

    # Exemple : si ta feature s'appelle "f_elo_diff", tu pourrais plus tard
    # calculer un vrai écart d'Elo ici.
    # if "f_elo_diff" in row:
    #     row["f_elo_diff"] = compute_elo_diff(home, away)

    X = pd.DataFrame([row])
    return X


def decode_probas(classes, probas) -> Dict[str, float]:
    """
    Mappe les classes du modèle vers des clés 'home_win', 'draw', 'away_win'.

    Le modèle peut avoir des classes: ['1', 'N', '2'] ou [0, 1, 2], etc.
    On essaie de deviner intelligemment.
    """
    proba_dict = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}

    mapping = {
        "1": "home_win",
        "H": "home_win",
        1: "home_win",

        "N": "draw",
        "D": "draw",
        "X": "draw",
        0: "draw",

        "2": "away_win",
        "A": "away_win",
        2: "away_win",
    }

    for cls, p in zip(classes, probas):
        key = mapping.get(cls)
        if key is None:
            # Si on ne reconnaît pas la classe, on l'ignore
            continue
        proba_dict[key] = float(p)

    # Normalisation légère si quelque chose ne tombe pas pile à 1
    total = sum(proba_dict.values())
    if total > 0:
        for k in proba_dict:
            proba_dict[k] = proba_dict[k] / total

    return proba_dict


def choose_label(proba_dict: Dict[str, float]) -> str:
    """
    Choisit le label final '1', 'N' ou '2' à partir des probas.
    """
    best = max(proba_dict, key=proba_dict.get)
    if best == "home_win":
        return "1"
    elif best == "away_win":
        return "2"
    else:
        return "N"


def predict_one(home: str, away: str) -> Dict[str, Any]:
    """
    Prédit l'issue d'un match (home vs away) avec le modèle 1X2.

    :param home: équipe à domicile
    :param away: équipe à l'extérieur
    :return: dict JSON-friendly
    """
    try:
        model, feature_columns = load_model_and_features()
    except ModelNotReadyError as e:
        return {
            "status": "error",
            "home": home,
            "away": away,
            "message": str(e),
        }

    X = build_feature_vector(feature_columns, home, away)

    # Probabilités de chaque classe
    probas = model.predict_proba(X)[0]
    classes = list(model.classes_)

    proba_dict = decode_probas(classes, probas)
    label = choose_label(proba_dict)

    return {
        "status": "ok",
        "home": home,
        "away": away,
        "prediction": label,          # '1', 'N' ou '2'
        "probas": proba_dict,         # {home_win, draw, away_win}
        "comment": (
            "Prédiction basée sur le modèle 1X2 entraîné. "
            "Les features sont actuellement simplifiées (tout à zéro)."
        ),
    }


def main_cli(argv=None):
    """
    Entrée ligne de commande.

    Exemple:
        python scripts/predict_one.py PSG Marseille
    """
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) != 2:
        print("Usage: python scripts/predict_one.py <HOME_TEAM> <AWAY_TEAM>")
        sys.exit(1)

    home, away = argv
    result = predict_one(home, away)
    # Affichage simple
    print(result)


if __name__ == "__main__":
    main_cli() 
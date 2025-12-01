import os
from typing import Optional, List
from datetime import datetime, timezone

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ============================================================
# Config API-FOOTBALL
# ============================================================

API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY")
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"

if API_FOOTBALL_KEY is None:
    print("⚠️  ATTENTION : la variable d'environnement API_FOOTBALL_KEY n'est pas définie.")


# ============================================================
# MODELES DE REPONSE (comme ton app iOS attend)
# ============================================================

class PredictionDTO(BaseModel):
    prediction: str
    p_home: float
    p_draw: float
    p_away: float
    comment: str
    status: str

    # Nouveaux champs
    btts_yes: Optional[float] = None   # probabilité que les 2 marquent
    over25: Optional[float] = None     # probabilité Over 2.5 buts
    correct_score: Optional[str] = None
    top_scorers: Optional[List[str]] = None


class FindFixtureResponse(BaseModel):
    status: str
    fixture_id: Optional[int]
    message: Optional[str]


# ----------- MODELES POUR LA RECHERCHE D'EQUIPES -----------

class TeamShort(BaseModel):
    id: int
    name: str
    country: Optional[str] = None
    league: Optional[str] = None
    logo: Optional[str] = None


class TeamSearchResponse(BaseModel):
    status: str
    teams: List[TeamShort]
    message: Optional[str] = None


# ============================================================
# FastAPI app
# ============================================================

app = FastAPI()


@app.get("/")
def read_root():
    return {"status": "ok", "message": "IA Prono Foot API en ligne"}


# ============================================================
# UTILITAIRES API-FOOTBALL
# ============================================================

def get_apifootball_headers() -> dict:
    if not API_FOOTBALL_KEY:
        raise HTTPException(
            status_code=500,
            detail="API_FOOTBALL_KEY manquante sur le serveur.",
        )
    return {"x-apisports-key": API_FOOTBALL_KEY}


def find_team_id(team_name: str) -> Optional[int]:
    """
    Cherche l'ID d'une équipe via /teams?search=...
    Retourne l'ID ou None si introuvable.
    """
    headers = get_apifootball_headers()
    params = {"search": team_name}

    r = requests.get(f"{API_FOOTBALL_BASE}/teams", headers=headers, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    resp = data.get("response", [])
    if not resp:
        return None

    team_obj = resp[0].get("team", {})
    return team_obj.get("id")


def decimal_to_prob(odd: Optional[float]) -> Optional[float]:
    if odd is None or odd <= 1.0:
        return None
    return 1.0 / odd


# ============================================================
# ---------- /predict_one  (MODE LIBRE) ----------
# ============================================================

@app.get("/predict_one", response_model=PredictionDTO)
def predict_one(
    home: str,
    away: str,
    odds_home: Optional[float] = None,
    odds_draw: Optional[float] = None,
    odds_away: Optional[float] = None,
):
    """
    Prono "libre" basé sur les noms d'équipes et éventuellement les cotes.
    Format de sortie compatible avec ton iPhone (PredictionDTO).
    """

    # Si les 3 cotes sont présentes, on calcule les probabilités implicites
    if odds_home and odds_draw and odds_away and odds_home > 0 and odds_draw > 0 and odds_away > 0:
        inv1 = 1.0 / odds_home
        invN = 1.0 / odds_draw
        inv2 = 1.0 / odds_away
        s = inv1 + invN + inv2

        p_home = inv1 / s
        p_draw = invN / s
        p_away = inv2 / s
        comment = f"Probabilités basées sur les cotes du marché pour {home} vs {away}."
    else:
        # Sinon, prono neutre simple (à améliorer plus tard)
        p_home = 0.40
        p_draw = 0.30
        p_away = 0.30
        comment = f"Prono générique (aucune cote fournie) pour {home} vs {away}."

    # Choix du signe le plus probable
    probs = {"1": p_home, "N": p_draw, "2": p_away}
    prediction = max(probs, key=probs.get)

    # Petites heuristiques provisoires pour BTTS / Over / Score exact
    btts_yes = min(0.85, max(0.25, (p_home + p_away) * 0.7))
    over25 = min(0.85, max(0.25, (p_home + p_away) * 0.6))
    correct_score = "2-1" if p_home >= p_away else "1-2"

    return PredictionDTO(
        prediction=prediction,
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
        comment=comment,
        status="ok",
        btts_yes=btts_yes,
        over25=over25,
        correct_score=correct_score,
        top_scorers=None,
    )


# ============================================================
# ---------- /teams_search  (RECHERCHE D'EQUIPES) ----------
# ============================================================

@app.get("/teams_search", response_model=TeamSearchResponse)
def teams_search(name: str):
    """
    Wrap de /teams?search=... pour l'app iOS.
    Retourne une liste simplifiée d'équipes possibles.
    """
    try:
        headers = get_apifootball_headers()
        params = {"search": name}

        r = requests.get(
            f"{API_FOOTBALL_BASE}/teams",
            headers=headers,
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()

        resp = data.get("response", [])
        teams: List[TeamShort] = []

        for item in resp:
            team = item.get("team", {}) or {}
            league_info = item.get("league", {}) or item.get("country", {}) or {}
            teams.append(
                TeamShort(
                    id=team.get("id"),
                    name=team.get("name", ""),
                    country=team.get("country"),
                    league=league_info.get("name"),
                    logo=team.get("logo"),
                )
            )

        if not teams:
            return TeamSearchResponse(
                status="error",
                teams=[],
                message=f"Aucune équipe trouvée pour '{name}' dans API-FOOTBALL.",
            )

        return TeamSearchResponse(
            status="ok",
            teams=teams,
            message=None,
        )

    except requests.HTTPError as e:
        return TeamSearchResponse(
            status="error",
            teams=[],
            message=f"Erreur API-FOOTBALL : {e}",
        )
    except Exception as e:
        return TeamSearchResponse(
            status="error",
            teams=[],
            message=f"Erreur serveur interne : {e}",
        )


# ============================================================
# ---------- /find_fixture  (AUTO API-FOOTBALL) ----------
# ============================================================

@app.get("/find_fixture", response_model=FindFixtureResponse)
def find_fixture(home: str, away: str):
    """
    1) Cherche l'ID de l'équipe domicile via /teams?search=home
    2) Cherche l'ID de l'équipe extérieure via /teams?search=away
    3) Essaye H2H (next, last) puis fixtures de la date du jour
    """
    try:
        headers = get_apifootball_headers()

        # 1) ID équipe domicile
        home_id = find_team_id(home)
        if home_id is None:
            return FindFixtureResponse(
                status="error",
                fixture_id=None,
                message=f"Équipe domicile '{home}' introuvable dans API-FOOTBALL.",
            )

        # 2) ID équipe extérieure
        away_id = find_team_id(away)
        if away_id is None:
            return FindFixtureResponse(
                status="error",
                fixture_id=None,
                message=f"Équipe extérieure '{away}' introuvable dans API-FOOTBALL.",
            )

        # Helper H2H deux sens
        def call_h2h(extra_params: dict) -> Optional[int]:
            for pair in (f"{home_id}-{away_id}", f"{away_id}-{home_id}"):
                params = {"h2h": pair, "timezone": "Europe/Paris"}
                params.update(extra_params)

                r = requests.get(
                    f"{API_FOOTBALL_BASE}/fixtures/headtohead",
                    headers=headers,
                    params=params,
                    timeout=15,
                )
                r.raise_for_status()
                data = r.json()
                resp = data.get("response", [])
                if not resp:
                    continue
                fixture = resp[0].get("fixture", {})
                fid = fixture.get("id")
                if fid:
                    return fid
            return None

        # 3a) prochain match à venir
        fixture_id = call_h2h({"next": 1})

        # 3b) dernier match joué
        if fixture_id is None:
            fixture_id = call_h2h({"last": 1})

        # 4) date du jour
        if fixture_id is None:
            today_str = datetime.now(timezone.utc).date().isoformat()

            def search_fixtures_for_team(team_id: int) -> Optional[int]:
                params = {
                    "team": team_id,
                    "date": today_str,
                    "timezone": "Europe/Paris",
                }
                r = requests.get(
                    f"{API_FOOTBALL_BASE}/fixtures",
                    headers=headers,
                    params=params,
                    timeout=15,
                )
                r.raise_for_status()
                data = r.json()
                for item in data.get("response", []):
                    teams = item.get("teams", {})
                    home_t = teams.get("home", {}).get("id")
                    away_t = teams.get("away", {}).get("id")
                    if (
                        (home_t == home_id and away_t == away_id)
                        or (home_t == away_id and away_t == home_id)
                    ):
                        fx = item.get("fixture", {})
                        fid = fx.get("id")
                        if fid:
                            return fid
                return None

            fixture_id = search_fixtures_for_team(home_id)
            if fixture_id is None:
                fixture_id = search_fixtures_for_team(away_id)

        if fixture_id is None:
            return FindFixtureResponse(
                status="error",
                fixture_id=None,
                message="Aucun match trouvé (ni à venir, ni récent, ni aujourd'hui) pour ce duel dans API-FOOTBALL.",
            )

        return FindFixtureResponse(
            status="ok",
            fixture_id=fixture_id,
            message=None,
        )

    except requests.HTTPError as e:
        return FindFixtureResponse(
            status="error",
            fixture_id=None,
            message=f"Erreur API-FOOTBALL : {e}",
        )
    except Exception as e:
        return FindFixtureResponse(
            status="error",
            fixture_id=None,
            message=f"Erreur serveur interne : {e}",
        )


# ============================================================
# ---------- /predict_one_api_fixture  (PRONO PRO) ----------
# ============================================================

@app.get("/predict_one_api_fixture", response_model=PredictionDTO)
def predict_one_api_fixture(fixture_id: int):
    """
    Prono PRO à partir d'un fixture_id.
    Essaie d'utiliser les cotes API-FOOTBALL (1N2, BTTS, Over 2.5).
    Si indisponible ou incohérent, revient à un prono neutre.
    """
    # Défault : prono neutre légèrement orienté domicile
    p_home = 0.45
    p_draw = 0.27
    p_away = 0.28
    btts_yes = 0.60
    over25 = 0.58
    comment_parts: list[str] = []

    headers = get_apifootball_headers()

    try:
        # 1) On va chercher les cotes de ce fixture
        params = {"fixture": fixture_id, "timezone": "Europe/Paris"}
        r = requests.get(
            f"{API_FOOTBALL_BASE}/odds",
            headers=headers,
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()

        resp = data.get("response", [])
        if resp:
            odds_block = resp[0]
            bookmakers = odds_block.get("bookmakers", [])

            if bookmakers:
                bookmaker = bookmakers[0]
                bets = bookmaker.get("bets", [])

                used_1x2 = False
                used_btts = False
                used_over = False

                odd_home = odd_draw = odd_away = None

                for bet in bets:
                    name = str(bet.get("name", "")).strip().lower()

                    # --- Match Winner / 1X2 / Full Time Result ---
                    if (not used_1x2 and
                        name in ["match winner",
                                 "1x2",
                                 "full time result",
                                 "match result"]):
                        inv_home = inv_draw = inv_away = None

                        for val in bet.get("values", []):
                            label = str(val.get("value", "")).strip().lower()
                            try:
                                odd = float(val.get("odd"))
                            except (TypeError, ValueError):
                                continue

                            if label in ("home", "1"):
                                inv_home = decimal_to_prob(odd)
                                odd_home = odd
                            elif label in ("draw", "x", "n", "d"):
                                inv_draw = decimal_to_prob(odd)
                                odd_draw = odd
                            elif label in ("away", "2"):
                                inv_away = decimal_to_prob(odd)
                                odd_away = odd

                        if inv_home and inv_draw and inv_away:
                            s = inv_home + inv_draw + inv_away
                            p_home = inv_home / s
                            p_draw = inv_draw / s
                            p_away = inv_away / s
                            used_1x2 = True
                            comment_parts.append(
                                "Probabilités PRO basées sur les cotes 1N2 de API-FOOTBALL "
                                f"(1={odd_home}, N={odd_draw}, 2={odd_away})."
                            )

                    # --- Both Teams To Score ---
                    if (not used_btts and
                        ("both teams to score" in name or "btts" in name)):
                        yes_prob = None
                        for val in bet.get("values", []):
                            label = str(val.get("value", "")).strip().lower()
                            try:
                                odd = float(val.get("odd"))
                            except (TypeError, ValueError):
                                continue
                            if label == "yes":
                                yes_prob = decimal_to_prob(odd)
                        if yes_prob is not None:
                            btts_yes = yes_prob
                            used_btts = True
                            comment_parts.append(
                                "BTTS basé sur les cotes 'Both Teams To Score'."
                            )

                    # --- Over/Under buts (on cherche Over 2.5) ---
                    if (not used_over and
                        ("over/under" in name
                         or "total goals" in name
                         or "goals over/under" in name)):
                        over_prob = None
                        for val in bet.get("values", []):
                            label = str(val.get("value", "")).lower()
                            try:
                                odd = float(val.get("odd"))
                            except (TypeError, ValueError):
                                continue

                            # Formats possibles : "Over 2.5", "2.5", ">2.5"
                            if "over" in label and "2.5" in label:
                                over_prob = decimal_to_prob(odd)
                            elif label == "2.5" and over_prob is None:
                                over_prob = decimal_to_prob(odd)

                        if over_prob is not None:
                            over25 = over_prob
                            used_over = True
                            comment_parts.append(
                                "Over 2.5 basé sur les cotes Over/Under."
                            )

        if not comment_parts:
            comment_parts.append(
                "Prono PRO basique (cotes détaillées indisponibles ou non reconnues), modèle à affiner."
            )

    except requests.HTTPError as e:
        comment_parts.append(
            f"Erreur API-FOOTBALL (odds) : {e}. Prono neutre utilisé."
        )
    except Exception as e:
        comment_parts.append(
            f"Erreur interne lors de la récupération des cotes : {e}. Prono neutre utilisé."
        )

    # Choix du signe le plus probable
    probs = {"1": p_home, "N": p_draw, "2": p_away}
    prediction = max(probs, key=probs.get)

    comment = " ".join(comment_parts) + f" (fixture_id {fixture_id})."

    return PredictionDTO(
        prediction=prediction,
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
        comment=comment,
        status="ok",
        btts_yes=btts_yes,
        over25=over25,
        correct_score="2-1",  # TODO: futur modèle score exact
        top_scorers=None,
    )
# scripts/rapidapi_client.py

import os
import requests

BASE_URL = "https://v3.football.api-sports.io"


class RapidApiError(Exception):
    pass


def _headers() -> dict:
    api_key = os.getenv("APISPORTS_KEY")
    if not api_key:
        raise RapidApiError(
            "APISPORTS_KEY non défini. Utilise : export APISPORTS_KEY=\"ta_clé\""
        )
    return {
        "x-apisports-key": api_key,
        "x-apisports-host": "v3.football.api-sports.io",
    }


def get_ligue1_next_fixtures(limit: int = 10) -> dict:
    params = {
        "league": 61,
        "season": 2023,  # FREE PLAN = 2021–2023 uniquement !
        "next": limit,
    }

    resp = requests.get(
        f"{BASE_URL}/fixtures",
        headers=_headers(),
        params=params,
        timeout=10,
    )

    if resp.status_code != 200:
        raise RapidApiError(f"HTTP {resp.status_code}: {resp.text}")

    data = resp.json()

    if data.get("errors"):
        raise RapidApiError(f"API Error: {data['errors']}")

    return data
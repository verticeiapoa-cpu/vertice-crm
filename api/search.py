import asyncio
from typing import Optional
import httpx

AI_PRIORITY_MAP = {
    "hairdresser":      10,
    "beauty":           10,
    "barber":           9,
    "nail_salon":       9,
    "spa":              8,
    "physiotherapist":  8,
    "dietitian":        8,
    "psychologist":     8,
    "dentist":          7,
    "fitness_centre":   7,
    "gym":              7,
    "veterinary":       6,
    "florist":          6,
    "restaurant":       5,
    "bakery":           5,
    "pharmacy":         4,
    "real_estate_agent":3,
    "lawyer":           3,
    "accountant":       3,
    "car_repair":       2,
    "hardware":         2,
    "supermarket":      2,
}

TERM_MAP = {
    "academia":          ("leisure", "fitness_centre"),
    "musculação":        ("leisure", "fitness_centre"),
    "salão de beleza":   ("shop",    "hairdresser"),
    "salao de beleza":   ("shop",    "hairdresser"),
    "salão":             ("shop",    "hairdresser"),
    "salao":             ("shop",    "hairdresser"),
    "barbearia":         ("shop",    "barber"),
    "barbearias":        ("shop",    "barber"),
    "restaurante":       ("amenity", "restaurant"),
    "restaurantes":      ("amenity", "restaurant"),
    "dentista":          ("amenity", "dentist"),
    "odonto":            ("amenity", "dentist"),
    "estética":          ("shop",    "beauty"),
    "estetica":          ("shop",    "beauty"),
    "beleza":            ("shop",    "beauty"),
    "spa":               ("leisure", "spa"),
    "psicolog":          ("amenity", "psychologist"),
    "fisioterapia":      ("amenity", "physiotherapist"),
    "nutrição":          ("amenity", "dietitian"),
    "nutri":             ("amenity", "dietitian"),
    "veterinário":       ("amenity", "veterinary"),
    "veterinario":       ("amenity", "veterinary"),
    "pet":               ("amenity", "veterinary"),
    "farmácia":          ("amenity", "pharmacy"),
    "farmacia":          ("amenity", "pharmacy"),
    "padaria":           ("shop",    "bakery"),
    "floricult":         ("shop",    "florist"),
    "imobiliária":       ("shop",    "estate_agent"),
    "imobiliaria":       ("shop",    "estate_agent"),
    "mecânica":          ("shop",    "car_repair"),
    "mecanica":          ("shop",    "car_repair"),
    "supermercado":      ("shop",    "supermarket"),
    "contabilid":        ("office",  "accountant"),
    "advocacia":         ("amenity", "lawyers"),
    "advogado":          ("amenity", "lawyers"),
}


def parse_search_term(termo: str) -> tuple[str, str, str]:
    t = termo.lower().strip()
    location = "São Paulo, Brasil"
    business = t

    for sep in [" em ", " in ", ", ", " - "]:
        if sep in t:
            parts = t.split(sep, 1)
            business = parts[0].strip()
            loc = parts[1].strip()
            if "brasil" not in loc.lower():
                location = f"{loc}, Brasil"
            else:
                location = loc
            break

    osm_key, osm_value = "amenity", "restaurant"
    for keyword, (k, v) in TERM_MAP.items():
        if keyword in business:
            osm_key, osm_value = k, v
            break

    return osm_key, osm_value, location


async def geocode(location: str) -> tuple[float, float]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": location, "format": "json", "limit": 1},
            headers={"Accept-Language": "pt-BR", "User-Agent": "VerticeCRM/2.0"},
        )
        data = r.json()
        if not data:
            raise ValueError(f"Localização não encontrada: '{location}'")
        return float(data[0]["lat"]), float(data[0]["lon"])


async def search_overpass(lat: float, lng: float, radius: int, key: str, value: str) -> list:
    query = (
        f"[out:json][timeout:25];"
        f'(node["{key}"="{value}"](around:{radius},{lat},{lng});'
        f'way["{key}"="{value}"](around:{radius},{lat},{lng}););'
        f"out center tags meta;"
    )
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    async with httpx.AsyncClient(timeout=30.0) as client:
        for ep in endpoints:
            try:
                r = await client.post(ep, data={"data": query})
                if r.status_code == 200:
                    return r.json().get("elements", [])
            except Exception:
                await asyncio.sleep(0.6)
    return []


def _get_phone(tags: dict) -> Optional[str]:
    return tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile")


def _get_website(tags: dict) -> Optional[str]:
    return tags.get("website") or tags.get("contact:website") or tags.get("url")


def _get_email(tags: dict) -> Optional[str]:
    return tags.get("email") or tags.get("contact:email")


def _addr(tags: dict) -> str:
    parts = [
        tags.get("addr:street", ""),
        tags.get("addr:housenumber", ""),
        tags.get("addr:suburb") or tags.get("addr:neighbourhood", ""),
        tags.get("addr:city", ""),
    ]
    return ", ".join(p for p in parts if p) or "—"


def calc_vertice_score(tags: dict) -> int:
    score = 0
    if not _get_website(tags):  score += 40
    if not _get_phone(tags):    score += 20
    if not tags.get("opening_hours"): score += 15
    if not _get_email(tags):    score += 10
    if not tags.get("image"):   score += 15
    return min(100, score)


def calc_ai_priority(tags: dict, osm_value: str, score_vertice: int) -> int:
    niche_base = AI_PRIORITY_MAP.get(osm_value, 3)
    niche_pts = min(5, round(niche_base / 2))

    bonus = 0
    if not _get_website(tags): bonus += 2
    if not _get_phone(tags):   bonus += 1
    if not tags.get("opening_hours"): bonus += 1
    if score_vertice >= 60:    bonus += 1

    return min(10, niche_pts + bonus)


async def hunt_leads(termo: str, raio: int = 3000, score_minimo: int = 30) -> list[dict]:
    osm_key, osm_value, location = parse_search_term(termo)
    lat, lng = await geocode(location)
    elements = await search_overpass(lat, lng, raio, osm_key, osm_value)

    leads = []
    for el in elements:
        tags = el.get("tags", {})
        if not tags.get("name"):
            continue

        score = calc_vertice_score(tags)
        if score < score_minimo:
            continue

        el_lat = el.get("lat") or (el.get("center") or {}).get("lat")
        el_lng = el.get("lon") or (el.get("center") or {}).get("lon")
        ai_p = calc_ai_priority(tags, osm_value, score)

        leads.append({
            "nome":          tags["name"],
            "empresa":       tags["name"],
            "telefone":      _get_phone(tags),
            "email":         _get_email(tags),
            "linkedin":      None,
            "cnpj":          None,
            "status":        "Novo",
            "ai_priority":   ai_p,
            "segmento":      osm_value.replace("_", " ").title(),
            "endereco":      _addr(tags),
            "score_vertice": score,
            "lat":           el_lat,
            "lng":           el_lng,
            "website":       _get_website(tags),
            "osm_id":        str(el.get("id")),
        })

    leads.sort(key=lambda x: (x["ai_priority"], x["score_vertice"]), reverse=True)
    return leads

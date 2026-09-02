"""Prospect search providers - modular architecture (V2.1).

Real Google Places provider now shipping. Mock stays available for demo/test.
All keys are read from server-side env vars only — never exposed to frontend.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
import os
import random
import httpx
from models import SearchCriteria


class ProspectSearchProvider(ABC):
    key: str = "base"
    label: str = "Base"
    requires_credentials: bool = False
    test_mode_only: bool = False

    def is_configured(self, org_integration: Optional[dict] = None) -> bool:
        return True

    @abstractmethod
    async def search(self, criteria: SearchCriteria) -> List[dict]:
        raise NotImplementedError


# ---------- Mock provider (Test Mode) ----------
CH_CITIES = [
    ("Lausanne", "1000", "VD"), ("Morges", "1110", "VD"), ("Renens", "1020", "VD"),
    ("Nyon", "1260", "VD"), ("Vevey", "1800", "VD"), ("Yverdon", "1400", "VD"),
    ("Genève", "1200", "GE"), ("Carouge", "1227", "GE"),
    ("Fribourg", "1700", "FR"), ("Bulle", "1630", "FR"),
    ("Neuchâtel", "2000", "NE"), ("La Chaux-de-Fonds", "2300", "NE"),
    ("Sion", "1950", "VS"), ("Martigny", "1920", "VS"),
    ("Berne", "3000", "BE"), ("Bienne", "2500", "BE"),
    ("Zurich", "8000", "ZH"), ("Winterthur", "8400", "ZH"),
    ("Bâle", "4000", "BS"), ("Lucerne", "6000", "LU"),
    ("Lugano", "6900", "TI"), ("Bellinzone", "6500", "TI"),
]

SUFFIXES = ["SA", "Sàrl", "& Fils", "Group", "Services", "AG", "GmbH"]
FIRST_NAMES = ["Martin", "Dubois", "Favre", "Rossi", "Meyer", "Schmid", "Weber",
               "Baumann", "Perret", "Aubert", "Chatelain", "Blanc", "Piaget"]


def _pick_suffix() -> str:
    return random.choice(SUFFIXES)


def _slug(name: str) -> str:
    return name.lower().replace(" ", "").replace("é", "e").replace("è", "e").replace("&", "and")


class MockProspectProvider(ProspectSearchProvider):
    key = "mock"
    label = "Mock (démo / Test Mode)"
    test_mode_only = True

    def is_configured(self, org_integration=None) -> bool:
        return True

    async def search(self, criteria: SearchCriteria) -> List[dict]:
        random.seed(hash(criteria.campaign_name + criteria.industry) & 0xFFFFFFFF)
        n = min(criteria.max_results, 30)
        results = []
        target_city = criteria.city
        city_pool = [c for c in CH_CITIES if not target_city or target_city.lower() in c[0].lower()]
        if not city_pool:
            city_pool = CH_CITIES
        for i in range(n):
            city, zip_base, canton = random.choice(city_pool)
            surname = random.choice(FIRST_NAMES)
            company = f"{criteria.industry.title()} {surname} {_pick_suffix()}"
            slug = _slug(surname)
            has_site = random.random() > 0.15
            has_email = random.random() > 0.25
            has_phone = random.random() > 0.10
            website = f"https://www.{slug}-{criteria.industry.lower().replace(' ', '')}.ch" if has_site else None
            email = f"info@{slug}-{criteria.industry.lower().replace(' ', '')}.ch" if has_email else None
            phone = f"+41 {random.randint(21, 91)} {random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}" if has_phone else None
            results.append({
                "company_name": company,
                "industry": criteria.industry,
                "description": f"{criteria.industry.title()} basé à {city}. Entreprise établie proposant ses services aux particuliers et PME de la région.",
                "website": website,
                "email": email,
                "phone": phone,
                "address": f"Rue de {random.choice(['la Gare', 'l Église', 'Bourg', 'la Poste'])} {random.randint(1, 90)}",
                "postal_code": zip_base,
                "city": city,
                "canton": canton,
                "country": criteria.country or "CH",
                "source": self.key,
                "source_provider": self.key,
                "source_url": None,
                "data_type": "demo",
            })
        return results


# ---------- Google Places (real) ----------
class GooglePlacesProvider(ProspectSearchProvider):
    """Google Places (New) — Text Search + Place Details.
    Docs: https://developers.google.com/maps/documentation/places/web-service/text-search
    Requires GOOGLE_PLACES_API_KEY in the server environment.
    Never exposes the key to the frontend."""
    key = "google_places"
    label = "Google Places"
    requires_credentials = True

    def _api_key(self) -> Optional[str]:
        return os.environ.get("GOOGLE_PLACES_API_KEY") or None

    def is_configured(self, org_integration=None) -> bool:
        return bool(self._api_key())

    async def validate(self) -> tuple[bool, Optional[str]]:
        """Verify that the API key works. Returns (ok, error_message)."""
        key = self._api_key()
        if not key:
            return False, "GOOGLE_PLACES_API_KEY not set"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    "https://places.googleapis.com/v1/places:searchText",
                    headers={
                        "Content-Type": "application/json",
                        "X-Goog-Api-Key": key,
                        "X-Goog-FieldMask": "places.id",
                    },
                    json={"textQuery": "test", "pageSize": 1},
                )
                if r.status_code == 200:
                    return True, None
                return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, str(e)[:200]

    async def search(self, criteria: SearchCriteria) -> List[dict]:
        key = self._api_key()
        if not key:
            raise RuntimeError("Google Places n'est pas configuré (GOOGLE_PLACES_API_KEY manquante).")

        # Build query
        location_parts = [criteria.city, criteria.canton, criteria.country]
        location = ", ".join([p for p in location_parts if p])
        query = f"{criteria.industry} {location}".strip()

        max_results = min(max(1, criteria.max_results), 20)
        field_mask = ",".join([
            "places.id", "places.displayName", "places.formattedAddress",
            "places.internationalPhoneNumber", "places.websiteUri",
            "places.googleMapsUri", "places.types",
            "places.primaryType", "places.primaryTypeDisplayName",
            "places.addressComponents",
        ])

        payload = {"textQuery": query, "pageSize": max_results}
        if criteria.country:
            payload["regionCode"] = criteria.country

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    "https://places.googleapis.com/v1/places:searchText",
                    headers={
                        "Content-Type": "application/json",
                        "X-Goog-Api-Key": key,
                        "X-Goog-FieldMask": field_mask,
                    },
                    json=payload,
                )
            if r.status_code != 200:
                raise RuntimeError(f"Google Places a répondu HTTP {r.status_code}")
            data = r.json()
        except httpx.RequestError as e:
            raise RuntimeError(f"Erreur réseau Google Places: {e}")

        results: List[dict] = []
        for place in (data.get("places") or [])[:max_results]:
            # Extract city / postal_code / country from address components
            city = None
            postal_code = None
            canton = None
            country = criteria.country or "CH"
            for comp in place.get("addressComponents", []) or []:
                types = comp.get("types", [])
                if "locality" in types or "postal_town" in types:
                    city = comp.get("longText") or city
                elif "administrative_area_level_1" in types:
                    canton = comp.get("shortText") or comp.get("longText")
                elif "postal_code" in types:
                    postal_code = comp.get("longText")
                elif "country" in types:
                    country = comp.get("shortText") or country

            name = (place.get("displayName") or {}).get("text") or ""
            primary_type = place.get("primaryTypeDisplayName", {}).get("text") or place.get("primaryType") or criteria.industry
            results.append({
                "company_name": name,
                "industry": primary_type,
                "description": None,  # never fabricate — leave to AI hypothesis
                "website": place.get("websiteUri"),
                "email": None,  # Google Places never returns emails
                "phone": place.get("internationalPhoneNumber"),
                "address": place.get("formattedAddress"),
                "postal_code": postal_code,
                "city": city or criteria.city,
                "canton": canton or criteria.canton,
                "country": country,
                "source": self.key,
                "source_provider": self.key,
                "source_url": place.get("googleMapsUri"),
                "external_id": place.get("id"),
                "data_type": "real",
            })
        return results


# ---------- Custom API adapter (stub) ----------
class CustomAPIProvider(ProspectSearchProvider):
    key = "custom_api"
    label = "API personnalisée"
    requires_credentials = True

    def is_configured(self, org_integration=None) -> bool:
        if not org_integration:
            return False
        cfg = org_integration.get("config") or {}
        return bool(cfg.get("base_url")) and org_integration.get("status") == "connected"

    async def search(self, criteria: SearchCriteria) -> List[dict]:
        raise RuntimeError("Custom API provider not yet configured for this organization.")


# ---------- CSV import provider (import-only) ----------
class CSVImportProvider(ProspectSearchProvider):
    key = "csv"
    label = "Import CSV"
    requires_credentials = False

    def is_configured(self, org_integration=None) -> bool:
        return True

    async def search(self, criteria: SearchCriteria) -> List[dict]:
        return []


# ---------- Registry ----------
_registry: dict[str, ProspectSearchProvider] = {}


def register(provider: ProspectSearchProvider) -> None:
    _registry[provider.key] = provider


def get_provider(key: str = "mock") -> Optional[ProspectSearchProvider]:
    """Return requested provider or None. Never silently fall back to mock."""
    return _registry.get(key)


def list_providers() -> List[dict]:
    return [{
        "key": p.key,
        "label": p.label,
        "requires_credentials": p.requires_credentials,
        "test_mode_only": p.test_mode_only,
    } for p in _registry.values()]


# Bootstrap providers
register(MockProspectProvider())
register(GooglePlacesProvider())
register(CustomAPIProvider())
register(CSVImportProvider())

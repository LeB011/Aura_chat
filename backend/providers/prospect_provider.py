"""Prospect search providers - modular architecture (V2.1).

Real Google Places provider now shipping. Mock stays available for demo/test.
All keys are read from server-side env vars only — never exposed to frontend.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
import os
import random
import re
from urllib.parse import urlparse
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


# ---------- TinyFish Search + Fetch (real, free tier) ----------
class TinyFishProvider(ProspectSearchProvider):
    """TinyFish Search + Fetch provider.

    V2 "Clean Companies": Search is treated as discovery only. Aura then
    validates each candidate as a likely first-party business website and
    derives a company name from the fetched site, not blindly from the search
    result title. Generic articles/directories are rejected.
    """
    key = "tinyfish"
    label = "TinyFish Search + Fetch"
    requires_credentials = True

    SEARCH_URL = "https://api.search.tinyfish.ai"
    FETCH_URL = "https://api.fetch.tinyfish.ai"

    EXCLUDED_DOMAINS = [
        "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
        "tiktok.com", "x.com", "twitter.com", "wikipedia.org",
        "local.ch", "search.ch", "yelp.com", "tripadvisor.com",
        "indeed.com", "jobs.ch", "glassdoor.com", "pinterest.com",
        "yellowpages.com", "pagesjaunes.fr", "118000.fr", "annuaire.ch",
        "moneyhouse.ch", "kompass.com", "firmenabc.at", "trustpilot.com",
    ]

    DIRECTORY_HOST_HINTS = (
        "directory", "annuaire", "guide", "listing", "top10", "top-10",
        "best", "meilleur", "vergleich", "branchenbuch", "business-list",
    )

    GENERIC_TITLE_HINTS = (
        "top ", "top-", "meilleur", "meilleures", "meilleurs", "best ",
        "annuaire", "liste des", "liste de", "entreprises à", "entreprises de",
        "électricien à", "electricien à", "électriciens à", "electriciens à",
        "plombier à", "plombiers à", "restaurants à", "services à",
        "comparatif", "comparaison", "guide ", "trouver ", "recherche ",
        "télécommunications", "suisse romande", "lausanne et suisse romande",
    )

    LEGAL_SUFFIXES = (
        "sa", "sàrl", "sarl", "sagl", "ag", "gmbh", "snc", "sàrl.",
        "s.a.", "s.a", "sarl.", "sàrl", "société", "services", "service",
        "group", "groupe", "solutions", "technique", "techniques",
    )

    GENERIC_EMAIL_PREFIXES = (
        "info", "contact", "hello", "office", "admin", "sales",
        "commercial", "vente", "support", "secretariat", "accueil",
        "service", "mail", "team",
    )

    def _api_key(self) -> Optional[str]:
        return os.environ.get("TINYFISH_API_KEY") or None

    def is_configured(self, org_integration=None) -> bool:
        return bool(self._api_key())

    async def validate(self) -> tuple[bool, Optional[str]]:
        key = self._api_key()
        if not key:
            return False, "TINYFISH_API_KEY manquante"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    self.SEARCH_URL,
                    headers={"X-API-Key": key},
                    params={"query": "electricien Lausanne entreprise", "location": "CH", "language": "fr", "page": 0},
                )
            if r.status_code == 200:
                return True, None
            return False, f"HTTP {r.status_code}: {r.text[:180]}"
        except Exception as e:
            return False, str(e)[:180]

    @staticmethod
    def _language(criteria: SearchCriteria) -> str:
        if criteria.language and criteria.language != "auto":
            return criteria.language
        canton = (criteria.canton or "").upper()
        if canton in {"ZH", "BE", "LU", "UR", "SZ", "OW", "NW", "GL", "ZG", "SO", "BS", "BL", "SH", "AR", "AI", "SG", "AG", "TG"}:
            return "de"
        if canton == "TI":
            return "it"
        return "fr"

    @staticmethod
    def _ensure_url(url: str) -> str:
        if not url:
            return ""
        return url if url.startswith(("http://", "https://")) else f"https://{url}"

    @staticmethod
    def _root_url(url: str) -> str:
        try:
            parsed = urlparse(TinyFishProvider._ensure_url(url))
            return f"{parsed.scheme or 'https'}://{parsed.netloc}" if parsed.netloc else TinyFishProvider._ensure_url(url)
        except Exception:
            return TinyFishProvider._ensure_url(url)

    @staticmethod
    def _domain(url: str) -> str:
        try:
            return urlparse(TinyFishProvider._ensure_url(url)).netloc.lower().removeprefix("www.")
        except Exception:
            return ""

    @staticmethod
    def _normalize(value: str) -> str:
        value = (value or "").lower().strip()
        value = value.replace("é", "e").replace("è", "e").replace("ê", "e")
        value = value.replace("à", "a").replace("â", "a").replace("ä", "a")
        value = value.replace("ö", "o").replace("ü", "u").replace("î", "i")
        return re.sub(r"\s+", " ", value)

    def _is_excluded_domain(self, domain: str) -> bool:
        d = (domain or "").lower().removeprefix("www.")
        if any(d == x or d.endswith("." + x) for x in self.EXCLUDED_DOMAINS):
            return True
        return any(h in d for h in self.DIRECTORY_HOST_HINTS)

    def _looks_generic_title(self, title: str, criteria: SearchCriteria) -> bool:
        t = self._normalize(title)
        if not t:
            return True
        if any(self._normalize(h) in t for h in self.GENERIC_TITLE_HINTS):
            return True
        # Search-result headlines such as "Electricien, Lausanne" are not company names.
        industry = self._normalize(criteria.industry)
        city = self._normalize(criteria.city or "")
        stripped = re.sub(r"[^a-z0-9 ]", " ", t)
        words = set(stripped.split())
        if industry and city and len(words) <= 6 and industry in t and city in t:
            return True
        if t in {industry, city, f"{industry} {city}".strip()}:
            return True
        return False

    @staticmethod
    def _domain_brand(domain: str) -> str:
        stem = (domain or "").split(".")[0].replace("-", " ").replace("_", " ").strip()
        # very short / generic domains are poor evidence for a business name
        if len(stem) < 3:
            return ""
        return " ".join(x.capitalize() for x in stem.split())[:120]

    def _candidate_name_from_title(self, title: str, criteria: SearchCriteria) -> Optional[str]:
        if not title:
            return None
        # Titles often look like "Company SA | Electricien Lausanne".
        parts = [x.strip(" \t-–—|") for x in re.split(r"\s*[|–—]\s*|\s+-\s+", title) if x.strip()]
        ranked = []
        for p in parts:
            if len(p) < 2 or len(p) > 100 or self._looks_generic_title(p, criteria):
                continue
            score = 0
            pn = self._normalize(p)
            if any(re.search(rf"\b{re.escape(self._normalize(s))}\b", pn) for s in self.LEGAL_SUFFIXES):
                score += 4
            if 1 < len(p.split()) <= 7:
                score += 2
            if criteria.city and self._normalize(criteria.city) not in pn:
                score += 1
            if criteria.industry and self._normalize(criteria.industry) not in pn:
                score += 1
            ranked.append((score, -len(p), p))
        if ranked:
            ranked.sort(reverse=True)
            return ranked[0][2][:120]
        return None

    def _extract_company_name_from_text(self, text: str, domain: str, criteria: SearchCriteria) -> Optional[str]:
        """Extract high-confidence names from fetched homepage markdown/text."""
        if not text:
            return None
        lines = [re.sub(r"\s+", " ", x).strip(" #*\t") for x in text.splitlines()]
        lines = [x for x in lines if 2 <= len(x) <= 110]
        ranked = []
        brand = self._normalize(self._domain_brand(domain))
        for idx, line in enumerate(lines[:140]):
            if self._looks_generic_title(line, criteria):
                continue
            ln = self._normalize(line)
            score = 0
            if any(re.search(rf"\b{re.escape(self._normalize(s))}\b", ln) for s in self.LEGAL_SUFFIXES):
                score += 7
            if brand and brand in ln:
                score += 5
            if idx < 15:
                score += 3
            if 1 < len(line.split()) <= 8:
                score += 2
            if "copyright" in ln or "©" in line:
                score += 2
                line = re.sub(r"(?i).*?(?:copyright|©)\s*(?:\d{4}\s*)?", "", line).strip(" -|,") or line
            if criteria.city and self._normalize(criteria.city) in ln:
                score -= 1
            if criteria.industry and ln == self._normalize(criteria.industry):
                score -= 4
            if score >= 6:
                ranked.append((score, -idx, -len(line), line))
        if ranked:
            ranked.sort(reverse=True)
            return ranked[0][3][:120]
        return None

    def _choose_company_name(self, fetched: dict, item: dict, domain: str, criteria: SearchCriteria) -> tuple[Optional[str], int]:
        text = fetched.get("text") if isinstance(fetched.get("text"), str) else ""
        fetched_title = fetched.get("title") if isinstance(fetched.get("title"), str) else ""
        search_title = item.get("title") if isinstance(item.get("title"), str) else ""

        from_text = self._extract_company_name_from_text(text, domain, criteria)
        if from_text:
            return from_text, 95

        from_fetched_title = self._candidate_name_from_title(fetched_title, criteria)
        if from_fetched_title:
            return from_fetched_title, 85

        from_search_title = self._candidate_name_from_title(search_title, criteria)
        if from_search_title:
            return from_search_title, 68

        # Domain brand is acceptable only when the domain itself looks branded.
        brand = self._domain_brand(domain)
        if brand and not self._looks_generic_title(brand, criteria):
            return brand, 58
        return None, 0

    def _extract_generic_email(self, text: str) -> Optional[str]:
        emails = re.findall(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text or "")
        seen = []
        for email in emails:
            e = email.strip(".,;:()[]<>").lower()
            if e not in seen:
                seen.append(e)
        for e in seen:
            prefix = e.split("@", 1)[0]
            if prefix.startswith(self.GENERIC_EMAIL_PREFIXES):
                return e
        return None

    @staticmethod
    def _extract_phone(text: str) -> Optional[str]:
        patterns = [
            r"(?<!\d)(?:\+41|0041)\s?(?:\(0\)\s?)?\d{2}[ .\-/]?\d{3}(?:[ .\-/]?\d{2}){2}(?!\d)",
            r"(?<!\d)0\d{2}[ .\-/]?\d{3}[ .\-/]?\d{2}[ .\-/]?\d{2}(?!\d)",
            r"(?<!\d)(?:\+33|0033)\s?[1-9](?:[ .\-/]?\d{2}){4}(?!\d)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text or "")
            if m:
                return re.sub(r"\s+", " ", m.group(0)).strip()
        return None

    async def search(self, criteria: SearchCriteria) -> List[dict]:
        key = self._api_key()
        if not key:
            raise RuntimeError("TinyFish n'est pas configuré (TINYFISH_API_KEY manquante).")

        requested = min(max(1, criteria.max_results), 50)
        language = self._language(criteria)
        location = (criteria.country or "CH").upper()
        place = " ".join([p for p in [criteria.city, criteria.canton] if p]).strip()

        # Ask for more candidates than requested because V2 deliberately rejects noise.
        candidate_target = min(60, max(requested * 3, 20))
        query = f'"{criteria.industry}" {place} entreprise société contact'.strip()
        purpose = (
            f"Identifier uniquement des entreprises réelles de type {criteria.industry} "
            f"dans {place or location}. Retourner leurs sites officiels. "
            "Exclure annuaires, articles, comparatifs, pages Top 10, réseaux sociaux et pages de catégories."
        )

        headers = {"X-API-Key": key}
        candidates: list[dict] = []
        seen_domains: set[str] = set()
        pages_to_try = min(8, max(2, (candidate_target + 9) // 10))

        async with httpx.AsyncClient(timeout=28.0, follow_redirects=True) as client:
            for page in range(pages_to_try):
                r = await client.get(
                    self.SEARCH_URL,
                    headers=headers,
                    params={
                        "query": query,
                        "purpose": purpose,
                        "location": location,
                        "language": language,
                        "exclude_domains": ",".join(self.EXCLUDED_DOMAINS),
                        "page": page,
                    },
                )
                if r.status_code != 200:
                    raise RuntimeError(f"TinyFish Search a répondu HTTP {r.status_code}: {r.text[:160]}")
                for item in (r.json().get("results") or []):
                    url = self._ensure_url(item.get("url") or "")
                    domain = self._domain(url)
                    title = (item.get("title") or "").strip()
                    if not url or not domain or domain in seen_domains or self._is_excluded_domain(domain):
                        continue
                    # Reject obvious editorial/directory results before spending a Fetch call.
                    path = (urlparse(url).path or "").lower()
                    if any(h in path for h in ("/blog/", "/article", "/actualite", "/news/", "/guide/", "/top-", "/comparatif")):
                        continue
                    if title and self._looks_generic_title(title, criteria) and len(path.strip("/")) > 0:
                        continue
                    seen_domains.add(domain)
                    candidates.append({**item, "url": url, "domain": domain})
                    if len(candidates) >= candidate_target:
                        break
                if len(candidates) >= candidate_target:
                    break

            if not candidates:
                return []

            # Fetch ROOT homepages; this is much better for brand/company identity than
            # fetching whatever deep page Search happened to return.
            roots = []
            root_to_domain = {}
            for c in candidates:
                root = self._root_url(c["url"])
                if root and root not in root_to_domain:
                    roots.append(root)
                    root_to_domain[root] = c["domain"]

            fetched_by_domain: dict[str, dict] = {}
            for start in range(0, len(roots), 10):
                batch = roots[start:start + 10]
                fr = await client.post(
                    self.FETCH_URL,
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "urls": batch,
                        "format": "markdown",
                        "links": False,
                        "ttl": 3600,
                        "per_url_timeout_ms": 20000,
                        "purpose": "Lire la page d'accueil officielle pour identifier précisément le nom de l'entreprise et ses coordonnées publiques.",
                    },
                )
                if fr.status_code == 200:
                    for fetched in (fr.json().get("results") or []):
                        raw_url = fetched.get("final_url") or fetched.get("url") or ""
                        dom = self._domain(raw_url)
                        if dom:
                            fetched_by_domain[dom] = fetched

        results: List[dict] = []
        for item in candidates:
            if len(results) >= requested:
                break
            domain = item["domain"]
            fetched = fetched_by_domain.get(domain) or {}
            text = fetched.get("text") if isinstance(fetched.get("text"), str) else ""
            description = fetched.get("description") or item.get("snippet") or None
            final_url = self._ensure_url(fetched.get("final_url") or self._root_url(item.get("url") or ""))
            website = self._root_url(final_url)

            company_name, confidence = self._choose_company_name(fetched, item, domain, criteria)
            # Clean-company principle: do not invent a prospect just to hit the requested count.
            if not company_name or confidence < 58 or self._looks_generic_title(company_name, criteria):
                continue

            email = self._extract_generic_email(text)
            phone = self._extract_phone(text)
            results.append({
                "company_name": company_name,
                "industry": criteria.industry,
                "description": (description[:600] if isinstance(description, str) else None),
                "website": website or None,
                "email": email,
                "phone": phone,
                "address": None,
                "postal_code": criteria.postal_code,
                "city": criteria.city,
                "canton": criteria.canton,
                "country": criteria.country or "CH",
                "source": self.key,
                "source_provider": self.key,
                "source_url": item.get("url"),
                "external_id": f"tinyfish:{domain}",
                "data_type": "real",
                "source_confidence": confidence,
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
register(TinyFishProvider())
register(CustomAPIProvider())
register(CSVImportProvider())

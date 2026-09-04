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

    V3 "Verified Businesses" treats TinyFish Search as discovery only.
    It expands broad user intents (e.g. "administration") into concrete
    business-service concepts, gathers candidates from several semantic queries,
    fetches first-party homepages, then verifies that each retained result is a
    real company whose own site actually matches the requested activity.

    No LLM key is required for this provider. The behaviour is deliberately
    conservative: returning fewer verified companies is preferred over filling
    the requested count with job boards, directories or editorial pages.
    """
    key = "tinyfish"
    label = "TinyFish — entreprises vérifiées"
    requires_credentials = True

    SEARCH_URL = "https://api.search.tinyfish.ai"
    FETCH_URL = "https://api.fetch.tinyfish.ai"

    EXCLUDED_DOMAINS = [
        # Social / encyclopaedia
        "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
        "tiktok.com", "x.com", "twitter.com", "wikipedia.org", "pinterest.com",
        # Swiss/global directories & review sites
        "local.ch", "search.ch", "yelp.com", "tripadvisor.com", "trustpilot.com",
        "moneyhouse.ch", "kompass.com", "annuaire.ch", "yellowpages.com",
        "pagesjaunes.fr", "118000.fr", "firmenabc.at", "branchenbuch.ch",
        # Jobs / recruitment / classifieds
        "indeed.com", "indeed.ch", "jobs.ch", "jobup.ch", "jobscout24.ch",
        "job-room.ch", "glassdoor.com", "jooble.org", "jooble.ch", "randstad.ch",
        "adecco.ch", "manpower.ch", "careerplus.ch", "jobcloud.ch", "talendo.ch",
        # Aggregators / comparison / marketplace
        "comparis.ch", "ofri.ch", "houzy.ch", "renovero.ch", "deindeal.ch",
    ]

    DIRECTORY_HOST_HINTS = (
        "directory", "annuaire", "guide", "listing", "top10", "top-10",
        "best", "meilleur", "vergleich", "branchenbuch", "business-list",
        "jobs", "job", "career", "emploi", "stellen", "recrut", "talent",
    )

    # Search/page titles that describe a category, job or article rather than a company.
    GENERIC_TITLE_HINTS = (
        "top ", "top-", "meilleur", "meilleures", "meilleurs", "best ",
        "annuaire", "liste des", "liste de", "entreprises à", "entreprises de",
        "comparatif", "comparaison", "guide ", "trouver ", "recherche ",
        "offre d'emploi", "offres d'emploi", "emploi ", "jobs ", "job ",
        "cfc", "apprentissage", "apprenti", "carrière", "carriere", "poste vacant",
        "h/f", "h/f/d", "m/f/d", "100%", "80%", "60%", "télécommunications",
        "suisse romande", "lausanne et suisse romande", "nos services", "solutions énergétiques",
        "service rapide", "à propos de", "depuis des années", "entreprise d’électricité suisse",
    )

    NON_COMPANY_PAGE_HINTS = (
        "/job", "/jobs", "/emploi", "/career", "/careers", "/stellen",
        "/blog", "/article", "/actualite", "/news", "/guide", "/top-",
        "/comparatif", "/category", "/categorie", "/tag/", "/search",
    )

    LEGAL_SUFFIXES = (
        "sa", "sàrl", "sarl", "sagl", "ag", "gmbh", "snc", "s.a.", "s.a",
        "sarl.", "société", "societe", "services", "service", "group", "groupe",
        "solutions", "consulting", "conseil", "fiduciaire", "bureau", "atelier",
    )

    BUSINESS_MARKERS = (
        "nos services", "notre entreprise", "à propos", "a propos", "contact",
        "nous contacter", "qui sommes-nous", "qui sommes nous", "équipe", "equipe",
        "clients", "prestations", "devis", "adresse", "téléphone", "telephone",
        "mentions légales", "mentions legales", "impressum",
    )

    # Broad intent -> concrete business concepts. This is semantic expansion, not a
    # replacement list: the original user term is always retained too.
    INTENT_EXPANSIONS = {
        "administration": [
            "services administratifs", "assistance administrative", "secrétariat externalisé",
            "secretariat externalise", "gestion administrative", "office management",
            "back office", "fiduciaire", "bureau administratif", "support administratif PME",
        ],
        "administratif": [
            "services administratifs", "assistance administrative", "secrétariat externalisé",
            "gestion administrative", "office management", "back office", "fiduciaire",
        ],
        "electricien": ["électricien", "installations électriques", "entreprise électrique", "dépannage électrique"],
        "électricien": ["électricien", "installations électriques", "entreprise électrique", "dépannage électrique"],
        "plombier": ["plomberie", "sanitaire", "chauffage sanitaire", "dépannage plomberie"],
        "informatique": ["services informatiques", "support IT", "infogérance", "MSP", "solutions informatiques PME"],
        "marketing": ["agence marketing", "marketing digital", "communication", "agence web"],
        "comptabilite": ["fiduciaire", "comptabilité", "tenue de comptes", "fiscalité PME"],
        "comptabilité": ["fiduciaire", "comptabilité", "tenue de comptes", "fiscalité PME"],
        "animaux": ["services animaliers", "pension pour animaux", "toilettage", "pet sitting", "vétérinaire"],
        "animal": ["services animaliers", "pension pour animaux", "toilettage", "pet sitting", "vétérinaire"],
    }

    GENERIC_EMAIL_PREFIXES = (
        "info", "contact", "hello", "office", "admin", "sales", "commercial",
        "vente", "support", "secretariat", "secrétariat", "accueil", "service", "team",
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
                    params={"query": "électricien Lausanne entreprise site officiel", "location": "CH", "language": "fr", "page": 0},
                )
            if r.status_code == 200:
                return True, None
            return False, f"HTTP {r.status_code}: {r.text[:180]}"
        except Exception as e:
            return False, str(e)[:180]

    @staticmethod
    def _language(criteria: SearchCriteria) -> str:
        if getattr(criteria, "language", None) and criteria.language != "auto":
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
        table = str.maketrans({
            "é":"e", "è":"e", "ê":"e", "ë":"e", "à":"a", "â":"a", "ä":"a",
            "ö":"o", "ô":"o", "ü":"u", "û":"u", "î":"i", "ï":"i", "ç":"c",
        })
        value = value.translate(table)
        return re.sub(r"\s+", " ", value)

    @classmethod
    def _tokens(cls, value: str) -> set[str]:
        value = cls._normalize(value)
        stop = {"de","du","des","la","le","les","un","une","et","a","au","aux","en","pour","sur","service","services","entreprise","societe"}
        return {w for w in re.findall(r"[a-z0-9]{3,}", value) if w not in stop}

    def _is_excluded_domain(self, domain: str) -> bool:
        d = (domain or "").lower().removeprefix("www.")
        if any(d == x or d.endswith("." + x) for x in self.EXCLUDED_DOMAINS):
            return True
        return any(h in d for h in self.DIRECTORY_HOST_HINTS)

    def _looks_generic_title(self, title: str, criteria: SearchCriteria) -> bool:
        t = self._normalize(title)
        if not t or len(t) > 140:
            return True
        if any(self._normalize(h) in t for h in self.GENERIC_TITLE_HINTS):
            return True
        # absurd IDs / hashes / tracking strings
        compact = re.sub(r"[^a-z0-9]", "", t)
        if len(compact) > 55 and sum(ch.isdigit() for ch in compact) > 8:
            return True
        if re.fullmatch(r"\d{3,}", compact or ""):
            return True
        industry = self._normalize(criteria.industry)
        city = self._normalize(criteria.city or "")
        words = set(re.sub(r"[^a-z0-9 ]", " ", t).split())
        if industry and city and len(words) <= 7 and industry in t and city in t:
            return True
        if t in {industry, city, f"{industry} {city}".strip()}:
            return True
        return False

    @staticmethod
    def _domain_brand(domain: str) -> str:
        stem = (domain or "").split(".")[0].replace("-", " ").replace("_", " ").strip()
        if len(stem) < 3 or stem.isdigit():
            return ""
        return " ".join(x.capitalize() for x in stem.split())[:120]

    def _candidate_name_from_title(self, title: str, criteria: SearchCriteria) -> Optional[str]:
        if not title:
            return None
        parts = [x.strip(" \t-–—|") for x in re.split(r"\s*[|–—]\s*|\s+-\s+|\s*::\s*", title) if x.strip()]
        ranked = []
        for p in parts:
            if len(p) < 2 or len(p) > 100 or self._looks_generic_title(p, criteria):
                continue
            score = 0
            pn = self._normalize(p)
            if any(re.search(rf"\b{re.escape(self._normalize(s))}\b", pn) for s in self.LEGAL_SUFFIXES):
                score += 5
            if 1 <= len(p.split()) <= 7:
                score += 2
            if criteria.city and self._normalize(criteria.city) not in pn:
                score += 1
            if criteria.industry and self._normalize(criteria.industry) not in pn:
                score += 1
            if not re.search(r"\b(emploi|job|cfc|100%|80%|60%)\b", pn):
                score += 2
            ranked.append((score, -len(p), p))
        if ranked:
            ranked.sort(reverse=True)
            return ranked[0][2][:120]
        return None

    def _extract_legal_company_name(self, text: str, domain: str, criteria: SearchCriteria) -> Optional[str]:
        """Extract a plausible legal/trading name, never an arbitrary service heading."""
        if not text:
            return None
        clean = re.sub(r"[\t\r]+", " ", text)
        legal = r"(?:SA|SÀRL|SARL|Sàrl|Sarl|AG|GmbH|SAGL|Sagl|SNC|S\.A\.|S\.A\.|Société anonyme)"
        # Capture short noun phrase ending with a Swiss legal suffix.
        patterns = [
            rf"(?m)([A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ0-9&'’._-]*(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ0-9&'’._-]+){{0,6}}\s+{legal})\b",
            rf"(?im)(?:raison sociale|entreprise|société|societe|firma|company)\s*[:\-]\s*([^\n|]{{2,90}}?\b{legal})\b",
        ]
        candidates=[]
        brand_tokens=self._tokens(self._domain_brand(domain))
        for pat in patterns:
            for m in re.finditer(pat, clean):
                name=re.sub(r"\s+", " ", m.group(1)).strip(" -|,.;:")
                name=re.sub(r"(?i)^(?:bienvenue chez|welcome to|willkommen bei|benvenuti da|à propos de|a propos de)\s+", "", name).strip()
                if self._looks_generic_title(name, criteria) or len(name.split()) > 9:
                    continue
                score=80
                if brand_tokens & self._tokens(name):
                    score += 15
                candidates.append((score, -len(name), name))
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][2][:120]
        return None

    def _candidate_name_from_title_strict(self, title: str, domain: str, criteria: SearchCriteria) -> Optional[str]:
        """Use page title only when it looks like a brand and aligns with the domain."""
        candidate=self._candidate_name_from_title(title, criteria)
        if not candidate:
            return None
        cn=self._normalize(candidate)
        generic_phrases=(
            "nos services", "solutions energetiques", "service rapide", "a propos de",
            "depuis des annees", "entreprise d electricite suisse", "electricien a",
            "electricien lausanne", "installation electrique", "depannage electrique",
        )
        if any(g in cn for g in generic_phrases):
            return None
        if len(candidate.split()) > 8 or len(candidate) > 90:
            return None
        brand_tokens=self._tokens(self._domain_brand(domain))
        cand_tokens=self._tokens(candidate)
        legal_hit=any(re.search(rf"\b{re.escape(self._normalize(s))}\b", cn) for s in self.LEGAL_SUFFIXES)
        if legal_hit or (brand_tokens and len(brand_tokens & cand_tokens) >= 1):
            return candidate[:120]
        return None

    def _choose_company_name(self, fetched: dict, item: dict, domain: str, criteria: SearchCriteria) -> tuple[Optional[str], int]:
        text = fetched.get("text") if isinstance(fetched.get("text"), str) else ""
        fetched_title = fetched.get("title") if isinstance(fetched.get("title"), str) else ""
        search_title = item.get("title") if isinstance(item.get("title"), str) else ""

        # 1) Legal name explicitly present on the official site.
        legal=self._extract_legal_company_name(text, domain, criteria)
        if legal:
            return legal, 98

        # 2) Homepage/page title, but only when it matches the site's own domain/brand.
        strict=self._candidate_name_from_title_strict(fetched_title, domain, criteria)
        if strict:
            return strict, 90
        strict=self._candidate_name_from_title_strict(search_title, domain, criteria)
        if strict:
            return strict, 82

        # 3) Domain brand is safer than inventing a name from an H1/service slogan.
        domain_brand=self._domain_brand(domain)
        if domain_brand and not self._looks_generic_title(domain_brand, criteria):
            tokens=self._tokens(domain_brand)
            if tokens and not any(x in self._normalize(domain_brand) for x in ("job", "emploi", "annuaire", "top", "guide")):
                return domain_brand, 72
        return None, 0

    DOMAIN_TAXONOMY = {
        "administratif": ("administratif", "administration", "secretariat", "secrétariat", "back office", "office management", "fiduciaire", "gestion administrative"),
        "informatique": ("informatique", "it ", "support it", "infogerance", "infogérance", "cyber", "logiciel", "software", "cloud", "msp"),
        "électricité": ("electricien", "électricien", "electrique", "électrique", "installation électrique", "courant fort", "courant faible"),
        "plomberie/chauffage": ("plomberie", "sanitaire", "chauffage", "thermique"),
        "marketing/communication": ("marketing", "communication", "agence web", "seo", "publicité", "publicite"),
        "comptabilité/fiduciaire": ("comptabilite", "comptabilité", "fiduciaire", "fiscalite", "fiscalité", "tenue de comptes"),
        "immobilier": ("immobilier", "immobiliere", "immobilière", "gérance", "gerance", "courtage"),
        "construction/artisanat": ("construction", "renovation", "rénovation", "peinture", "menuiserie", "maçonnerie", "maconnerie", "artisan"),
        "restauration/hôtellerie": ("restaurant", "restauration", "hotel", "hôtel", "traiteur"),
        "santé/bien-être": ("sante", "santé", "cabinet", "physio", "therapie", "thérapie", "bien-être", "bien etre"),
        "animaux": ("veterinaire", "vétérinaire", "animal", "animaux", "toilettage", "pension", "pet sitting"),
    }

    def _business_domain(self, text: str, criteria: SearchCriteria) -> str:
        """Classify the prospect domain while prioritising the user's requested domain.

        The search intent is the strongest signal: if the user searches for "peintre",
        a painter's page must not become "immobilier" just because the website mentions
        property owners or property management in its marketing copy. Only when the user
        query cannot be mapped to our taxonomy do we infer the category from page content.
        """
        requested=self._normalize(criteria.industry or "")

        # 1) Requested domain has priority. Use exact/semantic keyword mapping on the query only.
        requested_scores=[]
        for label, terms in self.DOMAIN_TAXONOMY.items():
            score=0
            for term in terms:
                nt=self._normalize(term)
                if nt and (nt in requested or requested in nt):
                    score += 2 if nt == requested else 1
            if score:
                requested_scores.append((score, label))
        if requested_scores:
            requested_scores.sort(reverse=True)
            return requested_scores[0][1]

        # 2) Otherwise infer from the verified first-party page.
        corpus=self._normalize((text or "")[:25000])
        scores=[]
        for label, terms in self.DOMAIN_TAXONOMY.items():
            score=sum(1 for term in terms if self._normalize(term) in corpus)
            if score:
                scores.append((score, label))
        if scores:
            scores.sort(reverse=True)
            return scores[0][1]

        # 3) Unknown custom domain: show the user's request rather than inventing a category.
        return requested[:60] or "autre"

    def _extract_founded_year(self, text: str) -> tuple[Optional[int], Optional[str], int]:
        """Extract founding year from explicit first-party wording only. Unknown stays unknown."""
        if not text:
            return None, None, 0
        now=2026
        patterns=[
            (r"(?i)\b(?:fond(?:e|é|ée|ee|ation|ée en)|cré(?:e|é|ée|ee) en|depuis)\s+(?:l['’]année\s+)?(18\d{2}|19\d{2}|20[0-2]\d)\b", "site officiel", 85),
            (r"(?i)\b(?:founded|established|since)\s+(?:in\s+)?(18\d{2}|19\d{2}|20[0-2]\d)\b", "site officiel", 85),
            (r"(?i)\b(?:gegründet|gegrundet|seit)\s+(?:im\s+Jahr\s+)?(18\d{2}|19\d{2}|20[0-2]\d)\b", "site officiel", 85),
            (r"(?i)\b(?:fondata|dal)\s+(?:nel\s+)?(18\d{2}|19\d{2}|20[0-2]\d)\b", "site officiel", 80),
        ]
        for pat, source, conf in patterns:
            m=re.search(pat, text[:60000])
            if m:
                year=int(m.group(1))
                if 1800 <= year <= now:
                    return year, source, conf
        return None, None, 0

    def _intent_terms(self, industry: str) -> list[str]:
        raw = (industry or "").strip()
        norm = self._normalize(raw)
        terms = [raw] if raw else []
        # exact and containment matches allow "service administratif" etc.
        for key, vals in self.INTENT_EXPANSIONS.items():
            nk = self._normalize(key)
            if norm == nk or nk in norm or norm in nk:
                terms.extend(vals)
        # Generic fallback: retain meaningful words and create business-oriented variants.
        if raw:
            terms.extend([f"entreprise {raw}", f"services {raw}", f"prestataire {raw}"])
        dedup=[]; seen=set()
        for t in terms:
            n=self._normalize(t)
            if n and n not in seen:
                seen.add(n); dedup.append(t)
        return dedup[:10]

    def _semantic_query_plan(self, criteria: SearchCriteria) -> list[str]:
        place = " ".join([p for p in [criteria.city, criteria.canton, criteria.country] if p]).strip()
        terms = self._intent_terms(criteria.industry)
        queries=[]
        for term in terms[:7]:
            queries.append(f'"{term}" {place} entreprise site officiel contact'.strip())
        # One broad query helps uncommon industries where exact wording is poor.
        queries.append(f'{criteria.industry} {place} PME société prestations contact'.strip())
        out=[]; seen=set()
        for q in queries:
            n=self._normalize(q)
            if n not in seen:
                seen.add(n); out.append(q)
        return out[:8]

    def _activity_relevance(self, text: str, criteria: SearchCriteria) -> tuple[int, list[str]]:
        """Score whether first-party site actually represents requested activity."""
        corpus = self._normalize(text[:50000])
        if not corpus:
            return 0, []
        concepts = self._intent_terms(criteria.industry)
        matched=[]
        score=0
        # Phrase matches are strongest.
        for concept in concepts:
            nc=self._normalize(concept)
            if len(nc) >= 4 and nc in corpus:
                matched.append(concept)
                score += 18 if concept == criteria.industry else 12
        # Token overlap catches inflections and wording variants.
        requested_tokens=set()
        for c in concepts:
            requested_tokens |= self._tokens(c)
        site_tokens=self._tokens(corpus)
        overlap=requested_tokens & site_tokens
        score += min(30, len(overlap)*6)
        # First-party business signals.
        markers=sum(1 for m in self.BUSINESS_MARKERS if self._normalize(m) in corpus)
        score += min(18, markers*3)
        # Job-board / recruitment-heavy pages should fail verification.
        job_hits=sum(1 for x in ("offres d'emploi","offre d'emploi","postes vacants","candidature","job alert","nos offres d emploi") if self._normalize(x) in corpus)
        if job_hits >= 2:
            score -= 35
        return max(0, min(100, score)), matched[:8]

    def _extract_generic_email(self, text: str, domain: str = "") -> Optional[str]:
        emails = re.findall(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text or "")
        seen=[]
        for email in emails:
            e=email.strip(".,;:()[]<>").lower()
            if e not in seen:
                seen.append(e)
        domain=(domain or "").lower()
        # Prefer generic address on same company domain.
        for e in seen:
            prefix, host=e.split("@",1)
            if domain and (host == domain or host.endswith("."+domain)) and prefix.startswith(self.GENERIC_EMAIL_PREFIXES):
                return e
        for e in seen:
            prefix=e.split("@",1)[0]
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
            m=re.search(pattern, text or "")
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
        headers = {"X-API-Key": key}

        # Multiple semantically-expanded searches mimic a human researcher better
        # than one literal keyword query. We intentionally over-discover, then verify.
        query_plan = self._semantic_query_plan(criteria)
        candidate_target = min(90, max(requested * 5, 30))
        candidates: list[dict] = []
        seen_domains: set[str] = set()

        purpose = (
            f"Trouver des entreprises réelles correspondant à l'activité '{criteria.industry}' "
            f"dans {place or location}. Comprendre l'intention métier, pas seulement le mot exact. "
            "Privilégier le site officiel de l'entreprise. Exclure offres d'emploi, cabinets de recrutement "
            "sauf s'ils correspondent eux-mêmes à l'activité demandée, annuaires, comparateurs, articles, "
            "pages Top 10, réseaux sociaux et pages de catégories."
        )

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for query in query_plan:
                # Usually first two pages are enough; semantic diversity comes from query expansion.
                for page in range(2):
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
                        # One failed semantic query must not kill the whole campaign.
                        # TinyFish can occasionally reject/timeout a specific query; continue with the others.
                        continue
                    for item in (r.json().get("results") or []):
                        url=self._ensure_url(item.get("url") or "")
                        domain=self._domain(url)
                        title=(item.get("title") or "").strip()
                        if not url or not domain or domain in seen_domains or self._is_excluded_domain(domain):
                            continue
                        path=(urlparse(url).path or "").lower()
                        if any(h in path for h in self.NON_COMPANY_PAGE_HINTS):
                            continue
                        # Generic title on a deep path is almost certainly editorial/category noise.
                        if title and self._looks_generic_title(title, criteria) and path.strip("/"):
                            continue
                        seen_domains.add(domain)
                        candidates.append({**item, "url": url, "domain": domain, "discovery_query": query})
                        if len(candidates) >= candidate_target:
                            break
                    if len(candidates) >= candidate_target:
                        break
                if len(candidates) >= candidate_target:
                    break

            if not candidates:
                return []

            roots=[]; root_to_domain={}
            for c in candidates:
                root=self._root_url(c["url"])
                if root and root not in root_to_domain:
                    roots.append(root); root_to_domain[root]=c["domain"]

            fetched_by_domain: dict[str, dict] = {}
            for start in range(0, len(roots), 10):
                batch=roots[start:start+10]
                fr=await client.post(
                    self.FETCH_URL,
                    headers={**headers, "Content-Type":"application/json"},
                    json={
                        "urls": batch,
                        "format":"markdown",
                        "links":False,
                        "ttl":3600,
                        "per_url_timeout_ms":20000,
                        "purpose": (
                            "Lire la page d'accueil officielle. Identifier le nom légal/commercial de l'entreprise, "
                            "ses prestations, sa localisation et ses coordonnées professionnelles publiques."
                        ),
                    },
                )
                if fr.status_code == 200:
                    for fetched in (fr.json().get("results") or []):
                        raw_url=fetched.get("final_url") or fetched.get("url") or ""
                        dom=self._domain(raw_url)
                        if dom:
                            fetched_by_domain[dom]=fetched

        verified=[]
        for item in candidates:
            domain=item["domain"]
            fetched=fetched_by_domain.get(domain) or {}
            text=fetched.get("text") if isinstance(fetched.get("text"), str) else ""
            if not text:
                continue
            final_url=self._ensure_url(fetched.get("final_url") or self._root_url(item.get("url") or ""))
            website=self._root_url(final_url)
            if not website or self._is_excluded_domain(self._domain(website)):
                continue

            company_name, name_confidence=self._choose_company_name(fetched, item, domain, criteria)
            if not company_name or name_confidence < 62 or self._looks_generic_title(company_name, criteria):
                continue

            relevance, matched=self._activity_relevance(text + "\n" + (item.get("snippet") or ""), criteria)
            # 40 means at least one strong concept + business evidence, or solid token evidence.
            if relevance < 40:
                continue

            description=fetched.get("description") or item.get("snippet") or None
            email=self._extract_generic_email(text, domain)
            phone=self._extract_phone(text)
            business_domain=self._business_domain(text, criteria)
            founded_year, founded_year_source, founded_year_confidence=self._extract_founded_year(text)

            # Search-time filters. Unknown founding year is kept only when no year filter is requested.
            filters=getattr(criteria, "filters", {}) or {}
            fy_min=filters.get("founded_year_min")
            fy_max=filters.get("founded_year_max")
            wanted_domain=self._normalize(filters.get("business_domain") or "")
            try:
                fy_min=int(fy_min) if fy_min not in (None, "", "any") else None
            except Exception:
                fy_min=None
            try:
                fy_max=int(fy_max) if fy_max not in (None, "", "any") else None
            except Exception:
                fy_max=None
            if (fy_min is not None or fy_max is not None):
                if founded_year is None:
                    continue
                if fy_min is not None and founded_year < fy_min:
                    continue
                if fy_max is not None and founded_year > fy_max:
                    continue
            if wanted_domain and wanted_domain != "any" and wanted_domain != self._normalize(business_domain):
                continue

            verification=min(99, round(name_confidence*0.45 + relevance*0.55))
            verified.append({
                "company_name": company_name,
                "industry": criteria.industry,
                "business_domain": business_domain,
                "founded_year": founded_year,
                "founded_year_source": founded_year_source,
                "founded_year_confidence": founded_year_confidence or None,
                "description": description[:600] if isinstance(description, str) else None,
                "website": website,
                "email": email,
                "phone": phone,
                "address": None,
                "postal_code": criteria.postal_code,
                "city": criteria.city,
                "canton": criteria.canton,
                "country": criteria.country or "CH",
                "source": self.key,
                "source_provider": self.key,
                "source_url": website,
                "external_id": f"tinyfish:{domain}",
                "data_type": "real",
                "source_confidence": verification,
                "verification": {
                    "name_confidence": name_confidence,
                    "activity_relevance": relevance,
                    "matched_concepts": matched,
                    "discovery_query": item.get("discovery_query"),
                },
            })

        # Best verified companies first; de-dupe final brand names as well as domains.
        verified.sort(key=lambda x: x.get("source_confidence", 0), reverse=True)
        results=[]; seen_names=set()
        for row in verified:
            n=self._normalize(row["company_name"])
            if n in seen_names:
                continue
            seen_names.add(n)
            results.append(row)
            if len(results) >= requested:
                break
        return results


# ---------- Aura Intelligence V6: multi-source fusion ----------
class AuraIntelligenceProvider(ProspectSearchProvider):
    """Aura's recommended search mode.

    Uses Google Places as an identity/location anchor when GOOGLE_PLACES_API_KEY is
    configured, and TinyFish as first-party website discovery/enrichment when
    TINYFISH_API_KEY is configured. If only one source is configured, it works with
    that source rather than failing. No API key is ever exposed to the frontend.
    """
    key = "aura_intelligence"
    label = "Aura Intelligence (multi-source)"
    requires_credentials = True

    def __init__(self):
        self.google = GooglePlacesProvider()
        self.tinyfish = TinyFishProvider()

    def is_configured(self, org_integration=None) -> bool:
        return self.google.is_configured() or self.tinyfish.is_configured()

    @staticmethod
    def _norm_domain(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        try:
            host = urlparse(url).netloc.lower().split(":")[0]
            return host[4:] if host.startswith("www.") else host
        except Exception:
            return None

    @staticmethod
    def _norm_name(name: Optional[str]) -> str:
        return re.sub(r"[^a-z0-9]", "", (name or "").lower())

    def _match(self, a: dict, b: dict) -> bool:
        da, db = self._norm_domain(a.get("website")), self._norm_domain(b.get("website"))
        if da and db and da == db:
            return True
        na, nb = self._norm_name(a.get("company_name")), self._norm_name(b.get("company_name"))
        return bool(na and nb and (na == nb or (len(na) > 6 and (na in nb or nb in na))))

    def _finalize(self, row: dict, sources: list[str], evidence: list[dict]) -> dict:
        score = 0
        if "google_places" in sources:
            score += 48
        if "tinyfish" in sources:
            score += 37
        if row.get("website"):
            score += 5
        if row.get("email"):
            score += 4
        if row.get("phone"):
            score += 3
        if row.get("founded_year"):
            score += 3
        score = min(100, score)
        row["verification_score"] = score
        row["verification_level"] = "verified" if score >= 80 else "strong" if score >= 60 else "partial"
        row["evidence_sources"] = sources
        row["evidence"] = evidence
        row["source"] = self.key
        row["source_provider"] = self.key
        row["data_type"] = "real"
        return row

    async def search(self, criteria: SearchCriteria) -> List[dict]:
        google_rows, tiny_rows = [], []
        errors = []
        if self.google.is_configured():
            try:
                google_rows = await self.google.search(criteria)
            except Exception as exc:
                errors.append(f"Google Places: {exc}")
        if self.tinyfish.is_configured():
            try:
                tiny_rows = await self.tinyfish.search(criteria)
            except Exception as exc:
                errors.append(f"TinyFish: {exc}")

        if not google_rows and not tiny_rows:
            if errors:
                raise RuntimeError(" | ".join(errors))
            raise RuntimeError("Aura Intelligence nécessite TINYFISH_API_KEY ou GOOGLE_PLACES_API_KEY.")

        merged = []
        used_tiny = set()
        for g in google_rows:
            best_i = None
            for i, t in enumerate(tiny_rows):
                if i not in used_tiny and self._match(g, t):
                    best_i = i
                    break
            row = dict(g)
            sources = ["google_places"]
            evidence = [{"source":"google_places", "url":g.get("source_url"), "role":"identity_location"}]
            if best_i is not None:
                t = tiny_rows[best_i]
                used_tiny.add(best_i)
                sources.append("tinyfish")
                for key in ("website","email","description","business_domain","founded_year","founded_year_source","founded_year_confidence"):
                    if t.get(key):
                        row[key] = t[key]
                if not row.get("phone") and t.get("phone"):
                    row["phone"] = t["phone"]
                row["source_confidence"] = max(int(t.get("source_confidence") or 0), 80)
                evidence.append({"source":"tinyfish", "url":t.get("source_url") or t.get("website"), "role":"website_enrichment"})
            merged.append(self._finalize(row, sources, evidence))

        for i, t in enumerate(tiny_rows):
            if i in used_tiny:
                continue
            row = dict(t)
            merged.append(self._finalize(row, ["tinyfish"], [{"source":"tinyfish", "url":t.get("source_url") or t.get("website"), "role":"identity_enrichment"}]))

        merged.sort(key=lambda r: (r.get("verification_score",0), r.get("source_confidence",0), bool(r.get("email"))), reverse=True)
        return merged[: max(1, criteria.max_results)]


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
register(AuraIntelligenceProvider())
register(CustomAPIProvider())
register(CSVImportProvider())

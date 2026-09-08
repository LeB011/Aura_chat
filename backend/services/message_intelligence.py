"""Aura V8 verified outreach drafts.
Uses only data present in the prospect/opportunity record. No hallucinated audits.
"""
from __future__ import annotations


def generate_verified_draft(prospect: dict, channel: str, tone: str, length: str,
                            language: str, objective: str, offer: dict | None = None,
                            strategy: str = "professional") -> dict:
    offer=offer or {}
    name=prospect.get("company_name") or "votre entreprise"
    city=prospect.get("city")
    domain=prospect.get("business_domain") or prospect.get("industry") or "votre secteur"
    opp=prospect.get("opportunity") or {}
    observations=opp.get("verified_observations") or []
    why=opp.get("why_this_prospect") or []
    product=offer.get("product_name") or "Aura Hub / Prospect AI"
    benefit=offer.get("main_benefit") or "réduire le temps nécessaire pour identifier et qualifier de nouvelles opportunités commerciales"
    desc=offer.get("description") or "un outil de prospection B2B qui recherche, vérifie et prépare des prises de contact personnalisées"
    sender=offer.get("sender_name") or "Bryan"
    brand=offer.get("brand") or "Aura Hub"

    # Only verified observations can be stated as facts. Hypotheses are never inserted as facts.
    factual=[]
    for x in observations:
        if x and not x.lower().startswith("hypoth"):
            factual.append(x)
    context = f"{name} est actif dans le domaine {domain}" + (f" à {city}" if city else "")
    if factual:
        context += ". " + factual[0] + "."

    if channel == "email":
        subjects=[f"Une idée pour {name}", f"Question rapide — {name}", f"Prospection : exemple pour {name}"]
        if strategy == "direct_short":
            body=(f"Bonjour,\n\nJe me permets de vous contacter car {context} "
                  f"Je développe {product}, {desc}. L'objectif : {benefit}.\n\n"
                  "Puis-je vous envoyer un exemple concret adapté à votre activité ?\n\n"
                  f"Cordialement,\n{sender}\n{brand}")
        elif strategy == "consultative":
            body=(f"Bonjour,\n\nJe me permets de vous écrire car {context} "
                  f"Je travaille sur {product}, {desc}. Je ne présume pas de votre organisation interne : "
                  "l'idée est simplement de vérifier, sur un cas concret, si l'outil peut créer de la valeur pour votre équipe.\n\n"
                  "Puis-je vous préparer un exemple sans engagement ?\n\n"
                  f"Cordialement,\n{sender}\n{brand}")
        else:
            body=(f"Bonjour,\n\nJe me permets de vous contacter car {context} "
                  f"Je développe {product}, {desc}, afin de {benefit}. "
                  "Aura garde la validation humaine avant toute prise de contact.\n\n"
                  "Est-ce que je peux vous envoyer un exemple adapté à votre activité ?\n\n"
                  f"Cordialement,\n{sender}\n{brand}")
        return {"subject":subjects[0],"subject_options":subjects,"body":body,
                "cta":"Puis-je vous envoyer un exemple concret ?","generation_mode":"verified_v8"}
    body=(f"Bonjour, je vous contacte car {context} Je développe {product} pour {benefit}. "
          "Puis-je vous montrer un exemple concret ?")
    return {"subject":None,"subject_options":[],"body":body,"cta":"Montrer un exemple concret", "generation_mode":"verified_v8"}

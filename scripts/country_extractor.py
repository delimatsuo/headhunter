#!/usr/bin/env python3
"""
Country Extractor Utility

Extracts and normalizes country from LinkedIn address fields.
Used for country-level filtering in candidate search.
"""

import re
from typing import Optional, Tuple

# Mapping of country variations to canonical names
COUNTRY_ALIASES = {
    # Brazil
    "brazil": "Brazil",
    "brasil": "Brazil",
    "br": "Brazil",

    # United States
    "united states": "United States",
    "united states of america": "United States",
    "usa": "United States",
    "us": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "america": "United States",

    # Common countries
    "argentina": "Argentina",
    "mexico": "Mexico",
    "méxico": "Mexico",
    "canada": "Canada",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "england": "United Kingdom",
    "germany": "Germany",
    "deutschland": "Germany",
    "france": "France",
    "spain": "Spain",
    "españa": "Spain",
    "portugal": "Portugal",
    "italy": "Italy",
    "italia": "Italy",
    "netherlands": "Netherlands",
    "india": "India",
    "china": "China",
    "japan": "Japan",
    "australia": "Australia",
    "colombia": "Colombia",
    "chile": "Chile",
    "peru": "Peru",
    "perú": "Peru",
    "uruguay": "Uruguay",
    "paraguay": "Paraguay",
    "venezuela": "Venezuela",
    "ecuador": "Ecuador",
    "bolivia": "Bolivia",
}

# Brazilian states - if we see these, the country is Brazil
BRAZILIAN_STATES = {
    "são paulo", "sao paulo", "sp",
    "rio de janeiro", "rj",
    "minas gerais", "mg",
    "bahia", "ba",
    "paraná", "parana", "pr",
    "rio grande do sul", "rs",
    "santa catarina", "sc",
    "pernambuco", "pe",
    "ceará", "ceara", "ce",
    "goiás", "goias", "go",
    "pará", "para", "pa",
    "maranhão", "maranhao", "ma",
    "amazonas", "am",
    "espírito santo", "espirito santo", "es",
    "paraíba", "paraiba", "pb",
    "mato grosso", "mt",
    "mato grosso do sul", "ms",
    "rio grande do norte", "rn",
    "alagoas", "al",
    "piauí", "piaui", "pi",
    "distrito federal", "df", "brasília", "brasilia",
    "sergipe", "se",
    "rondônia", "rondonia", "ro",
    "tocantins", "to",
    "acre", "ac",
    "amapá", "amapa", "ap",
    "roraima", "rr",
}

# US states - if we see these, the country is United States
US_STATES = {
    "california", "ca",
    "new york", "ny",
    "texas", "tx",
    "florida", "fl",
    "illinois", "il",
    "pennsylvania", "pa",
    "ohio", "oh",
    "georgia", "ga",
    "north carolina", "nc",
    "michigan", "mi",
    "new jersey", "nj",
    "virginia", "va",
    "washington", "wa",
    "arizona", "az",
    "massachusetts", "ma",
    "tennessee", "tn",
    "indiana", "in",
    "missouri", "mo",
    "maryland", "md",
    "wisconsin", "wi",
    "colorado", "co",
    "minnesota", "mn",
    "south carolina", "sc",
    "alabama", "al",
    "louisiana", "la",
    "kentucky", "ky",
    "oregon", "or",
    "oklahoma", "ok",
    "connecticut", "ct",
    "utah", "ut",
    "iowa", "ia",
    "nevada", "nv",
    "arkansas", "ar",
    "mississippi", "ms",
    "kansas", "ks",
    "new mexico", "nm",
    "nebraska", "ne",
    "idaho", "id",
    "west virginia", "wv",
    "hawaii", "hi",
    "new hampshire", "nh",
    "maine", "me",
    "montana", "mt",
    "rhode island", "ri",
    "delaware", "de",
    "south dakota", "sd",
    "north dakota", "nd",
    "alaska", "ak",
    "vermont", "vt",
    "wyoming", "wy",
    "district of columbia", "dc", "washington dc", "washington d.c.",
}

# Major Brazilian cities
BRAZILIAN_CITIES = {
    "são paulo", "sao paulo",
    "rio de janeiro",
    "brasília", "brasilia",
    "salvador",
    "fortaleza",
    "belo horizonte",
    "manaus",
    "curitiba",
    "recife",
    "porto alegre",
    "belém", "belem",
    "goiânia", "goiania",
    "guarulhos",
    "campinas",
    "são luís", "sao luis",
    "são gonçalo", "sao goncalo",
    "maceió", "maceio",
    "duque de caxias",
    "natal",
    "teresina",
    "campo grande",
    "santos",
    "santo andré", "santo andre",
    "osasco",
    "joão pessoa", "joao pessoa",
    "ribeirão preto", "ribeirao preto",
    "uberlândia", "uberlandia",
    "sorocaba",
    "contagem",
    "aracaju",
    "feira de santana",
    "cuiabá", "cuiaba",
    "joinville",
    "londrina",
    "juiz de fora",
    "niterói", "niteroi",
    "florianópolis", "florianopolis",
}


def normalize_text(text: str) -> str:
    """Normalize text for comparison (lowercase, strip whitespace)."""
    return text.lower().strip()


def extract_country_from_address(address: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract country from a LinkedIn-style address string.

    Args:
        address: Address string like "São Paulo, State of São Paulo, Brazil"

    Returns:
        Tuple of (country, city) where country is the canonical country name
        and city is the extracted city (if found)
    """
    if not address or not address.strip():
        return None, None

    # Split by comma and clean parts
    parts = [p.strip() for p in address.split(",")]
    parts = [p for p in parts if p]  # Remove empty parts

    if not parts:
        return None, None

    # Try the last part first (usually country)
    last_part = normalize_text(parts[-1])

    # Check if last part is a known country
    if last_part in COUNTRY_ALIASES:
        country = COUNTRY_ALIASES[last_part]
        city = parts[0] if len(parts) > 1 else None
        return country, city

    # Check if any part contains "state of" (Brazilian pattern)
    for part in parts:
        normalized = normalize_text(part)
        if "state of" in normalized:
            # Extract state name after "state of"
            state_match = re.search(r"state of\s+(.+)", normalized)
            if state_match:
                state_name = state_match.group(1).strip()
                if state_name in BRAZILIAN_STATES:
                    city = parts[0] if parts else None
                    return "Brazil", city

    # Check if any part is a Brazilian state
    for part in parts:
        normalized = normalize_text(part)
        if normalized in BRAZILIAN_STATES:
            city = parts[0] if parts[0].lower().strip() != normalized else None
            return "Brazil", city

    # Check if any part is a Brazilian city
    for part in parts:
        normalized = normalize_text(part)
        if normalized in BRAZILIAN_CITIES:
            return "Brazil", part.strip()

    # Check if any part is a US state
    for part in parts:
        normalized = normalize_text(part)
        if normalized in US_STATES:
            city = parts[0] if parts[0].lower().strip() != normalized else None
            return "United States", city

    # If we still don't know, check for explicit country mentions in any part
    for part in parts:
        normalized = normalize_text(part)
        for alias, canonical in COUNTRY_ALIASES.items():
            if alias in normalized:
                city = parts[0] if len(parts) > 1 else None
                return canonical, city

    # Could not determine country
    return None, parts[0] if parts else None


def extract_country_from_job_description(job_description: str) -> Optional[str]:
    """
    Extract required country from a job description.

    Args:
        job_description: The job description text

    Returns:
        The canonical country name if found, None otherwise
    """
    if not job_description:
        return None

    text = normalize_text(job_description)

    # Check for explicit location requirements
    location_patterns = [
        r"based in\s+([^,.\n]+)",
        r"located in\s+([^,.\n]+)",
        r"position in\s+([^,.\n]+)",
        r"role in\s+([^,.\n]+)",
        r"office in\s+([^,.\n]+)",
        r"headquarters in\s+([^,.\n]+)",
        r"location:\s*([^,.\n]+)",
    ]

    for pattern in location_patterns:
        match = re.search(pattern, text)
        if match:
            location_text = match.group(1).strip()

            # Check if it's a country
            if location_text in COUNTRY_ALIASES:
                return COUNTRY_ALIASES[location_text]

            # Check if it's a Brazilian city/state
            if location_text in BRAZILIAN_CITIES or location_text in BRAZILIAN_STATES:
                return "Brazil"

            # Check if it's a US state
            if location_text in US_STATES:
                return "United States"

    # Check for country mentions anywhere in text
    # Prioritize Brazil since that's the main use case
    brazil_indicators = [
        "são paulo", "sao paulo", "rio de janeiro", "brasil", "brazil",
        "belo horizonte", "curitiba", "porto alegre", "brasília", "brasilia",
        "recife", "salvador", "fortaleza"
    ]

    for indicator in brazil_indicators:
        if indicator in text:
            return "Brazil"

    # Check for US indicators
    us_indicators = ["united states", "usa", "u.s.", "us only", "new york", "san francisco",
                     "los angeles", "seattle", "boston", "chicago", "austin", "remote us"]

    for indicator in us_indicators:
        if indicator in text:
            return "United States"

    return None


# Test function
if __name__ == "__main__":
    test_addresses = [
        "São Paulo, State of São Paulo, Brazil",
        "São Paulo, Brazil",
        "Santo André, São Paulo, Brazil",
        "Rio de Janeiro, RJ",
        "Belo Horizonte, State of Minas Gerais, Brazil",
        "San Francisco, CA",
        "New York, NY, United States",
        "Atlanta, Georgia, United States",
        "Buenos Aires, Argentina",
        "London, United Kingdom",
        "",
        None,
    ]

    print("Testing address extraction:")
    for addr in test_addresses:
        country, city = extract_country_from_address(addr)
        print(f"  '{addr}' -> country='{country}', city='{city}'")

    print("\nTesting job description extraction:")
    test_jds = [
        "We are looking for a Senior Engineer based in São Paulo",
        "This role is located in Brazil",
        "Position in San Francisco, CA",
        "Remote role, US only",
    ]

    for jd in test_jds:
        country = extract_country_from_job_description(jd)
        print(f"  '{jd[:50]}...' -> country='{country}'")

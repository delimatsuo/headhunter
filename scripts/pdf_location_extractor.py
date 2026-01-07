#!/usr/bin/env python3
"""
PDF Location Extractor for LinkedIn Profiles

Extracts location/country information from LinkedIn PDF exports.
LinkedIn PDFs have a specific structure:
- Page 1 has: Name, Title at Company, Location (right under title)
- Experience section has job locations like "City, State, Country"

This script extracts location from both sources and normalizes to country.
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple, List, Dict

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF not installed. Run: pip3 install pymupdf")
    sys.exit(1)

# Import our existing country extractor
sys.path.insert(0, str(Path(__file__).parent))
from country_extractor import extract_country_from_address, COUNTRY_ALIASES

# Brazilian states and their abbreviations
BRAZILIAN_STATES = {
    'ac': 'Acre', 'al': 'Alagoas', 'ap': 'Amapá', 'am': 'Amazonas',
    'ba': 'Bahia', 'ce': 'Ceará', 'df': 'Federal District', 'es': 'Espírito Santo',
    'go': 'Goiás', 'ma': 'Maranhão', 'mt': 'Mato Grosso', 'ms': 'Mato Grosso do Sul',
    'mg': 'Minas Gerais', 'pa': 'Pará', 'pb': 'Paraíba', 'pr': 'Paraná',
    'pe': 'Pernambuco', 'pi': 'Piauí', 'rj': 'Rio de Janeiro', 'rn': 'Rio Grande do Norte',
    'rs': 'Rio Grande do Sul', 'ro': 'Rondônia', 'rr': 'Roraima', 'sc': 'Santa Catarina',
    'sp': 'São Paulo', 'se': 'Sergipe', 'to': 'Tocantins',
    # Full names
    'acre': 'Acre', 'alagoas': 'Alagoas', 'amapá': 'Amapá', 'amazonas': 'Amazonas',
    'bahia': 'Bahia', 'ceará': 'Ceará', 'federal district': 'Federal District',
    'espírito santo': 'Espírito Santo', 'goiás': 'Goiás', 'maranhão': 'Maranhão',
    'mato grosso': 'Mato Grosso', 'mato grosso do sul': 'Mato Grosso do Sul',
    'minas gerais': 'Minas Gerais', 'pará': 'Pará', 'paraíba': 'Paraíba',
    'paraná': 'Paraná', 'pernambuco': 'Pernambuco', 'piauí': 'Piauí',
    'rio de janeiro': 'Rio de Janeiro', 'rio grande do norte': 'Rio Grande do Norte',
    'rio grande do sul': 'Rio Grande do Sul', 'rondônia': 'Rondônia',
    'roraima': 'Roraima', 'santa catarina': 'Santa Catarina', 'são paulo': 'São Paulo',
    'sergipe': 'Sergipe', 'tocantins': 'Tocantins',
    # Common variations
    'state of são paulo': 'São Paulo', 'state of rio de janeiro': 'Rio de Janeiro',
    'state of minas gerais': 'Minas Gerais', 'state of paraná': 'Paraná',
}

# Brazilian cities (major ones)
BRAZILIAN_CITIES = {
    'são paulo', 'sao paulo', 'rio de janeiro', 'brasília', 'brasilia',
    'belo horizonte', 'curitiba', 'porto alegre', 'salvador', 'recife',
    'fortaleza', 'manaus', 'campinas', 'goiânia', 'goiania', 'belém', 'belem',
    'guarulhos', 'campinas', 'são bernardo do campo', 'santo andré',
    'osasco', 'ribeirão preto', 'sorocaba', 'uberlândia', 'contagem',
    'joinville', 'florianópolis', 'florianopolis', 'vitória', 'vitoria',
    'niterói', 'niteroi', 'londrina', 'maringá', 'maringa', 'blumenau',
}

# US states
US_STATES = {
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota', 'mississippi',
    'missouri', 'montana', 'nebraska', 'nevada', 'new hampshire', 'new jersey',
    'new mexico', 'new york', 'north carolina', 'north dakota', 'ohio',
    'oklahoma', 'oregon', 'pennsylvania', 'rhode island', 'south carolina',
    'south dakota', 'tennessee', 'texas', 'utah', 'vermont', 'virginia',
    'washington', 'west virginia', 'wisconsin', 'wyoming',
    # Common metros
    'greater boston', 'greater new york', 'san francisco bay area',
    'greater los angeles', 'greater chicago', 'greater seattle',
    'greater miami', 'greater atlanta', 'greater dallas', 'greater houston',
}


def extract_text_from_pdf(pdf_path: str, max_pages: int = 2) -> str:
    """Extract text from first N pages of a PDF."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page_num in range(min(max_pages, len(doc))):
            page = doc[page_num]
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return ""


def extract_profile_header_location(text: str) -> Optional[str]:
    """
    Extract the location from LinkedIn profile header.

    LinkedIn PDF format typically has:
    - Contact info section (left column)
    - Name (large text)
    - Title at Company
    - Location (single word or "City, State" - right under title)
    - Summary section

    The location is usually a single line before "Summary" section.
    """
    lines = text.split('\n')

    # Look for location patterns in first ~30 lines (header area)
    for i, line in enumerate(lines[:40]):
        line = line.strip()
        if not line:
            continue

        # Skip common non-location lines
        skip_patterns = [
            'contact', 'linkedin.com', 'top skills', 'languages',
            'certifications', 'summary', 'experience', 'education',
            'www.', 'http', '@', 'email', 'phone', 'english', 'portuguese',
            'spanish', 'french', 'german', 'page ', 'professional',
        ]
        line_lower = line.lower()
        if any(p in line_lower for p in skip_patterns):
            continue

        # Look for location patterns
        # Pattern 1: "City, State, Country" or "City, Country"
        if ', brazil' in line_lower or ', brasil' in line_lower:
            return line
        if ', united states' in line_lower or ', usa' in line_lower:
            return line
        if ', portugal' in line_lower:
            return line
        if ', uk' in line_lower or ', united kingdom' in line_lower:
            return line

        # Pattern 2: Just a Brazilian state or city (common in LinkedIn)
        if line_lower in BRAZILIAN_CITIES or line_lower in BRAZILIAN_STATES:
            return line

        # Pattern 3: "City Area, Country" pattern
        if ' area' in line_lower and ('brazil' in line_lower or 'brasil' in line_lower):
            return line

    return None


def extract_job_locations(text: str) -> List[str]:
    """
    Extract location strings from job experience entries.

    Job locations in LinkedIn PDFs appear like:
    - "Curitiba, Paraná, Brazil"
    - "São Paulo Area, Brazil"
    - "Greater Boston"
    - "Campos, Rio de Janeiro, Brazil"
    """
    locations = []

    # Look for location patterns in the text
    # Pattern: City, State/Province, Country (with Brazil)
    brazil_pattern = r'([A-Za-zÀ-ÿ\s]+(?:Area)?),?\s*(?:([A-Za-zÀ-ÿ\s]+),?\s*)?(Brazil|Brasil)'
    matches = re.finditer(brazil_pattern, text, re.IGNORECASE)
    for match in matches:
        locations.append(match.group(0))

    # Pattern: City, State (for US locations)
    us_pattern = r'([A-Za-z\s]+),\s*(United States|USA|US)\b'
    matches = re.finditer(us_pattern, text, re.IGNORECASE)
    for match in matches:
        locations.append(match.group(0))

    # Pattern: Greater [City] or [City] Area
    area_pattern = r'(Greater\s+[A-Za-z\s]+|[A-Za-z\s]+\s+Area)'
    matches = re.finditer(area_pattern, text)
    for match in matches:
        loc = match.group(0).strip()
        if len(loc) > 5:  # Filter out noise
            locations.append(loc)

    return locations


def infer_country_from_location(location: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Infer country from a location string.
    Returns (country, city).
    """
    if not location:
        return None, None

    location_lower = location.lower().strip()

    # Direct country mentions
    if 'brazil' in location_lower or 'brasil' in location_lower:
        # Extract city
        parts = [p.strip() for p in location.split(',')]
        city = parts[0] if parts else None
        return 'Brazil', city

    if 'united states' in location_lower or location_lower.endswith(', usa') or location_lower.endswith(', us'):
        parts = [p.strip() for p in location.split(',')]
        city = parts[0] if parts else None
        return 'United States', city

    if 'portugal' in location_lower:
        parts = [p.strip() for p in location.split(',')]
        city = parts[0] if parts else None
        return 'Portugal', city

    if 'united kingdom' in location_lower or ', uk' in location_lower:
        parts = [p.strip() for p in location.split(',')]
        city = parts[0] if parts else None
        return 'United Kingdom', city

    if 'canada' in location_lower:
        parts = [p.strip() for p in location.split(',')]
        city = parts[0] if parts else None
        return 'Canada', city

    if 'germany' in location_lower or 'deutschland' in location_lower:
        parts = [p.strip() for p in location.split(',')]
        city = parts[0] if parts else None
        return 'Germany', city

    # Check for Brazilian state/city (implies Brazil)
    for token in location_lower.replace(',', ' ').split():
        token = token.strip()
        if token in BRAZILIAN_STATES:
            parts = [p.strip() for p in location.split(',')]
            city = parts[0] if parts else None
            return 'Brazil', city
        if token in BRAZILIAN_CITIES:
            return 'Brazil', token.title()

    # Check for US state (implies USA)
    for state in US_STATES:
        if state in location_lower:
            parts = [p.strip() for p in location.split(',')]
            city = parts[0] if parts else None
            return 'United States', city

    # Use the existing country extractor as fallback
    return extract_country_from_address(location)


def extract_location_from_linkedin_pdf(pdf_path: str) -> Dict[str, Optional[str]]:
    """
    Extract location information from a LinkedIn PDF.

    Returns dict with:
    - country: Normalized country name
    - city: City if detected
    - raw_location: Original location string found
    - source: Where the location was found ('header' or 'experience')
    """
    result = {
        'country': None,
        'city': None,
        'raw_location': None,
        'source': None,
    }

    text = extract_text_from_pdf(pdf_path)
    if not text:
        return result

    # Try header location first (most reliable for current location)
    header_location = extract_profile_header_location(text)
    if header_location:
        country, city = infer_country_from_location(header_location)
        if country:
            result['country'] = country
            result['city'] = city
            result['raw_location'] = header_location
            result['source'] = 'header'
            return result

    # Fall back to job experience locations
    job_locations = extract_job_locations(text)
    if job_locations:
        # Prefer the most recent job location (first one in list)
        for loc in job_locations:
            country, city = infer_country_from_location(loc)
            if country:
                result['country'] = country
                result['city'] = city
                result['raw_location'] = loc
                result['source'] = 'experience'
                return result

    return result


def build_candidate_pdf_mapping(resumes_dir: str) -> Dict[str, str]:
    """
    Build a mapping of candidate_id -> PDF file path.

    Folder structure: resumes/{job_id}/{candidate_id}/download/{filename}.pdf
    """
    mapping = {}
    resumes_path = Path(resumes_dir)

    if not resumes_path.exists():
        print(f"Error: Resumes directory not found: {resumes_dir}")
        return mapping

    # Find all PDF files
    for pdf_file in resumes_path.glob('**/download/*.pdf'):
        # Extract candidate_id from path
        # Path: .../resumes/{job_id}/{candidate_id}/download/{filename}.pdf
        try:
            candidate_id = pdf_file.parent.parent.name
            if candidate_id.isdigit():
                # If multiple PDFs exist for same candidate, prefer non-"Profile" named ones
                existing = mapping.get(candidate_id)
                if existing and 'Profile' in str(pdf_file):
                    continue
                mapping[candidate_id] = str(pdf_file)
        except Exception as e:
            print(f"Error parsing path {pdf_file}: {e}")
            continue

    return mapping


if __name__ == "__main__":
    # Test with a sample PDF
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        print(f"Extracting location from: {pdf_path}")
        result = extract_location_from_linkedin_pdf(pdf_path)
        print(f"Result: {result}")
    else:
        # Run a quick test
        test_dir = "/Volumes/Extreme Pro/myprojects/headhunter/CSV files/505039_Ella_Executive_Search_files_1/resumes"

        print("Building candidate -> PDF mapping...")
        mapping = build_candidate_pdf_mapping(test_dir)
        print(f"Found {len(mapping)} candidates with PDFs")

        # Test extraction on first 5
        print("\nSample extractions:")
        for candidate_id, pdf_path in list(mapping.items())[:5]:
            result = extract_location_from_linkedin_pdf(pdf_path)
            print(f"  {candidate_id}: {result['country']} ({result['source']})")

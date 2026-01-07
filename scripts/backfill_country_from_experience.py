#!/usr/bin/env python3
"""
Backfill Country from Experience Data

For candidates without PDFs, infer country from:
1. Brazilian company names in experience
2. Brazilian city names in experience/headline
3. Brazilian universities

This is a secondary pass after PDF extraction.

Usage:
    python3 backfill_country_from_experience.py [--dry-run] [--limit N]
"""

import argparse
import logging
import re
from collections import Counter
from typing import Optional, Tuple

import firebase_admin
from firebase_admin import credentials, firestore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Brazilian companies (well-known, unambiguous)
BRAZIL_COMPANIES = {
    # Banks & Fintech
    'nubank', 'itaú', 'itau', 'bradesco', 'banco do brasil', 'bb ', 'caixa econômica',
    'santander brasil', 'btg pactual', 'xp inc', 'safra', 'votorantim',
    'stone pagamentos', 'pagseguro', 'cielo', 'picpay', 'c6 bank', 'banco inter',
    'creditas', 'neon', 'agibank', 'banco original', 'banco pan',
    # Tech & E-commerce
    'ifood', 'magazine luiza', 'magalu', 'mercado livre brasil', 'b2w',
    'americanas s.a', 'via varejo', 'casas bahia', 'ponto frio',
    'vtex', 'locaweb', 'totvs', 'linx', 'movile', 'sympla',
    'hotmart', 'rd station', 'resultados digitais', 'conta azul', 'omie',
    'loft', 'quinto andar', 'quintoandar', 'zap imóveis', 'viva real',
    'loggi', 'rapiddo', 'cornershop brasil',
    # Industry & Energy
    'petrobras', 'vale s.a', 'ambev', 'embraer', 'weg', 'gerdau',
    'usiminas', 'csn', 'suzano', 'klabin', 'jbs', 'brf', 'marfrig',
    'cosan', 'raízen', 'ultrapar', 'braskem',
    # Retail & Consumer
    'natura', 'boticário', 'renner', 'riachuelo', 'hering', 'arezzo',
    'centauro', 'netshoes', 'dafiti',
    # Media
    'globo', 'rede globo', 'grupo globo', 'folha de s.paulo', 'estadão', 'uol',
    # Consulting/Tech Services (Brazil offices)
    'ci&t', 'dextra', 'daitan', 'db1', 'objective', 'south system',
    # HR Tech
    'catho', 'gupy', 'kenoby', 'revelo',
    # Universities
    'usp', 'unicamp', 'unesp', 'ufmg', 'ufrj', 'ufpr', 'ufrgs', 'ufsc',
    'puc-rio', 'puc-sp', 'puc-rs', 'fgv', 'insper', 'ibmec',
    'mackenzie', 'faap', 'espm', 'senac', 'senai', 'fatec',
}

# Brazilian cities (unambiguous)
BRAZIL_CITIES = {
    'são paulo', 'sao paulo', 'rio de janeiro', 'belo horizonte',
    'curitiba', 'porto alegre', 'brasília', 'brasilia', 'salvador',
    'fortaleza', 'recife', 'campinas', 'florianópolis', 'florianopolis',
    'vitória', 'vitoria', 'goiânia', 'goiania', 'manaus', 'belém', 'belem',
    'guarulhos', 'são bernardo', 'santo andré', 'osasco',
    'ribeirão preto', 'sorocaba', 'uberlândia', 'contagem',
    'joinville', 'londrina', 'maringá', 'maringa', 'blumenau',
    'niterói', 'niteroi', 'santos', 'são josé dos campos',
    'juiz de fora', 'feira de santana', 'natal', 'joão pessoa',
    'teresina', 'campo grande', 'cuiabá', 'cuiaba', 'aracaju',
    'maceió', 'maceio', 'são luís', 'sao luis', 'porto velho',
}

# Brazilian state references
BRAZIL_STATES = {
    'paraná', 'parana', 'santa catarina', 'rio grande do sul',
    'minas gerais', 'espírito santo', 'espirito santo',
    'bahia', 'pernambuco', 'ceará', 'ceara', 'amazonas', 'pará', 'para',
    'goiás', 'goias', 'mato grosso', 'mato grosso do sul',
    'distrito federal', 'maranhão', 'maranhao', 'piauí', 'piaui',
    'rio grande do norte', 'paraíba', 'paraiba', 'sergipe', 'alagoas',
    'tocantins', 'rondônia', 'rondonia', 'acre', 'amapá', 'amapa', 'roraima',
}

# US companies (to exclude false positives)
US_COMPANIES = {
    'google', 'meta', 'facebook', 'amazon', 'apple', 'microsoft',
    'netflix', 'uber', 'airbnb', 'stripe', 'slack', 'dropbox',
    'salesforce', 'oracle', 'ibm', 'cisco', 'intel', 'nvidia',
    'linkedin', 'twitter', 'snap', 'pinterest', 'reddit',
    'goldman sachs', 'morgan stanley', 'jpmorgan', 'citibank',
    'mckinsey', 'bain', 'bcg', 'deloitte', 'pwc', 'ey', 'kpmg',
}


def detect_country_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Detect country from experience/headline text.
    Returns (country, matched_term).
    """
    if not text:
        return None, None

    text_lower = text.lower()

    # Check for US indicators first (to avoid false positives)
    for company in US_COMPANIES:
        if company in text_lower:
            # If they also have Brazil indicators, prefer Brazil
            # (many people work for US companies remotely from Brazil)
            pass

    # Check Brazilian companies
    for company in BRAZIL_COMPANIES:
        # Use word boundary matching to avoid partial matches
        pattern = r'\b' + re.escape(company) + r'\b'
        if re.search(pattern, text_lower):
            return 'Brazil', company

    # Check Brazilian cities
    for city in BRAZIL_CITIES:
        pattern = r'\b' + re.escape(city) + r'\b'
        if re.search(pattern, text_lower):
            return 'Brazil', city

    # Check Brazilian states
    for state in BRAZIL_STATES:
        pattern = r'\b' + re.escape(state) + r'\b'
        if re.search(pattern, text_lower):
            return 'Brazil', state

    # Check explicit Brazil mentions
    if re.search(r'\bbrasil\b|\bbrazil\b', text_lower):
        return 'Brazil', 'brazil/brasil'

    return None, None


def init_firebase():
    """Initialize Firebase Admin SDK."""
    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app()
            logger.info("Initialized Firebase with default credentials")
        except Exception:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {'projectId': 'headhunter-ai-0088'})
            logger.info("Initialized Firebase with application default credentials")


def backfill_from_experience(dry_run: bool = False, limit: Optional[int] = None):
    """
    Backfill country from experience data.
    """
    db = firestore.client()
    candidates_ref = db.collection('candidates')

    updated = 0
    skipped = 0
    already_has = 0
    country_stats = Counter()
    match_stats = Counter()

    batch = db.batch()
    batch_count = 0
    BATCH_SIZE = 500

    docs = list(candidates_ref.stream())
    total = len(docs)

    if limit:
        docs = docs[:limit]

    logger.info(f"Processing {len(docs)} candidates...")

    for i, doc in enumerate(docs):
        data = doc.to_dict()

        # Skip if already has country
        if data.get('country'):
            already_has += 1
            country_stats[data['country']] += 1
            continue

        # Get text to analyze
        orig = data.get('original_data', {}) or {}
        experience = orig.get('experience', '') or ''
        headline = orig.get('headline', '') or ''
        text = experience + ' ' + headline

        country, match = detect_country_from_text(text)

        if country:
            if dry_run:
                logger.debug(f"[DRY RUN] {doc.id}: {country} (matched: {match})")
            else:
                batch.update(candidates_ref.document(doc.id), {
                    'country': country,
                    'country_source': 'experience_inference',
                    'country_match': match,
                })
                batch_count += 1

                if batch_count >= BATCH_SIZE:
                    batch.commit()
                    logger.info(f"Committed batch of {batch_count} updates")
                    batch = db.batch()
                    batch_count = 0

            updated += 1
            country_stats[country] += 1
            match_stats[match] += 1
        else:
            skipped += 1

        if (i + 1) % 5000 == 0:
            logger.info(f"Processed {i + 1}/{len(docs)}...")

    # Commit remaining
    if batch_count > 0 and not dry_run:
        batch.commit()
        logger.info(f"Committed final batch of {batch_count} updates")

    logger.info(f"\n=== Summary ===")
    logger.info(f"Total candidates: {total}")
    logger.info(f"Already had country: {already_has}")
    logger.info(f"Updated from experience: {updated}")
    logger.info(f"No match found: {skipped}")

    logger.info(f"\nCountry distribution:")
    for country, count in country_stats.most_common():
        logger.info(f"  {country}: {count}")

    logger.info(f"\nTop match terms:")
    for match, count in match_stats.most_common(20):
        logger.info(f"  {match}: {count}")

    return updated, skipped


def main():
    parser = argparse.ArgumentParser(description='Backfill country from experience data')
    parser.add_argument('--dry-run', action='store_true', help='Preview without updating')
    parser.add_argument('--limit', type=int, help='Limit candidates to process')
    args = parser.parse_args()

    logger.info("=== Country Backfill from Experience ===")
    if args.dry_run:
        logger.info("Running in DRY RUN mode")

    init_firebase()
    backfill_from_experience(dry_run=args.dry_run, limit=args.limit)


if __name__ == '__main__':
    main()

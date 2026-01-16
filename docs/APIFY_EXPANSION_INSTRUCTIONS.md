# Apify LinkedIn Profile Expansion - Instructions for AI Agent

## Objective
Download additional Brazilian software engineer profiles from LinkedIn using Apify, avoiding duplicates with our existing 2,374+ candidates.

## Current State
- **Existing candidates**: ~2,374 in `sourcing.candidates` table
- **Source**: Apify LinkedIn scraping (São Paulo focus)
- **Database**: Cloud SQL PostgreSQL with `sourcing` schema

## Strategy to Avoid Duplicates

### Option 1: Geographic Expansion (Recommended)
Target different Brazilian cities/regions we haven't fully covered:

```python
EXPANSION_LOCATIONS = [
    # Tier 1 - Major tech hubs not fully scraped
    "Rio de Janeiro, Brazil",
    "Belo Horizonte, Brazil",
    "Curitiba, Brazil",
    "Porto Alegre, Brazil",
    "Brasília, Brazil",

    # Tier 2 - Growing tech scenes
    "Florianópolis, Brazil",  # "Silicon Island"
    "Campinas, Brazil",       # Unicamp tech hub
    "Recife, Brazil",         # Porto Digital
    "Salvador, Brazil",
    "Fortaleza, Brazil",

    # Tier 3 - Remote work hubs
    "Ribeirão Preto, Brazil",
    "Joinville, Brazil",
    "Goiânia, Brazil",
]
```

### Option 2: Role/Title Variations
Use different search queries to find engineers with varied titles:

```python
SEARCH_QUERIES = [
    # Portuguese titles
    "Desenvolvedor Backend OR Desenvolvedor Frontend",
    "Engenheiro de Software OR Arquiteto de Software",
    "Desenvolvedor Full Stack OR Programador",
    "Analista de Sistemas OR Desenvolvedor Mobile",

    # Seniority variations
    "Tech Lead OR Engineering Manager Brazil",
    "Staff Engineer OR Principal Engineer Brazil",
    "CTO OR VP Engineering Brazil",

    # Technology-specific
    "Python Developer Brazil",
    "Java Developer Brazil",
    "React Developer OR Angular Developer Brazil",
    "DevOps Engineer OR SRE Brazil",
    "Data Engineer OR ML Engineer Brazil",
]
```

### Option 3: Company-Based Search
Target engineers from specific companies:

```python
COMPANY_KEYWORDS = [
    "Nubank engineer",
    "iFood developer",
    "PicPay engineer",
    "Mercado Libre developer",
    "Stone Pagamentos engineer",
    "Itaú developer",
    "XP Inc engineer",
]
```

## Implementation Code

### Step 1: Check Existing URLs Before Scraping

```python
def get_existing_linkedin_urls() -> set:
    """Get all LinkedIn URLs we already have to prevent duplicates"""
    import psycopg2
    from urllib.parse import quote_plus
    import subprocess

    # Get DB password from Secret Manager
    result = subprocess.run(
        ['gcloud', 'secrets', 'versions', 'access', 'latest',
         '--secret=db-primary-password', '--project=headhunter-ai-0088'],
        capture_output=True, text=True
    )
    password = result.stdout.strip()

    db_url = f"postgresql://hh_app:{quote_plus(password)}@136.113.28.239:5432/headhunter"
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    cur.execute("SELECT linkedin_url FROM sourcing.candidates")
    existing = {row[0] for row in cur.fetchall()}

    conn.close()
    return existing
```

### Step 2: Run Discovery with New Locations

```python
from apify_client import ApifyClient
import os

def discover_new_profiles(location: str, max_items: int = 1000) -> list:
    """Discover profiles from a new location"""
    client = ApifyClient(os.getenv('APIFY_TOKEN'))

    run_input = {
        "profileScraperMode": "Short",  # Just URLs, cheaper
        "searchQuery": "Software Engineer OR Desenvolvedor",
        "locations": [location],
        "maxItems": max_items,
    }

    run = client.actor("harvestapi/linkedin-profile-search").call(run_input=run_input)
    return client.dataset(run["defaultDatasetId"]).list_items().items
```

### Step 3: Filter Out Duplicates Before Extraction

```python
def filter_new_profiles(discovered: list, existing_urls: set) -> list:
    """Remove profiles we already have"""
    new_profiles = []

    for profile in discovered:
        url = profile.get('linkedinUrl') or profile.get('profileUrl')
        if url and url not in existing_urls:
            # Normalize URL to handle variations
            normalized = url.rstrip('/').lower()
            if normalized not in {u.rstrip('/').lower() for u in existing_urls}:
                new_profiles.append(profile)

    return new_profiles
```

### Step 4: Full Pipeline Script

```python
#!/usr/bin/env python3
"""
Expand Ella Sourcing database with new LinkedIn profiles
Avoids duplicates by checking existing URLs before extraction
"""

import os
import json
from datetime import datetime
from pathlib import Path

# Configuration
EXPANSION_LOCATIONS = [
    "Rio de Janeiro, Brazil",
    "Belo Horizonte, Brazil",
    "Curitiba, Brazil",
    "Porto Alegre, Brazil",
    "Florianópolis, Brazil",
]

MAX_PER_LOCATION = 500  # Profiles per location
TOTAL_BUDGET = 50.0     # USD budget cap

def main():
    from apify_client import ApifyClient

    # Get existing URLs
    print("Loading existing LinkedIn URLs...")
    existing_urls = get_existing_linkedin_urls()
    print(f"Found {len(existing_urls)} existing profiles to skip")

    client = ApifyClient(os.getenv('APIFY_TOKEN'))
    all_new_profiles = []
    total_cost = 0.0

    for location in EXPANSION_LOCATIONS:
        print(f"\n🔍 Searching: {location}")

        # Discovery (cheap)
        discovered = discover_new_profiles(location, MAX_PER_LOCATION)
        print(f"   Discovered: {len(discovered)}")

        # Filter duplicates
        new_profiles = filter_new_profiles(discovered, existing_urls)
        print(f"   New (not in DB): {len(new_profiles)}")

        if not new_profiles:
            print("   Skipping - no new profiles")
            continue

        # Extract full profiles (more expensive)
        urls = [p.get('linkedinUrl') or p.get('profileUrl') for p in new_profiles]

        # supreme_coder extraction: ~$3/1k profiles
        extraction_cost = (len(urls) / 1000) * 3.0
        if total_cost + extraction_cost > TOTAL_BUDGET:
            print(f"   Budget limit reached. Stopping.")
            break

        print(f"   Extracting {len(urls)} profiles (est. ${extraction_cost:.2f})")

        run_input = {"urls": [{"url": u} for u in urls]}
        run = client.actor("supreme_coder/linkedin-profile-scraper").call(run_input=run_input)
        extracted = client.dataset(run["defaultDatasetId"]).list_items().items

        all_new_profiles.extend(extracted)
        total_cost += extraction_cost

        # Add to existing set to avoid duplicates in subsequent locations
        existing_urls.update(urls)

        print(f"   ✅ Extracted: {len(extracted)}")

    # Save results
    output_file = Path(f"data/sourcing/expansion_{datetime.now():%Y%m%d_%H%M%S}.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(all_new_profiles, f, indent=2, default=str)

    print(f"\n✅ COMPLETE")
    print(f"   New profiles: {len(all_new_profiles)}")
    print(f"   Estimated cost: ${total_cost:.2f}")
    print(f"   Saved to: {output_file}")

    return all_new_profiles

if __name__ == "__main__":
    main()
```

## Running the Expansion

### Prerequisites
```bash
# Ensure environment variables are set
export APIFY_TOKEN="your_apify_token"

# Or in .env file
echo "APIFY_TOKEN=your_token" >> .env
```

### Execution
```bash
cd /Volumes/Extreme\ Pro/myprojects/headhunter

# Test with one location first
python3 -c "
from scripts.apify_linkedin_pipeline import ApifyLinkedInPipeline
pipeline = ApifyLinkedInPipeline()
results = pipeline.discover_profiles(
    search_query='Software Engineer',
    locations=['Rio de Janeiro, Brazil'],
    max_items=100,
    scraper_mode='Short'
)
print(f'Found {len(results)} profiles')
"
```

### After Downloading New Profiles

1. **Store in database**:
```python
pipeline.store_profiles(new_profiles)
```

2. **Run enrichment**:
```bash
python3 scripts/sourcing_gemini_enrichment.py --max-cost 20
```

3. **Generate embeddings**:
```bash
python3 scripts/sourcing_embeddings.py
```

## Cost Estimates

| Operation | Cost | Notes |
|-----------|------|-------|
| Discovery | ~$0.10/page + $0.004/profile | ~25 results per page |
| Extraction | ~$3.00/1,000 profiles | supreme_coder actor |
| Enrichment | ~$0.01/profile | Gemini 2.5 Flash |

**Example: 5,000 new profiles**
- Discovery: ~$20-30
- Extraction: ~$15
- Enrichment: ~$50
- **Total: ~$85-95**

## Deduplication Strategy

The key to avoiding duplicates is the `linkedin_url` field:

1. **Before scraping**: Load all existing URLs into memory
2. **After discovery**: Filter out URLs that match existing ones
3. **URL normalization**: Handle variations like:
   - `https://linkedin.com/in/john-doe` vs `https://www.linkedin.com/in/john-doe/`
   - Case sensitivity: URLs should be compared lowercase
4. **Database constraint**: The `linkedin_url` column has `UNIQUE` constraint, so duplicates will fail on insert (upsert handles this)

## Notes

- LinkedIn has ~2M+ software engineers in Brazil
- São Paulo alone has ~500K+ tech professionals
- Each location search can yield 1,000-10,000 unique profiles
- Budget $100-200 for a meaningful expansion (5,000-10,000 new profiles)

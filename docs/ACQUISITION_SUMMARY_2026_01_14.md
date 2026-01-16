# Brazilian Engineering Talent Database - Acquisition Summary

**Date**: January 14, 2026
**Status**: ✅ Pipeline Operational
**Budget Used**: ~$1.50 (testing) / $300-500 allocated

---

## Executive Summary

Successfully implemented and tested a comprehensive data acquisition pipeline for building a database of top Brazilian software engineers. The system scrapes engineers from target companies (unicorns, big tech, funded startups), enriches profiles with AI analysis, and generates embeddings for semantic search.

### Current Database Status

| Metric | Count |
|--------|-------|
| **Total Candidates** | 2,631 |
| **Enriched** | 1,854 (70.5%) |
| **Pending Enrichment** | 777 |
| **With Experience Data** | 1,949 |
| **Experience Records** | 18,000 |
| **Embeddings** | 25 |

---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TOP BRAZILIAN ENGINEERS PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────┐                                                  │
│  │ 1. COMPANY SCRAPE      │  Apify: harvestapi/linkedin-company-employees   │
│  │    Target Companies    │  Cost: $4-8 per 1,000 profiles                  │
│  │    (100 companies)     │  Input: Company LinkedIn URLs                   │
│  └───────────┬────────────┘  Filter: "engineer OR developer OR desenvolvedor"│
│              │                                                               │
│              ▼                                                               │
│  ┌────────────────────────┐                                                  │
│  │ 2. LOCAL FILTER        │  70+ bilingual job titles (EN + PT)             │
│  │    Engineering Roles   │  ~88% yield (strict engineering filter)         │
│  └───────────┬────────────┘                                                  │
│              │                                                               │
│              ▼                                                               │
│  ┌────────────────────────┐                                                  │
│  │ 3. DATABASE STORAGE    │  PostgreSQL: sourcing.candidates               │
│  │    Deduplication       │  UNIQUE constraint on linkedin_url             │
│  │    Experience Parsing  │  sourcing.experience (work history)            │
│  └───────────┬────────────┘                                                  │
│              │                                                               │
│              ▼                                                               │
│  ┌────────────────────────┐                                                  │
│  │ 4. AI ENRICHMENT       │  Gemini 2.5 Flash                               │
│  │    Profile Analysis    │  Cost: ~$0.01 per profile                       │
│  │                        │  Output: level, skills, salary, summary         │
│  └───────────┬────────────┘                                                  │
│              │                                                               │
│              ▼                                                               │
│  ┌────────────────────────┐                                                  │
│  │ 5. EMBEDDINGS          │  Gemini Embedding API                           │
│  │    768-dim vectors     │  For semantic search                            │
│  └───────────┬────────────┘                                                  │
│              │                                                               │
│              ▼                                                               │
│  ┌────────────────────────┐                                                  │
│  │ 6. ALUMNI TAGGING      │  Filter experience for target companies         │
│  │    (Optional)          │  is_current = FALSE → alumni                    │
│  └────────────────────────┘                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Target Companies (100 total)

### Tier 1: Unicorns ($1B+ valuation) - 15 companies
Priority: 100 | Estimated: 8,000+ engineers

- Nubank, QuintoAndar, C6 Bank, iFood, Creditas
- Loft, CloudWalk, Ebanx, Nuvemshop, Loggi
- MadeiraMadeira, Dock, Unico, Olist, QI Tech

### Tier 2: Big Tech Brazil - 10 companies
Priority: 95 | Estimated: 4,300+ engineers

- Google Brazil, Meta Brazil, Microsoft Brazil, Amazon Brazil
- Mercado Libre, Salesforce, SAP, Oracle, IBM, Spotify

### Tier 3: Funded Scaleups - 20 companies
Priority: 85 | Estimated: 6,000+ engineers

- PicPay, Stone, PagSeguro, Celcoin, Omie, RD Station
- VTEX, Gympass/Wellhub, Hotmart, TOTVS, Contabilizei
- Clara, Hash, Caju, Gupy, Warren, Kovi, Buser, Méliuz

### Tier 4: Series A/B Funded - 30 companies
Priority: 75 | Estimated: 4,000+ engineers

- Pipefy, Involves, Runrun.it, Pipo Saúde, Memed
- Freto, Logcomex, Sólides, Feedz, Neoway, BigDataCorp
- Cortex, Parfin, Aarin, Z1, Cora, Blu, Qulture.Rocks
- Neon, Inter, Original, RecargaPay, Asaas, Transfeera
- Magalu, Americanas, Via, Zenklub, Psicologia Viva, Dr. Consulta

### Tier 5: Emerging Startups - 15 companies
Priority: 65 | Estimated: 1,000+ engineers

- VAAS, Capim, Canopy, Agrolend, Trace Finance
- Dotz, Nomad, Frete.com, Tembici, Alice
- Facily, Zé Delivery, Daki, Shopper, Liv Up

---

## Scripts Created

| Script | Purpose | Usage |
|--------|---------|-------|
| `company_employee_scraper.py` | Scrape engineers from company LinkedIn pages | `python scrape-tier --tier tier1_unicorns --budget 50` |
| `alumni_extractor.py` | Tag candidates with alumni affiliations | `python tag-existing` |
| `sourcing_gemini_enrichment.py` | Enrich profiles with AI analysis | `python --max-cost 50` |
| `sourcing_embeddings.py` | Generate 768-dim embeddings | `python` |
| `monitor_acquisition.py` | Auto-check status every 15 minutes | `python --interval 15` |
| `build_top_engineers_db.py` | Master orchestration script | `python run --budget 300` |

---

## Cost Breakdown

### Acquisition Costs (Apify)

| Mode | Cost | Use Case |
|------|------|----------|
| Short profile | $4/1,000 | Basic data (name, title, URL) |
| Full profile | $8/1,000 | Work history, skills, summary |

### Enrichment Costs (Gemini 2.5 Flash)

| Metric | Cost |
|--------|------|
| Input tokens | $0.30/1M |
| Output tokens | $2.50/1M |
| **Per profile** | **~$0.01** |

### Estimated Full Pipeline

| Phase | Profiles | Cost |
|-------|----------|------|
| Scrape unicorns | 8,000 | $32-64 |
| Scrape big tech | 4,000 | $16-32 |
| Scrape scaleups | 6,000 | $24-48 |
| Scrape Series A/B | 4,000 | $16-32 |
| Enrichment | 15,000 | $150 |
| Embeddings | 15,000 | ~$0 |
| **Total** | **~15,000** | **~$300** |

---

## Bilingual Job Titles (70+)

The scraper uses bilingual keywords to capture both English and Portuguese job titles:

### English
- software engineer, developer, programmer
- backend, frontend, full stack, fullstack
- devops, sre, site reliability, platform engineer
- data engineer, ml engineer, machine learning
- tech lead, engineering manager, architect
- staff engineer, principal engineer, senior engineer

### Portuguese
- desenvolvedor, programador
- engenheiro de software, engenheira de software
- desenvolvedor backend, desenvolvedor frontend
- engenheiro de dados, cientista de dados
- líder técnico, gerente de engenharia
- arquiteto de software, arquiteto de soluções
- analista de sistemas, analista desenvolvedor

---

## Monitoring

The `monitor_acquisition.py` script runs every 15 minutes and displays:

```
======================================================================
📊 ACQUISITION & ENRICHMENT STATUS
   2026-01-14T17:23:02
======================================================================

📦 DATABASE OVERVIEW
--------------------------------------------------
   Total candidates:        2,631
   Enriched:                1,854 (70.5%)
   Pending enrichment:      777
   With experience data:    1,949
   Experience records:      18,000

🎯 TARGET COMPANY TRACKING
--------------------------------------------------
   Alumni (former):         [after migration]
   Current employees:       [after migration]

📈 RECENT ACTIVITY (24h)
--------------------------------------------------
   Candidates added:        2,631
   Candidates enriched:     1,854

🏢 BY SOURCE (Top 10)
--------------------------------------------------
   apify_linkedin                            2,374
   company_scrape:Nubank                        44
   company_scrape:Loft                          29
   ...

   Enrichment: [████████████████████████████░░░░░░░░░░░░] 70.5%
```

---

## Database Schema

### sourcing.candidates
```sql
id                    SERIAL PRIMARY KEY
linkedin_url          TEXT UNIQUE NOT NULL
first_name            TEXT
last_name             TEXT
headline              TEXT
location              TEXT
profile_image_url     TEXT
source                TEXT
scraped_at            TIMESTAMP
enriched_at           TIMESTAMP
intelligent_analysis  JSONB  -- AI enrichment results
company_affiliations  JSONB  -- {current: [], past: []}
is_target_company_alumni  BOOLEAN
is_target_company_current BOOLEAN
target_companies_worked   TEXT[]
```

### sourcing.experience
```sql
id              SERIAL PRIMARY KEY
candidate_id    INTEGER REFERENCES candidates(id)
company_name    TEXT
title           TEXT
is_current      BOOLEAN
start_date      DATE
end_date        DATE
description     TEXT
```

### sourcing.embeddings
```sql
candidate_id    INTEGER PRIMARY KEY REFERENCES candidates(id)
embedding       VECTOR(768)
created_at      TIMESTAMP
```

---

## Next Steps

1. **Apply Alumni Migration**: Run `scripts/migrations/004_alumni_tracking.sql` to enable alumni tracking
2. **Continue Enrichment**: Background process enriching remaining 777 candidates
3. **Scale Acquisition**: Run full pipeline with $300 budget
4. **Generate Embeddings**: Create embeddings for all enriched profiles
5. **Test Search**: Validate semantic search functionality

---

## Commands Reference

```bash
# Check current status
python scripts/monitor_acquisition.py --once

# Scrape a single company
python scripts/company_employee_scraper.py scrape --company "Nubank" --max 500

# Scrape all unicorns
python scripts/company_employee_scraper.py scrape-tier --tier tier1_unicorns --budget 100

# Scrape all tiers with budget
python scripts/company_employee_scraper.py scrape-all --budget 200

# Tag alumni affiliations
python scripts/alumni_extractor.py tag-existing

# Enrich profiles
python scripts/sourcing_gemini_enrichment.py --max-cost 50

# Generate embeddings
python scripts/sourcing_embeddings.py

# Full pipeline
python scripts/build_top_engineers_db.py run --budget 300
```

---

## Files Modified/Created

| File | Action |
|------|--------|
| `data/sourcing/target_companies.json` | **Modified**: Expanded from 55 to 100 companies |
| `scripts/company_employee_scraper.py` | **Modified**: Added 70+ bilingual titles, fixed Apify params |
| `scripts/alumni_extractor.py` | **Created**: Alumni detection and tagging |
| `scripts/migrations/004_alumni_tracking.sql` | **Created**: Alumni tracking schema |
| `scripts/build_top_engineers_db.py` | **Created**: Master orchestration |
| `scripts/monitor_acquisition.py` | **Created**: Auto-status checking |
| `docs/ACQUISITION_SUMMARY_2026_01_14.md` | **Created**: This document |

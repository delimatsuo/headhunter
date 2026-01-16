# Session Summary: January 16, 2026

## Status Check - Sourcing Pipeline

### Database Status (Current)

| Metric | Count | Notes |
|--------|-------|-------|
| **Total Candidates** | 15,117 | Target pool of Brazilian engineers |
| **Enriched** | 4,598 (30.4%) | AI-analyzed profiles |
| **Pending Enrichment** | 10,519 | Awaiting AI analysis |
| **With Experience Data** | 1,949 | Have work history |
| **Experience Records** | 18,000 | Total job entries |
| **With Embeddings** | 25 | Need embedding generation |
| **Added Last 48h** | 12,743 | Recent scraping results |

### Enrichment Progress

```
Enrichment: [████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 30.4%
```

The enrichment pipeline ran after the previous session crash, progressing from ~291 to 4,598 candidates before stopping.

### Top Source Companies (by profile count)

| Rank | Company | Profiles |
|------|---------|----------|
| 1 | Nubank | 450 |
| 2 | PagSeguro | 433 |
| 3 | Spotify Brazil | 413 |
| 4 | QuintoAndar | 407 |
| 5 | Stone Pagamentos | 402 |
| 6 | C6 Bank | 401 |
| 7 | iFood | 401 |
| 8 | PicPay | 391 |
| 9 | Meta Brazil | 355 |
| 10 | Inter | 336 |

---

## Previous Session (Jan 15, 2026) - Acquisition Expansion

### Scraping Completed

| Tier | Companies | New Profiles | Cost |
|------|-----------|--------------|------|
| Tier5 (Emerging Startups) | 28 | 962 | $11.69 |
| Tier6 (Software Consultancies) | 15 | 937 | ~$7 |
| Tier7 (Missing Unicorns) | 10 | 532 | ~$3 |
| **TOTAL** | **53** | **2,431** | **~$22** |

### Companies Added to Target List

**Tier5 (13 new)**: Conta Simples, Vammo, NG.Cash, Huna, Genial Care, Mombak, Iugu, Vindi, Revelo, Sympla, PlayKids, Cielo, Linx

**Tier6 - Software Consultancies (15 new)**: CI&T, BairesDev, Luby Software, Cheesecake Labs, DB1 Global Software, BRQ Digital Solutions, Zallpy Digital, Avenue Code, Objective, Stefanini, Dextra Digital, Ateliware, Supero Technology, Encora (Daitan), Matera

**Tier7 - Missing Unicorns (10 new)**: Wildlife Studios, Movile, CargoX, Agibank, 2TM (Mercado Bitcoin), Mercado Bitcoin, Bitso, Hashdex, Locaweb, Rede

---

## Next Steps

1. **Resume Enrichment**: Run `python scripts/sourcing_gemini_enrichment.py --max-cost 100` to continue enriching the 10,519 pending profiles

2. **Generate Embeddings**: After enrichment, run `python scripts/sourcing_embeddings.py` to create semantic search vectors

3. **Validate Data Quality**: Check enrichment error rate and data completeness

4. **Integrate with Main Search**: Consider merging sourcing candidates with main candidate pool

---

## Files Modified

| File | Action |
|------|--------|
| `data/sourcing/target_companies.json` | Updated with 38 new companies (135 total) |
| `data/sourcing/tier_tier5_*.json` | New scraping results |
| `data/sourcing/tier_tier6_*.json` | New scraping results |
| `data/sourcing/tier_tier7_*.json` | New scraping results |
| `scripts/company_employee_scraper.py` | Added tier6/tier7 support |
| `docs/ACQUISITION_SUMMARY_2026_01_14.md` | Pipeline documentation |

---

## Quick Commands

```bash
# Check current status
python scripts/monitor_acquisition.py --once

# Resume enrichment (with cost limit)
python scripts/sourcing_gemini_enrichment.py --max-cost 100

# Generate embeddings for enriched candidates
python scripts/sourcing_embeddings.py

# Scrape additional companies
python scripts/company_employee_scraper.py scrape-tier --tier tier1_unicorns --budget 50
```

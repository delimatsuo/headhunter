# EMBEDDING MODEL BAKE-OFF REPORT
Generated: 2025-09-10T22:08:53.121894
============================================================

## EXECUTIVE SUMMARY
• Providers Tested: vertex_ai, deterministic
• Total Tests: 22
• **Recommended Provider**: vertex_ai

## PERFORMANCE COMPARISON
```
Provider        Avg Time     Throughput   Success Rate
------------------------------------------------------------
vertex_ai       0.000s       4766.7/sec   100.0%
deterministic   0.000s       5843.1/sec   100.0%
```

## COST COMPARISON
```
Provider        Per Embedding   29K Candidates
--------------------------------------------------
vertex_ai       $0.000002       $0.06
deterministic   $0.000000       $0.00
```

## QUALITY COMPARISON (Search Relevance)
```
Provider        Quality Score Avg Error    Correlation
-------------------------------------------------------
vertex_ai       0.145         0.524        0.305
deterministic   0.145         0.524        0.305
```

## RECOMMENDATIONS
🏆 **Best Overall**: vertex_ai
⚡ **Best Performance**: deterministic
💰 **Best Cost**: deterministic
🎯 **Best Quality**: vertex_ai

### Reasoning:
• Quality: vertex_ai provides best search relevance (score: 0.145)
• Performance: deterministic offers highest throughput (5843.1 embeddings/sec)
• Cost: deterministic is most cost-effective ($0.000000 per embedding)
• Production: vertex_ai recommended for balanced performance, cost, and quality

## DETAILED ANALYSIS

### VERTEX_AI
**Performance**: 0.000s avg, 100.0% success
**Cost**: $0.000002 per embedding, $0.06 for 29K candidates
**Quality**: 0.145 score, 0.524 avg error

### DETERMINISTIC
**Performance**: 0.000s avg, 100.0% success
**Cost**: $0.000000 per embedding, $0.00 for 29K candidates
**Quality**: 0.145 score, 0.524 avg error

## IMPLEMENTATION NOTES
• All providers tested with same dataset for fair comparison
• Quality measured by similarity correlation with expected job-candidate matches
• Cost estimates based on current provider pricing
• Performance measured on single-threaded execution
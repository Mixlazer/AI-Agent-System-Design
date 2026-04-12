# Load Testing for LLM Balancer

## Overview

30-minute sustained load test with OpenTelemetry metrics collection.

## Test Configuration

| Parameter | Value |
|-----------|-------|
| Duration | 30 minutes |
| Rate | ~10 requests/minute |
| Total | ~300 requests |
| Interval | 6 seconds |
| Models | `minimax/minimax-m2.5:free`, `gemma4:31b-cloud`, `google/gemma-4-E2B-it` |
| **Response Capture** | ✅ Saves model responses |
| **Complexity Detection** | `rnj-1:8b-cloud` or fallback to prompt length |

### Complexity Detection

```
rnj-1:8b-cloud available → LLM classifies: LOW/MEDIUM/HIGH
rnj-1:8b-cloud offline   → Length-based:
  • <30 chars   = LOW
  • 30-80 chars = MEDIUM  
  • >80 chars   = HIGH
```

## Quick Start

```bash
cd ~/bonus-track-hw/load-testing
pip install -r requirements.txt

# 1. Quick test (5 min)
python quick_test.py

# 2. Full test (30 min)
python load_test.py
```

## Monitoring

**Prometheus:** http://localhost:9090
**Grafana:** http://localhost:3000 (admin/admin)

## Output

- `results_YYYYMMDD_HHMMSS.json` — raw data
- `summary_YYYYMMDD_HHMMSS.json` — statistics

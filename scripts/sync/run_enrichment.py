#!/usr/bin/env python3
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.enrich_orcids_batch import main as enrich_main

# Mock arguments by modifying sys.argv
sys.argv = [
    "enrich_orcids_batch.py",
    "--csv", "data/orcid_extraction_report_20260105_012133.csv",
    "--auto-create"
]

if __name__ == "__main__":
    print("🚀 Launching enrichment directly via python...")
    enrich_main()

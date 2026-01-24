#!/usr/bin/env python3
"""Script to append Scholar endpoints to publications.py"""

import sys

# Read scholar endpoints
with open('api/routes/scholar_endpoints.py', 'r') as f:
    scholar_content = f.read()

# Append to publications.py
with open('api/routes/publications.py', 'a') as f:
    f.write(scholar_content)

print("✅ Scholar endpoints appended to publications.py")

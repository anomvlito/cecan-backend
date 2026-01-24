#!/usr/bin/env python3
"""
Script rápido para analizar la distribución de miembros académicos.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import get_session
from core.models import AcademicMember, ResearcherDetails
from sqlalchemy import func

session = get_session()

print("=" * 60)
print("ANÁLISIS DE MIEMBROS ACADÉMICOS ACTIVOS")
print("=" * 60)

# 1. Por member_type
print("\n1. DISTRIBUCIÓN POR TIPO:")
print("-" * 40)
results = session.query(
    AcademicMember.member_type,
    func.count(AcademicMember.id)
).filter(
    AcademicMember.is_active == True
).group_by(
    AcademicMember.member_type
).all()

for member_type, count in results:
    print(f"  {member_type:15s} : {count:3d}")

# 2. Por category (Solo Researchers)
print("\n2. DISTRIBUCIÓN POR CATEGORÍA (Researchers):")
print("-" * 40)
results = session.query(
    ResearcherDetails.category,
    func.count(ResearcherDetails.id)
).join(
    AcademicMember, AcademicMember.id == ResearcherDetails.member_id
).filter(
    AcademicMember.is_active == True
).group_by(
    ResearcherDetails.category
).all()

for category, count in results:
    cat_name = category if category else "(Sin Categoría)"
    print(f"  {cat_name:15s} : {count:3d}")

# 3. Total
total = session.query(AcademicMember).filter(AcademicMember.is_active == True).count()
print("\n" + "=" * 60)
print(f"TOTAL ACTIVOS: {total}")
print("=" * 60)

session.close()

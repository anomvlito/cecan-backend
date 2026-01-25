import sys
import os
import random
from datetime import date, timedelta

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database.session import SessionLocal
from core.models import (
    ScientificProject, ProjectActivity, WorkPackageType, 
    ProjectStatusType, ActivityStatusType, PaymentStatusType
)

# Filenames from "Cartas Gantt FINALES e informadas"
FILES = [
    "FINAL OUTREACH Carta Gantt 2025 CRM Rev-CCV.xlsx",
    "HUMAN CAPITAL TRAINING Carta Gantt 2025. BN_EC-CCV.xlsx",
    "INT  NAT Carta Gantt 2025 lista BN-CCV.xlsx",
    "WP-1 Carta Gantt 2025 lista BN- CCV.xlsx",
    "WP-2 Carta Gantt 2025 lista BN-CCV.xlsx",
    "WP-3 Carta Gantt 2025 lista BN-CCV EC.xlsx",
    "WP-4 Carta Gantt 2025 lista BN-CCV.xlsx",
    "WP-5 Carta Gantt 2025 lista BN-CCV.xlsx"
]

def get_wp_type(filename: str) -> WorkPackageType:
    upper = filename.upper()
    if "WP-1" in upper: return WorkPackageType.WP1
    if "WP-2" in upper: return WorkPackageType.WP2
    if "WP-3" in upper: return WorkPackageType.WP3
    if "WP-4" in upper: return WorkPackageType.WP4
    if "WP-5" in upper: return WorkPackageType.WP5
    if "OUTREACH" in upper: return WorkPackageType.OUTREACH
    if "TRAINING" in upper: return WorkPackageType.TRAINING
    return WorkPackageType.GOVERNANCE # Default for INT NAT or others

def get_clean_title(filename: str) -> str:
    # Remove extension and common clutter
    name = filename.replace(".xlsx", "").replace("Carta Gantt 2025", "").replace("lista BN-CCV", "").replace("lista BN- CCV", "")
    return name.strip()

def seed_dummies():
    db: Session = SessionLocal()
    try:
        print("Starting dummy seed...")
        
        # Colors map
        wp_colors = {
            "WP1": "#3b82f6", "WP2": "#10b981", "WP3": "#f59e0b",
            "WP4": "#8b5cf6", "WP5": "#6366f1", "OUTREACH": "#ec4899",
            "TRAINING": "#06b6d4", "GOVERNANCE": "#8b5cf6"
        }

        for i, filename in enumerate(FILES):
            wp = get_wp_type(filename)
            title = f"{wp.value}: {get_clean_title(filename)}"
            code = f"DP-{i+1:02d}" # Dummy Project
            
            # Check exist
            exists = db.query(ScientificProject).filter(ScientificProject.title == title).first()
            if exists:
                print(f"Skipping {title}, already exists.")
                continue

            print(f"Creating {title}...")
            
            budget = random.randint(10, 500) * 1000000

            project = ScientificProject(
                title=title,
                code=code,
                description=f"Proyecto importado automáticamente desde {filename}. Datos simulados.",
                work_package=wp,
                grant_type="Research Project",
                pi_name="Investigador Simulado",
                years_covered=[3, 4, 5], # Years 2023, 2024, 2025
                budget_allocated=budget,
                budget_executed=budget * 0.3,
                status=ProjectStatusType.ACTIVE,
                color=wp_colors.get(wp.value, "#9ca3af"),
                created_by=1 # Assume admin
            )
            
            # Save to get ID
            db.add(project)
            db.flush()
            project.calculate_dates_from_years()

            # Create random activities
            for j in range(random.randint(4, 8)):
                start_month = random.randint(1, 10)
                duration = random.randint(2, 5)
                # Random year between 2024 (Year 4), 2025 (Year 5), and 2026
                year = random.choice([2024, 2025, 2026])
                
                s_date = date(year, start_month, 1)
                e_date = (s_date + timedelta(days=duration*30)).replace(day=1) # Rough approximation

                act = ProjectActivity(
                    project_id=project.id,
                    number=j+1,
                    description=f"Actividad Simulada {j+1}",
                    start_month=s_date,
                    end_month=e_date,
                    status=random.choice(list(ActivityStatusType)),
                    progress=random.randint(0, 100) if random.random() > 0.3 else 0,
                    budget_allocated=random.randint(1, 10) * 1000000,
                    sort_order=j
                )
                db.add(act)

            db.commit()
            print(f"Created {title} with activities.")

    except Exception as e:
        print(f"Error seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_dummies()


import sys
import os
from datetime import date, datetime

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database.session import get_session
from core.models import (
    ScientificProject, 
    ProjectActivity, 
    WorkPackageType, 
    ProjectStatusType, 
    ActivityStatusType,
    User,
    AcademicMember,
    ResponsibilityAssignment,
    ResourceType,
    RaciRole,
    UserRole
)

def seed_wp5_demo():
    print("🚀 Starting WP-5 Demo Simulation Seed...")
    
    session: Session = next(get_session())
    
    try:
        # 1. Get Key Users
        # We need Staff (Admin), Researcher, and Student users
        staff_user = session.query(User).filter(User.email == "staff@cecan.cl").first()
        researcher_user = session.query(User).filter(User.email == "researcher@cecan.cl").first()
        student_user = session.query(User).filter(User.email == "student@cecan.cl").first()
        
        # Verify users exist, if not likely need to run basic seed first, but we attempt to proceed
        if not staff_user or not researcher_user or not student_user:
            print("⚠️ Key demo users missing. Please run seed_users_demo.py first.")
            return

        print(f"✅ Found users: Staff={staff_user.email}, Researcher={researcher_user.email}, Student={student_user.email}")
        
        # Get their AcademicMember IDs (critical for RACI)
        staff_member = staff_user.academic_member
        researcher_member = researcher_user.academic_member
        student_member = student_user.academic_member
        
        if not staff_member or not researcher_member or not student_member:
             print("⚠️ Linked Academic Members missing. Check user setups.")
             return

        # 2. Clear Existing WP-5 Data (Cleanup for idempotency)
        # Find existing WP-5 projects
        existing_projects = session.query(ScientificProject).filter(
            ScientificProject.work_package == WorkPackageType.WP5
        ).all()
        
        if existing_projects:
            print(f"🧹 Cleaning up {len(existing_projects)} existing WP-5 projects...")
            for p in existing_projects:
                # Cascade deletes activities automatically via ORM usually, but explicit is safe
                session.delete(p)
            session.commit()
            print("   Cleanup done.")

        # 3. Create Projects from Excel
        print("🏗️ Creating Scientific Projects...")
        
        # --- Project 1 ---
        p1 = ScientificProject(
            title="Standardize clinical repository for the management of cancer records",
            code="WP5-P1",
            description="Project 1: Standardize clinical repository for the management of cancer records (Year 1,2,3,4,5)",
            work_package=WorkPackageType.WP5,
            grant_type="CECAN Core",
            pi_id=researcher_member.id, # Assign Researcher as PI effectively
            pi_name=researcher_member.full_name,
            years_covered=[1, 2, 3, 4, 5],
            status=ProjectStatusType.ACTIVE,
            progress=0.40,
            budget_allocated=120000000.0,
            start_date=date(2024, 1, 1),
            end_date=date(2028, 12, 31)
        )
        session.add(p1)
        session.flush() # Flush to get ID
        
        # --- Project 2 ---
        p2 = ScientificProject(
            title="Collaborative research repository",
            code="WP5-P2",
            description="Project 2: Collaborative research repository (Year 1,2,3,4,5)",
            work_package=WorkPackageType.WP5,
            grant_type="CECAN Core",
            pi_id=researcher_member.id,
            pi_name=researcher_member.full_name,
            years_covered=[1, 2, 3, 4, 5],
            status=ProjectStatusType.ACTIVE,
            progress=0.40,
            budget_allocated=80000000.0,
            start_date=date(2024, 1, 1),
            end_date=date(2028, 12, 31)
        )
        session.add(p2)
        session.flush()

        # --- Project 3 ---
        p3 = ScientificProject(
            title="Analytical models for the design of public policies",
            code="WP5-P3",
            description="Project 3: Analytical models for the design of public policies (Year 1,2,3,4,5)",
            work_package=WorkPackageType.WP5,
            grant_type="CECAN Core",
            pi_id=researcher_member.id,
            pi_name=researcher_member.full_name,
            years_covered=[1, 2, 3, 4, 5],
            status=ProjectStatusType.ACTIVE,
            progress=0.40,
            budget_allocated=95000000.0,
            start_date=date(2024, 1, 1),
            end_date=date(2028, 12, 31)
        )
        session.add(p3)
        session.flush()
        
        # 4. Create Project Activities & Assign Responsibilities
        print("📝 Creating Activities and Assigning RACI Roles...")

        def create_activity(project, number, desc, start, end, status, progress, assigned_to_role_R, assigned_to_role_A=staff_member):
            # Create Activity
            act = ProjectActivity(
                project_id=project.id,
                description=desc,
                number=number,
                start_month=start,
                end_month=end,
                status=status,
                progress=progress,
                budget_allocated=2000000.0 # Dummy budget per activity
            )
            session.add(act)
            session.flush()
            
            # 1. Assign RESPONSIBLE (R) - The person doing the work (Student or Researcher)
            assign_r = ResponsibilityAssignment(
                resource_type=ResourceType.PROJECT_ACTIVITY,
                resource_id=act.id,
                raci_role=RaciRole.R,
                member_id=assigned_to_role_R.id,
                # Also link to User ID if available for easier dashboard queries
                user_id=session.query(User).filter(User.academic_member == assigned_to_role_R).first().id
            )
            session.add(assign_r)
            
            # 2. Assign ACCOUNTABLE (A) - The Staff member supervising
            assign_a = ResponsibilityAssignment(
                resource_type=ResourceType.PROJECT_ACTIVITY,
                resource_id=act.id,
                raci_role=RaciRole.A,
                member_id=assigned_to_role_A.id,
                user_id=session.query(User).filter(User.academic_member == assigned_to_role_A).first().id
            )
            session.add(assign_a)
            
            return act

        # --- ACTIVITIES FOR PROJECT 1 ---
        # (1) Gathering information - Student task (Done)
        create_activity(p1, 1, "(1) Gathering information from existing registries in the country (Year 1,2)", 
                       date(2024, 10, 1), date(2025, 10, 1), ActivityStatusType.DONE, 1.0, student_member)
        
        # (2) Define software architecture - Researcher task (Done)
        create_activity(p1, 2, "(2) Define software architecture, Definition minimum data sets; System Model defined", 
                       date(2024, 10, 1), date(2025, 9, 1), ActivityStatusType.DONE, 1.0, researcher_member)

        # (3.1) Study to identify current status - Student task (In Progress)
        create_activity(p1, 3, "3.1. Study to identify the current status of cancer registries in Latin America. Paper under review.", 
                       date(2025, 3, 1), date(2025, 11, 1), ActivityStatusType.IN_PROGRESS, 0.90, student_member)
        
        # (3.6) Publications - Researcher task (In Progress)
        create_activity(p1, 4, "3.6. Publications management and consolidation", 
                       date(2024, 11, 1), date(2025, 12, 1), ActivityStatusType.IN_PROGRESS, 0.55, researcher_member)


        # --- ACTIVITIES FOR PROJECT 2 ---
        # (1) To identify main factors... - Researcher task (In Progress)
        create_activity(p2, 1, "(1) To identify the main factors that can cause the occurrence of cancer, model survival and recurrence", 
                       date(2025, 1, 1), date(2026, 1, 1), ActivityStatusType.IN_PROGRESS, 0.40, researcher_member)

        # (4) Early detection (Postponed) - Student task (Blocked)
        create_activity(p2, 4, "(4) Early detection of cancer-based evidence, to support decision-making (Posposed)", 
                       date(2025, 6, 1), date(2026, 6, 1), ActivityStatusType.BLOCKED, 0.25, student_member)


        # --- ACTIVITIES FOR PROJECT 3 ---
        # (1) Development of analytical models - Researcher (Done)
        create_activity(p3, 1, "(1) Development of analytical models that capture the main factors to determine cost-effective screening policy", 
                       date(2024, 11, 1), date(2025, 4, 1), ActivityStatusType.DONE, 1.0, researcher_member)

        # (4.2) Posters - Student (Done)
        create_activity(p3, 2, "4.2. Presentation of posters at Chilean Conference on Computer Science: 'Predicting Cervix Uteri Cancer'", 
                       date(2025, 10, 1), date(2025, 11, 1), ActivityStatusType.DONE, 1.0, student_member)

        # (4.3) App for early oral cancer detection - Student (In Progress/Active)
        create_activity(p3, 3, "4.3. Development of an application for early oral cancer detection with Deep Learning Image-based Chatbot (Ormeño 2025)", 
                       date(2025, 11, 1), date(2026, 3, 1), ActivityStatusType.IN_PROGRESS, 0.80, student_member)


        session.commit()
        print("✅ WP-5 Simulation Data Loaded Successfully!")
        print("\nSUMMARY:")
        print(f"  - Staff ({staff_member.full_name}): Accountable for all activities.")
        print(f"  - Researcher ({researcher_member.full_name}): Responsible for architecture, models, core analysis.")
        print(f"  - Student ({student_member.full_name}): Responsible for data gathering, systematic reviews, app dev.")
        print("\n👉 Now login as 'student@cecan.cl', 'researcher@cecan.cl', or 'staff@cecan.cl' to see the changes.")

    except Exception as e:
        session.rollback()
        print(f"❌ Error seeding WP-5 data: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    seed_wp5_demo()

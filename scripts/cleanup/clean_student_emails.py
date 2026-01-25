#!/usr/bin/env python3
"""
Clean Malformed Student Emails
Fixes emails with multiple addresses, spaces, or invalid characters
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from core.models import AcademicMember

def clean_email(raw_email: str) -> str:
    """Extract first valid email from malformed string"""
    if not raw_email:
        return None
    
    # Remove spaces
    cleaned = raw_email.strip()
    
    # If contains "/" or multiple @, split and take first valid
    if '/' in cleaned or cleaned.count('@') > 1:
        # Split by common separators
        parts = re.split(r'[/\s,;]+', cleaned)
        for part in parts:
            part = part.strip()
            # Basic email validation
            if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', part):
                return part
        return None
    
    # Return as-is if seems valid
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', cleaned):
        return cleaned
    
    return None


def clean_student_emails():
    """Clean malformed emails in AcademicMember table"""
    db = SessionLocal()
    
    print("=" * 60)
    print("🧹 Cleaning Malformed Student Emails")
    print("=" * 60)
    
    try:
        # Get all members with emails
        members = db.query(AcademicMember).filter(
            AcademicMember.email.isnot(None)
        ).all()
        
        cleaned = 0
        errors = 0
        
        for member in members:
            original = member.email
            
            # Check if needs cleaning
            if '/' in original or original.count('@') > 1 or '  ' in original:
                print(f"\n🔍 Cleaning: {member.full_name}")
                print(f"   Original: {original}")
                
                cleaned_email = clean_email(original)
                
                if cleaned_email:
                    member.email = cleaned_email
                    db.commit()
                    print(f"   ✅ Cleaned: {cleaned_email}")
                    cleaned += 1
                else:
                    member.email = None
                    db.commit()
                    print(f"   ⚠️  Set to NULL (no valid email found)")
                    errors += 1
        
        print("\n" + "=" * 60)
        print(f"📊 Summary:")
        print(f"   ✅ Cleaned: {cleaned}")
        print(f"   ⚠️  Set to NULL: {errors}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    clean_student_emails()
    print("\n✅ Email cleaning completed!")

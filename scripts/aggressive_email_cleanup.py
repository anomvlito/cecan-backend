#!/usr/bin/env python3
"""
Aggressive Email Cleanup
Fixes all malformed emails (multiple addresses, slashes, etc.)
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def extract_first_valid_email(email_str):
    """Extract first valid email from malformed string"""
    if not email_str:
        return None
    
    # Split by common separators
    parts = re.split(r'[/\s,;]+', email_str)
    
    for part in parts:
        part = part.strip()
        # Basic email validation regex
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', part):
            return part
    
    return None

def clean_all_malformed_emails():
    """Clean all malformed emails in academic_members"""
    db = SessionLocal()
    
    try:
        print("🧹 Cleaning ALL malformed emails...")
        
        # Get all members with emails
        result = db.execute(text("SELECT id, full_name, email FROM academic_members WHERE email IS NOT NULL;"))
        members = result.fetchall()
        
        cleaned = 0
        nulled = 0
        
        for member_id, name, email in members:
            # Check if email is malformed (contains /, multiple @, spaces, etc.)
            if '/' in email or email.count('@') > 1 or '  ' in email or ' @' in email or '@ ' in email:
                print(f"\n🔧 {name}")
                print(f"   Original: {email}")
                
                cleaned_email = extract_first_valid_email(email)
                
                if cleaned_email:
                    db.execute(text("UPDATE academic_members SET email = :email WHERE id = :id"), 
                              {"email": cleaned_email, "id": member_id})
                    print(f"   ✅ Cleaned: {cleaned_email}")
                    cleaned += 1
                else:
                    db.execute(text("UPDATE academic_members SET email = NULL WHERE id = :id"), 
                              {"id": member_id})
                    print(f"   ⚠️  Set to NULL (no valid email found)")
                    nulled += 1
        
        db.commit()
        
        print("\n" + "=" * 60)
        print(f"✅ Cleanup complete!")
        print(f"   Cleaned: {cleaned}")
        print(f"   Nulled: {nulled}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clean_all_malformed_emails()

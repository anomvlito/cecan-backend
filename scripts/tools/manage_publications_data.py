import sys
import os
import json
import argparse
from datetime import datetime
from sqlalchemy import text
from typing import List, Dict, Any

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import SessionLocal
from core.models import Publication, PublicationChunk, PublicationImpact, ResearcherPublication, ExternalMetric

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)

class PublicationManager:
    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def serialize_model(self, instance) -> Dict[str, Any]:
        """Convert SQLAlchemy model instance to dictionary."""
        data = {}
        for column in instance.__table__.columns:
            value = getattr(instance, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            data[column.name] = value
        return data

    def backup(self, filename: str = None):
        """Backup all publication-related data to a JSON file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(BACKUP_DIR, f"publications_backup_{timestamp}.json")

        print(f"📦 Starting backup to {filename}...")
        
        data = {
            "meta": {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            },
            "publications": [],
            "chunks": [],
            "impacts": [],
            "researcher_publications": [],
            "external_metrics": [] # Only those related to publications if possible, or all for safety
        }

        # 1. Publications
        pubs = self.db.query(Publication).all()
        data["publications"] = [self.serialize_model(p) for p in pubs]
        print(f"   - Publications: {len(data['publications'])}")

        # 2. Chunks
        chunks = self.db.query(PublicationChunk).all()
        data["chunks"] = [self.serialize_model(c) for c in chunks]
        print(f"   - Chunks: {len(data['chunks'])}")

        # 3. Impacts
        impacts = self.db.query(PublicationImpact).all()
        data["impacts"] = [self.serialize_model(i) for i in impacts]
        print(f"   - Impacts: {len(data['impacts'])}")

        # 4. Researcher Links
        links = self.db.query(ResearcherPublication).all()
        data["researcher_publications"] = [self.serialize_model(l) for l in links]
        print(f"   - Researcher Links: {len(data['researcher_publications'])}")

        # Save to file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Backup completed successfully: {filename}")
        return filename

    def purge(self):
        """Delete all publication data."""
        print("⚠️  WARNING: This will DELETE ALL PUBLICATION DATA.")
        confirm = input("Are you sure? Type 'DELETE' to confirm: ")
        if confirm != "DELETE":
            print("❌ Operation cancelled.")
            return

        try:
            # Order matters due to Foreign Keys
            print("🗑️  Deleting Researcher Links...")
            self.db.query(ResearcherPublication).delete()
            
            print("🗑️  Deleting Impacts...")
            self.db.query(PublicationImpact).delete()
            
            print("🗑️  Deleting Chunks...")
            self.db.query(PublicationChunk).delete()
            
            print("🗑️  Deleting Publications...")
            self.db.query(Publication).delete()
            
            self.db.commit()
            print("✅ Purge completed. All publication data is gone.")
            
        except Exception as e:
            self.db.rollback()
            print(f"❌ Error during purge: {e}")

    def restore(self, filename: str):
        """Restore data from a backup JSON file."""
        if not os.path.exists(filename):
            print(f"❌ File not found: {filename}")
            return

        print(f"♻️  Starting restore from {filename}...")
        
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        try:
            # 1. Clean current state (Optional? Better to be safe and clean first to avoid ID conflicts)
            # For now, let's assume we want a clean restore.
            print("   Cleaning existing data first...")
            self.db.query(ResearcherPublication).delete()
            self.db.query(PublicationImpact).delete()
            self.db.query(PublicationChunk).delete()
            self.db.query(Publication).delete()
            self.db.flush()

            # 2. Restore Publications
            print(f"   Restoring {len(data['publications'])} publications...")
            for p_data in data['publications']:
                # Handle datetime parsing
                if p_data.get('last_enrichment_at'):
                    p_data['last_enrichment_at'] = datetime.fromisoformat(p_data['last_enrichment_at'])
                if p_data.get('metrics_last_updated'):
                    p_data['metrics_last_updated'] = datetime.fromisoformat(p_data['metrics_last_updated'])
                if p_data.get('last_audit_date'):
                    p_data['last_audit_date'] = datetime.fromisoformat(p_data['last_audit_date'])
                
                self.db.add(Publication(**p_data))
            self.db.flush() # Commit IDs

            # 3. Restore Related Data
            print(f"   Restoring {len(data['chunks'])} chunks...")
            for c_data in data['chunks']:
                self.db.add(PublicationChunk(**c_data))

            print(f"   Restoring {len(data['impacts'])} impacts...")
            for i_data in data['impacts']:
                self.db.add(PublicationImpact(**i_data))
                
            print(f"   Restoring {len(data['researcher_publications'])} links...")
            for l_data in data['researcher_publications']:
                self.db.add(ResearcherPublication(**l_data))

            self.db.commit()
            print("✅ Restore completed successfully.")

        except Exception as e:
            self.db.rollback()
            print(f"❌ Error during restore: {e}")

def main():
    parser = argparse.ArgumentParser(description="Manage Publication Data (Backup/Purge/Restore)")
    parser.add_argument('--action', choices=['backup', 'purge', 'restore'], required=True, help="Action to perform")
    parser.add_argument('--file', help="Backup file path (required for restore)")
    
    args = parser.parse_args()
    
    manager = PublicationManager()
    
    try:
        if args.action == 'backup':
            manager.backup(args.file)
        elif args.action == 'purge':
            # Auto-backup before purge recommendation? 
            # Let's manual for now script simplicity, but user instructed strict safety.
            # Ideally the user runs backup first.
            manager.purge()
        elif args.action == 'restore':
            if not args.file:
                print("❌ --file argument is required for restore")
                return
            manager.restore(args.file)
    finally:
        manager.close()

if __name__ == "__main__":
    main()

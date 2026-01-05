"""
🌍 CECAN - Migrate ORCID Metadata for Existing Publications
Processes existing publications to extract ORCIDs and enrich with country data
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import csv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import get_session
from core.models import Publication
from services.orcid_metadata_service import (
    extract_orcids_from_pdf_hyperlinks,
    enrich_orcids_with_metadata
)


def migrate_orcid_metadata(limit: int = None, dry_run: bool = False):
    """
    Migrate ORCID metadata for existing publications.
    
    Args:
        limit: Process only N publications (for testing)
        dry_run: Don't save to database, only print results
    """
    print("\n" + "=" * 80)
    print("🌍 CECAN - Migración de Metadata ORCID".center(80))
    print("=" * 80 + "\n")
    
    if dry_run:
        print("⚠️  DRY RUN MODE - No se guardará en base de datos\n")
    
    db = get_session()
    
    try:
        # Get publications that have local_path (PDF file exists)
        query = db.query(Publication).filter(
            Publication.local_path != None,
            Publication.local_path != ""
        )
        
        if limit:
            query = query.limit(limit)
            print(f"📊 Procesando primeras {limit} publicaciones con PDF\n")
        
        publications = query.all()
        total_pubs = len(publications)
        
        print(f"📂 Total de publicaciones a procesar: {total_pubs}\n")
        print("=" * 80)
        
        results = []
        processed = 0
        with_orcids = 0
        errors = 0
        
        for idx, pub in enumerate(publications, 1):
            print(f"\n[{idx}/{total_pubs}] 📄 {pub.title[:60]}...")
            print(f"   ID: {pub.id} | Archivo: {pub.local_path}")
            
            try:
                # Check if file exists
                if not os.path.exists(pub.local_path):
                    print(f"   ⚠️  Archivo no encontrado: {pub.local_path}")
                    results.append({
                        'id': pub.id,
                        'status': 'file_not_found',
                        'orcids': 0
                    })
                    errors += 1
                    continue
                
                # Read PDF
                with open(pub.local_path, 'rb') as f:
                    content = f.read()
                
                # Extract ORCIDs from hyperlinks
                orcids_list = extract_orcids_from_pdf_hyperlinks(content)
                
                if not orcids_list:
                    print("   ℹ️  Sin ORCIDs detectados")
                    results.append({
                        'id': pub.id,
                        'status': 'no_orcids',
                        'orcids': 0
                    })
                    processed += 1
                    continue
                
                print(f"   🆔 ORCIDs encontrados: {len(orcids_list)}")
                for orcid in orcids_list:
                    print(f"      • {orcid}")
                
                # Enrich with metadata from ORCID API
                author_metadata = enrich_orcids_with_metadata(orcids_list)
                
                # Count successful metadata fetches
                successful = len([m for m in author_metadata.values() if not m.get('fetch_error')])
                print(f"   ✅ Metadata obtenida: {successful}/{len(orcids_list)} autores")
                
                # Display author info
                for orcid, metadata in author_metadata.items():
                    if not metadata.get('fetch_error'):
                        name = metadata.get('name', 'Unknown')
                        countries = ', '.join(metadata.get('countries', [])) or 'No country'
                        print(f"      👤 {name} - {countries}")
                
                # Update publication
                if not dry_run:
                    pub.extracted_orcids = ",".join(orcids_list)
                    pub.author_metadata = author_metadata
                    db.commit()
                    print(f"   💾 Base de datos actualizada")
                else:
                    print(f"   🔍 DRY RUN - No guardado")
                
                results.append({
                    'id': pub.id,
                    'status': 'success',
                    'orcids': len(orcids_list),
                    'metadata_fetched': successful
                })
                
                with_orcids += 1
                processed += 1
                
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                results.append({
                    'id': pub.id,
                    'status': 'error',
                    'error': str(e)
                })
                errors += 1
        
        # Summary
        print("\n" + "=" * 80)
        print("\n" + "🎯 " + "RESUMEN DE MIGRACIÓN".center(76) + " 🎯")
        print("=" * 80)
        print(f"\n📊 Estadísticas:")
        print(f"   • Total procesadas: {processed}")
        print(f"   • Con ORCIDs: {with_orcids}")
        print(f"   • Sin ORCIDs: {processed - with_orcids}")
        print(f"   • Errores: {errors}")
        
        # Export report
        if not dry_run:
            export_migration_report(results)
        
        print("\n" + "=" * 80)
        print("\n✨ Migración completada!\n")
        
    finally:
        db.close()


def export_migration_report(results):
    """Export migration results to CSV"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"orcid_migration_report_{timestamp}.csv"
    filepath = Path(__file__).parent.parent / "data" / filename
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'status', 'orcids', 'metadata_fetched', 'error'])
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n💾 Reporte exportado: {filepath}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate ORCID metadata for existing publications')
    parser.add_argument('--limit', type=int, help='Process only N publications')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t save to database')
    
    args = parser.parse_args()
    
    migrate_orcid_metadata(limit=args.limit, dry_run=args.dry_run)

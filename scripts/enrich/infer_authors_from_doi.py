import sys
import os
import argparse
import asyncio
import pandas as pd
from datetime import datetime
from difflib import SequenceMatcher
import unicodedata

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add utilidades path for Semantic Scholar
util_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'utilidades', 'reusable_scholar_module', 'backend')
sys.path.append(util_path)

from database.session import get_session
from core.models import Publication, AcademicMember, ResearcherPublication, ResearcherDetails
from services.openalex_service import get_publication_by_doi

# Import Semantic Scholar client
try:
    from client import SemanticScholarClient
    S2_AVAILABLE = True
    print("✅ Semantic Scholar module loaded")
except ImportError:
    print("⚠️ Semantic Scholar module not found. Will use only OpenAlex.")
    S2_AVAILABLE = False

# Global storage for S2 data to export to Excel
s2_data_export = []

def normalize_name(name):
    """Normalize name for comparison (lowercase, remove accents)."""
    if not name:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', name)
    only_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return only_ascii.lower().strip()

def calculate_similarity(name1, name2):
    """Calculate string similarity ratio."""
    return SequenceMatcher(None, normalize_name(name1), normalize_name(name2)).ratio()

async def fetch_s2_data(doi):
    """Fetch data from Semantic Scholar API."""
    if not S2_AVAILABLE:
        return None
    
    try:
        client = SemanticScholarClient()
        data = await client.get_paper_intelligence(doi)
        return data
    except Exception as e:
        print(f"  [S2] ⚠️ Error fetching from Semantic Scholar: {e}")
        return None

def match_authors(publication_id, doi, dry_run=True):
    """
    Fetch authors from OpenAlex + Semantic Scholar and match with local DB members.
    """
    session = get_session()
    matches_found = []
    
    try:
        print(f"  [match_authors] Iniciando para Pub ID {publication_id}")
        print(f"  [match_authors] DOI a consultar: {doi}")
        
        # === 1. Fetch from OpenAlex ===
        print(f"  [match_authors] Llamando a OpenAlex API...")
        oa_authors = []
        try:
            oa_data = get_publication_by_doi(doi)
            print(f"  [match_authors] ✅ Respuesta recibida de OpenAlex")
            
            for authorship in oa_data.get('authorships', []):
                author = authorship.get('author', {})
                if author.get('display_name'):
                    oa_authors.append({
                        'name': author.get('display_name'),
                        'orcid': author.get('orcid', '').split('/')[-1] if author.get('orcid') else None,
                        'position': authorship.get('author_position'),
                        'source': 'OpenAlex'
                    })
        except Exception as e:
            print(f"  [match_authors] ⚠️ OpenAlex error: {e}")

        if oa_authors:
            print(f"  [OpenAlex] Found {len(oa_authors)} authors")

        # === 2. Fetch from Semantic Scholar ===
        s2_authors = []
        s2_full_data = None
        if S2_AVAILABLE:
            print(f"  [match_authors] Llamando a Semantic Scholar API...")
            try:
                s2_full_data = asyncio.run(fetch_s2_data(doi))
                if s2_full_data and s2_full_data.get('paperId') != 'NOT_FOUND':
                    print(f"  [match_authors] ✅ Respuesta recibida de Semantic Scholar")
                    
                    for author in s2_full_data.get('authors', []):
                        if author.get('name'):
                            s2_authors.append({
                                'name': author.get('name'),
                                'authorId': author.get('authorId'),
                                'source': 'SemanticScholar'
                            })
                    
                    # Store for Excel export
                    s2_data_export.append({
                        'DOI': doi,
                        'Publication_ID': publication_id,
                        'S2_PaperID': s2_full_data.get('paperId'),
                        'Title': s2_full_data.get('title'),
                        'Year': s2_full_data.get('year'),
                        'Authors': '; '.join([a.get('name', '') for a in s2_full_data.get('authors', [])]),
                        'TLDR': s2_full_data.get('tldr'),
                        'Citation_Intents': str(s2_full_data.get('intent_breakdown', {}))
                    })
                else:
                    print(f"  [S2] ⚠️ Paper not found in Semantic Scholar")
            except Exception as e:
                print(f"  [S2] ⚠️ Error: {e}")
        
        if s2_authors:
            print(f"  [S2] Found {len(s2_authors)} authors")

        # === 3. Combine authors from both sources ===
        all_authors = oa_authors + s2_authors
        unique_authors = {}
        for author in all_authors:
            name = author['name']
            if name not in unique_authors:
                unique_authors[name] = author
        
        combined_authors = list(unique_authors.values())
        print(f"  [Combined] Total unique authors: {len(combined_authors)}")

        if not combined_authors:
            print("  ⚠️ No authors found from any source")
            return []

        # === 4. Get CECAN Core Members ===
        print(f"  [match_authors] Consultando miembros académicos CECAN...")
        
        query = session.query(AcademicMember).filter(AcademicMember.is_active == True)
        
        from sqlalchemy import or_
        
        researchers_with_category = session.query(ResearcherDetails.member_id).filter(
            ResearcherDetails.category.isnot(None)
        ).subquery()
        
        local_members = query.filter(
            or_(
                AcademicMember.id.in_(researchers_with_category),
                AcademicMember.member_type == "student"
            )
        ).all()
        
        print(f"  [match_authors] ✅ {len(local_members)} miembros CECAN válidos en BD")

        # === 5. Fuzzy Match ===
        for author in combined_authors:
            best_match = None
            highest_score = 0.0
            target_name = author['name']
            
            for member in local_members:
                score = calculate_similarity(target_name, member.full_name)
                
                # ORCID boost (OpenAlex only)
                member_orcid = None
                if member.researcher_details and member.researcher_details.orcid:
                    member_orcid = member.researcher_details.orcid
                
                if author.get('orcid') and member_orcid and author['orcid'] == member_orcid:
                    score = 1.0
                
                if score > highest_score:
                    highest_score = score
                    best_match = member

            # Threshold check
            if highest_score >= 0.82:
                source_tag = f"[{author['source']}]"
                print(f"  ✅ MATCH {source_tag}: '{target_name}' ~= '{best_match.full_name}' (Score: {highest_score:.2f})")
                
                existing_conn = session.query(ResearcherPublication).filter_by(
                    member_id=best_match.id,
                    publication_id=publication_id
                ).first()
                
                if not existing_conn:
                    if not dry_run:
                        member = session.merge(best_match)
                        new_conn = ResearcherPublication(
                            member_id=member.id,
                            publication_id=publication_id,
                            match_score=int(highest_score * 100),
                            match_method=f"fuzzy_doi_{author['source'].lower()}"
                        )
                        session.add(new_conn)
                        print("     -> Connection created (Pending Commit)")
                    else:
                        print("     -> [Dry Run] Would create connection")
                    
                    matches_found.append(f"{best_match.full_name} ({int(highest_score*100)}%)")
                else:
                    print("     -> Connection already exists")

        if not dry_run:
            session.commit()
            print("  💾 Changes saved to database.")
            
    except Exception as e:
        print(f"  ❌ Error processing publication: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()
        
    return matches_found

def run_recovery(year=None, dry_run=True):
    global s2_data_export
    session = get_session()
    
    try:
        print("=" * 70)
        print("  Script de Recuperación de Autores mediante DOI")
        print("  Fuentes: OpenAlex + Semantic Scholar")
        print("=" * 70)
        print(f"Modo: {'DRY RUN (Solo simulación)' if dry_run else 'LIVE (Guardando cambios)'}")
        print()
        
        print("[LOG] Conectando a base de datos...")
        query = session.query(Publication).filter(Publication.canonical_doi.isnot(None))
        if year:
            query = query.filter(Publication.year.like(f"%{year}%"))
            print(f"[LOG] Filtrando por año: {year}")
            
        print("[LOG] Consultando publicaciones...")
        publications = query.all()
        print(f"[LOG] ✅ Total publicaciones con DOI a analizar: {len(publications)}")
        print()
        
        total_new_matches = 0
        
        for i, pub in enumerate(publications):
            print(f"\n{'='*60}")
            print(f"[LOG] Procesando publicación {i+1}/{len(publications)}")
            print(f"[LOG] ID: {pub.id} | Título: {pub.title[:50] if pub.title else 'Sin título'}...")
            print(f"[LOG] DOI: {pub.canonical_doi}")
            matches = match_authors(pub.id, pub.canonical_doi, dry_run=dry_run)
            if matches:
                total_new_matches += len(matches)
                print(f"[LOG] ✅ Matches encontrados: {len(matches)}")
            else:
                print(f"[LOG] ⚠️ Sin matches para esta publicación")
                
        print("\n" + "=" * 70)
        print("RESUMEN")
        print("=" * 70)
        print(f"Total Nuevas Conexiones Identificadas: {total_new_matches}")
        
        # Export Semantic Scholar data to Excel
        if s2_data_export:
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'archivado')
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_path = os.path.join(output_dir, f'semantic_scholar_data_{timestamp}.xlsx')
            
            df = pd.DataFrame(s2_data_export)
            df.to_excel(excel_path, index=False)
            print(f"\n📊 Datos de Semantic Scholar exportados a:")
            print(f"   {excel_path}")
            print(f"   Total filas: {len(s2_data_export)}")
        else:
            print("\n⚠️ No se recopiló data de Semantic Scholar")
        
        print("=" * 70)
        
    finally:
        session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recuperar autores de publicaciones usando OpenAlex + Semantic Scholar")
    parser.add_argument("--year", type=str, help="Filtrar por año (ej: 2025)")
    parser.add_argument("--live", action="store_true", help="Ejecutar guardando cambios en BD")
    args = parser.parse_args()
    
    run_recovery(year=args.year, dry_run=not args.live)

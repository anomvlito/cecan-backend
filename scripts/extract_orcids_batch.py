"""
🔬 CECAN - Extractor Rápido de ORCIDs desde PDFs
Analiza carpeta de PDFs, extrae ORCIDs de HYPERLINKS y texto.
Version 2.0 - Extracción desde anotaciones/hipervínculos del PDF
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Set
from datetime import datetime
import PyPDF2

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import get_session
from core.models import AcademicMember, ResearcherDetails
from services.publication_service import extract_text_from_pdf


class ORCIDExtractor:
    """Elegant ORCID extraction from PDF hyperlinks and text"""
    
    ORCID_PATTERN = re.compile(r'\b(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])\b', re.IGNORECASE)
    
    def __init__(self, db_session):
        self.db = db_session
        self.cecan_researchers = self._load_cecan_researchers()
        self.results = []
        
    def _load_cecan_researchers(self) -> Dict[str, Dict]:
        """Load active CECAN researchers with their ORCIDs"""
        print("📋 Cargando investigadores CECAN activos...")
        
        researchers = self.db.query(AcademicMember, ResearcherDetails).outerjoin(
            ResearcherDetails, AcademicMember.id == ResearcherDetails.member_id
        ).filter(
            AcademicMember.member_type == 'researcher',
            AcademicMember.is_active == True
        ).all()
        
        cecan_map = {}
        for member, details in researchers:
            if details and details.orcid:
                # Clean ORCID (remove URL if present)
                clean_orcid = details.orcid.split('/')[-1].strip() if '/' in details.orcid else details.orcid.strip()
                cecan_map[clean_orcid] = {
                    'id': member.id,
                    'name': member.full_name,
                    'email': member.email,
                    'orcid': clean_orcid
                }
        
        print(f"   ✅ {len(cecan_map)} investigadores CECAN con ORCID\n")
        return cecan_map
    
    def extract_orcids_from_pdf(self, pdf_path: str) -> Set[str]:
        """
        Extract ORCIDs from PDF hyperlinks (annotations) and text.
        Priority: Hyperlinks (green ORCID icons) > Text
        """
        orcids = set()
        
        try:
            # Method 1: Extract from PDF annotations/hyperlinks (PRIMARY METHOD)
            with open(pdf_path, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                
                for page_num, page in enumerate(pdf.pages):
                    # Extract annotations (where ORCID icons/links usually are)
                    if '/Annots' in page:
                        try:
                            annotations = page['/Annots']
                            if annotations:
                                # Handle both direct and indirect references
                                if hasattr(annotations, 'get_object'):
                                    annotations = annotations.get_object()
                                
                                for annot in annotations:
                                    try:
                                        annot_obj = annot.get_object() if hasattr(annot, 'get_object') else annot
                                        
                                        if annot_obj and '/A' in annot_obj:
                                            action = annot_obj['/A']
                                            if hasattr(action, 'get_object'):
                                                action = action.get_object()
                                            
                                            if '/URI' in action:
                                                uri = str(action['/URI'])
                                                # Check if it's an ORCID URL
                                                if 'orcid.org' in uri.lower():
                                                    match = self.ORCID_PATTERN.search(uri)
                                                    if match:
                                                        orcids.add(match.group(1))
                                                        print(f"      🔗 ORCID desde hyperlink: {match.group(1)}")
                                    except Exception as e:
                                        continue
                        except Exception as e:
                            continue
            
            # Method 2: Extract from text content (FALLBACK)
            with open(pdf_path, 'rb') as f:
                content = f.read()
                text = extract_text_from_pdf(content)
                
                if text:
                    # Search for ORCID URLs in extracted text
                    orcid_url_pattern = re.compile(r'orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])', re.IGNORECASE)
                    url_matches = orcid_url_pattern.findall(text)
                    
                    for match in url_matches:
                        if match not in orcids:
                            orcids.add(match)
                            print(f"      📝 ORCID desde texto: {match}")
                    
                    # Also search for plain ORCIDs (without URL)
                    plain_matches = self.ORCID_PATTERN.findall(text)
                    for match in plain_matches:
                        if match not in orcids and len(orcids) < 20:  # Limit to avoid false positives
                            orcids.add(match)
                            print(f"      📄 ORCID plano: {match}")
            
            return orcids
            
        except Exception as e:
            print(f"   ⚠️  Error leyendo {pdf_path}: {e}")
            return set()
    
    def process_directory(self, directory: str):
        """Process all PDFs in directory"""
        pdf_dir = Path(directory)
        
        if not pdf_dir.exists():
            print(f"❌ Directorio no encontrado: {directory}")
            return
        
        pdf_files = list(pdf_dir.glob("**/*.pdf"))
        total_pdfs = len(pdf_files)
        
        print(f"📂 Procesando {total_pdfs} PDFs desde: {directory}\n")
        print("=" * 80)
        
        for idx, pdf_file in enumerate(pdf_files, 1):
            filename = pdf_file.name
            print(f"\n[{idx}/{total_pdfs}] 📄 {filename}")
            
            # Extract ORCIDs (from hyperlinks + text)
            orcids_found = self.extract_orcids_from_pdf(str(pdf_file))
            
            if not orcids_found:
                print("   ℹ️  Sin ORCIDs detectados")
                continue
            
            print(f"   🆔 ORCIDs totales: {len(orcids_found)}")
            
            # Match against CECAN researchers
            cecan_matches = []
            for orcid in orcids_found:
                if orcid in self.cecan_researchers:
                    researcher = self.cecan_researchers[orcid]
                    cecan_matches.append(researcher)
                    print(f"      ✅ CECAN MATCH: {researcher['name']} ({orcid})")
                else:
                    print(f"      🌍 Externo: {orcid}")
            
            # Store result
            self.results.append({
                'filename': filename,
                'path': str(pdf_file),
                'orcids_total': list(orcids_found),
                'cecan_matches': cecan_matches,
                'match_count': len(cecan_matches)
            })
        
        print("\n" + "=" * 80)
        self._print_summary()
    
    def _print_summary(self):
        """Print beautiful summary report"""
        print("\n" + "🎯 " + "RESUMEN FINAL".center(76) + " 🎯")
        print("=" * 80)
        
        total_pdfs = len(self.results)
        pdfs_with_orcids = len([r for r in self.results if r['orcids_total']])
        pdfs_with_cecan = len([r for r in self.results if r['cecan_matches']])
        
        all_orcids = set()
        all_cecan_orcids = set()
        
        for result in self.results:
            all_orcids.update(result['orcids_total'])
            for match in result['cecan_matches']:
                all_cecan_orcids.add(match['orcid'])
        
        print(f"\n📊 Estadísticas Generales:")
        print(f"   • PDFs procesados: {total_pdfs}")
        print(f"   • PDFs con ORCIDs: {pdfs_with_orcids}")
        print(f"   • PDFs con autores CECAN: {pdfs_with_cecan}")
        print(f"   • ORCIDs únicos encontrados: {len(all_orcids)}")
        print(f"   • ORCIDs de investigadores CECAN: {len(all_cecan_orcids)}")
        
        # Top CECAN authors
        if all_cecan_orcids:
            print(f"\n👥 Investigadores CECAN Detectados ({len(all_cecan_orcids)}):")
            cecan_counts = {}
            for result in self.results:
                for match in result['cecan_matches']:
                    orcid = match['orcid']
                    if orcid not in cecan_counts:
                        cecan_counts[orcid] = {
                            'name': match['name'],
                            'count': 0,
                            'papers': []
                        }
                    cecan_counts[orcid]['count'] += 1
                    cecan_counts[orcid]['papers'].append(result['filename'])
            
            # Sort by count
            sorted_authors = sorted(cecan_counts.items(), key=lambda x: x[1]['count'], reverse=True)
            
            for orcid, data in sorted_authors:
                print(f"   • {data['name']}")
                print(f"     ORCID: {orcid}")
                print(f"     Publicaciones: {data['count']}")
                if data['count'] <= 3:  # Show papers for authors with few papers
                    for paper in data['papers']:
                        print(f"       - {paper}")
                print()
        
        # Non-CECAN ORCIDs
        non_cecan_orcids = all_orcids - all_cecan_orcids
        if non_cecan_orcids:
            print(f"\n🌍 ORCIDs Externos (No CECAN): {len(non_cecan_orcids)}")
            for orcid in sorted(non_cecan_orcids)[:10]:  # Show first 10
                print(f"   • {orcid}")
            if len(non_cecan_orcids) > 10:
                print(f"   ... y {len(non_cecan_orcids) - 10} más")
        
        print("\n" + "=" * 80)
        
        # Export option
        self._export_csv()
    
    def _export_csv(self):
        """Export results to CSV"""
        import csv
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"orcid_extraction_report_{timestamp}.csv"
        filepath = Path(__file__).parent.parent / "data" / filename
        
        # Ensure data directory exists
        filepath.parent.mkdir(exist_ok=True)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Archivo PDF', 
                'ORCIDs Totales', 
                'ORCIDs CECAN',
                'Autores CECAN',
                'Todos los ORCIDs'
            ])
            
            for result in self.results:
                cecan_authors = ', '.join([m['name'] for m in result['cecan_matches']])
                cecan_orcids = ', '.join([m['orcid'] for m in result['cecan_matches']])
                all_orcids_str = ', '.join(result['orcids_total'])
                
                writer.writerow([
                    result['filename'],
                    len(result['orcids_total']),
                    cecan_orcids,
                    cecan_authors,
                    all_orcids_str
                ])
        
        print(f"\n💾 Reporte exportado: {filepath}")


def main():
    """Main execution"""
    print("\n" + "=" * 80)
    print("🔬 CECAN - Extractor de ORCIDs desde PDFs (v2.0 - Hyperlinks)".center(80))
    print("=" * 80 + "\n")
    
    # Database connection
    db = get_session()
    
    try:
        # Initialize extractor
        extractor = ORCIDExtractor(db)
        
        # Process directory
        pdf_directory = "data/publications/Registro Publicaciones"
        extractor.process_directory(pdf_directory)
        
    finally:
        db.close()
    
    print("\n✨ Proceso completado!\n")


if __name__ == "__main__":
    main()

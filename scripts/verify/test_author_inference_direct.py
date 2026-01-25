#!/usr/bin/env python3
"""
Testing DIRECTO del servicio de inferencia (sin HTTP)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import get_session
from core.models import Publication, ResearcherPublication
from services.author_inference_service import AuthorInferenceService

def main():
    print("="*60)
    print("🧪 TEST DIRECTO: Author Inference Service")
    print("="*60)
    
    session = get_session()
    
    try:
        # 1. Buscar publicación con DOI sin autores
        print("\n1️⃣ Buscando publicación para probar...")
        
        pubs = session.query(Publication).filter(
            Publication.canonical_doi.isnot(None)
        ).all()
        
        test_pub = None
        for pub in pubs:
            count = session.query(ResearcherPublication).filter(
                ResearcherPublication.publication_id == pub.id
            ).count()
            if count == 0:
                test_pub = pub
                break
        
        if not test_pub:
            print("❌ No se encontraron publicaciones con DOI sin autores")
            return
        
        print(f"\n✅ Publicación seleccionada:")
        print(f"   ID: {test_pub.id}")
        print(f"   Título: {test_pub.title[:80]}")
        print(f"   DOI: {test_pub.canonical_doi}")
        
        # 2. Crear servicio e inferir autores
        print(f"\n2️⃣ Llamando al servicio de inferencia...")
        print(f"   Threshold: 0.7")
        print(f"   Auto-link: False (solo ver resultados)")
        
        service = AuthorInferenceService(session)
        
        result = service.infer_authors_for_publication(
            publication_id=test_pub.id,
            auto_link=False,
            threshold=0.7
        )
        
        # 3. Mostrar resultados
        print(f"\n{'='*60}")
        print(f"📊 RESULTADOS")
        print(f"{'='*60}")
        
        print(f"\nDOI consultado: {result['doi']}")
        print(f"Fuentes: {', '.join(result['sources_consulted'])}")
        print(f"Autores externos encontrados: {result['stats']['total_external_authors']}")
        print(f"Matches encontrados: {result['stats']['total_matches_found']}")
        
        if result['candidates']:
            print(f"\n🔗 CANDIDATOS ENCONTRADOS:\n")
            for i, candidate in enumerate(result['candidates'], 1):
                print(f"{i}. Autor externo: {candidate['external_author']}")
                print(f"   Fuente: {candidate['source']}")
                
                if candidate['matched_member']:
                    member = candidate['matched_member']
                    score = candidate['score']
                    print(f"   ✅ MATCH: {member['name']} ({member['category']})")
                    print(f"   Score: {score:.2f} ({int(score*100)}%)")
                    
                    # Código de colores para score
                    if score >= 0.9:
                        print(f"   🟢 Confianza: MUY ALTA")
                    elif score >= 0.8:
                        print(f"   🟡 Confianza: Alta")
                    elif score >= 0.7:
                        print(f"   🟠 Confianza: Media (revisar)")
                    else:
                        print(f"   🔴 Confianza: Baja")
                else:
                    print(f"   ❌ No se encontró match")
                
                print()
        else:
            print("\n⚠️ No se encontraron candidatos")
        
        # 4. Preguntar si quiere hacer auto-link
        if result['candidates']:
            print("="*60)
            response = input("\n¿Ejecutar de nuevo con AUTO-LINK habilitado? (s/n): ")
            
            if response.lower() == 's':
                print("\n3️⃣ Ejecutando con AUTO-LINK...")
                
                result_linked = service.infer_authors_for_publication(
                    publication_id=test_pub.id,
                    auto_link=True,
                    threshold=0.7
                )
                
                print(f"\n✅ Resultados:")
                print(f"   Conexiones creadas: {result_linked['stats']['auto_linked']}")
                print(f"   Skipped: {result_linked['stats']['skipped']}")
                
                # Verificar en BD
                new_count = session.query(ResearcherPublication).filter(
                    ResearcherPublication.publication_id == test_pub.id
                ).count()
                
                print(f"\n🔍 Verificación en BD:")
                print(f"   Autores conectados ahora: {new_count}")
        
        print("\n" + "="*60)
        print("✅ Test completado")
        print("="*60)
        
    finally:
        session.close()

if __name__ == "__main__":
    main()

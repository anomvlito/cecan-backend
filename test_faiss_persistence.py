"""
Script de prueba para verificar la persistencia de embeddings con FAISS
"""
import os
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, 'D:\\0 one drive fgortega microsoft\\OneDrive - Universidad Católica de Chile\\0 antigravity\\cecan-agent\\backend')

from dotenv import load_dotenv
load_dotenv()

from services.rag_service import get_semantic_engine, reset_semantic_engine

print("="*70)
print(" TEST 1: Inicialización desde cero (debe generar y guardar)")
print("="*70)

# Delete cache if exists
vectorstore_path = Path("backend/data/vectorstore/projects")
if vectorstore_path.exists():
    import shutil
    shutil.rmtree(vectorstore_path)
    print("✓ Cache eliminado para prueba limpia")

# Reset singleton
reset_semantic_engine()

# First initialization (should generate and save)
print("\nInicializando SemanticSearchEngine por primera vez...")
start_time = time.time()
engine1 = get_semantic_engine()
elapsed1 = time.time() - start_time
print(f"\n⏱️  Tiempo transcurrido: {elapsed1:.2f} segundos")

print("\n" + "="*70)
print(" TEST 2: Reinicialización (debe cargar desde disco)")
print("="*70)

# Reset singleton to simulate server restart
reset_semantic_engine()

# Second initialization (should load from disk)
print("\nReinicializando SemanticSearchEngine (simulando reinicio)...")
start_time = time.time()
engine2 = get_semantic_engine()
elapsed2 = time.time() - start_time
print(f"\n⏱️  Tiempo transcurrido: {elapsed2:.2f} segundos")

print("\n" + "="*70)
print(" RESUMEN DE RESULTADOS")
print("="*70)
print(f"Primera inicialización:  {elapsed1:.2f}s (generación + guardado)")
print(f"Segunda inicialización:  {elapsed2:.2f}s (carga desde disco)")
print(f"Mejora de rendimiento:   {((elapsed1 - elapsed2) / elapsed1 * 100):.1f}%")

if elapsed2 < 1.0:
    print("\n✅ ÉXITO: La carga desde disco es casi instantánea!")
else:
    print(f"\n⚠️  ADVERTENCIA: La carga tomó {elapsed2:.2f}s (esperado < 1s)")

# Check if vectorstore exists
if vectorstore_path.exists() and (vectorstore_path / "index.faiss").exists():
    print(f"\n✓ Índice FAISS guardado en: {vectorstore_path}")
else:
    print(f"\n✗ ERROR: No se encontró índice FAISS en {vectorstore_path}")

# Test search
print("\n" + "="*70)
print(" TEST 3: Búsqueda semántica")
print("="*70)
results = engine2.search("desigualdad", top_k=3)
print(f"\nEncontrados {len(results)} resultados para 'desigualdad'")
for i, res in enumerate(results[:3], 1):
    print(f"{i}. {res['project']['titulo']} (score: {res['score']:.3f})")

print("\n" + "="*70)
print(" TEST COMPLETADO")
print("="*70)

#!/usr/bin/env python3
"""
Test mejorado para extraer datos con regex del texto plano
"""
import requests
from bs4 import BeautifulSoup
import re

url = "https://cecan.cl/publicaciones/cientificas/integrated-clinico-molecular-analysis-of-gastric-cancer-in-european-and-latin-american-populations-legacy-project/"

print("=" * 80)
print("🔍 EXTRACCIÓN CON REGEX DEL TEXTO PLANO")
print("=" * 80)

headers = {'User-Agent': 'Mozilla/5.0'}

try:
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Obtener TODO el texto
    full_text = soup.get_text()
    
    # Limpiar espacios múltiples
    clean_text = re.sub(r'\s+', ' ', full_text).strip()
    
    print(f"\n📄 TEXTO COMPLETO ({len(clean_text)} caracteres)")
    print("-" * 80)
    print(clean_text[:3000])  # Primeros 3000 caracteres
    
    print("\n\n" + "=" * 80)
    print("🔍 EXTRAYENDO CON REGEX")
    print("=" * 80)
    
    # 1. FECHA - Buscar patrón de fecha
    fecha_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', clean_text)
    if fecha_match:
        fecha = fecha_match.group(1)
        print(f"\n📅 FECHA encontrada: {fecha}")
    else:
        print("\n❌ No se encontró fecha")
    
    # 2. RESUMEN - Todo después de "Sobre esta publicación"
    resumen_match = re.search(r'Sobre esta publicación\s*(.{200,1000})', clean_text)
    if resumen_match:
        resumen = resumen_match.group(1).strip()
        print(f"\n📝 RESUMEN encontrado ({len(resumen)} caracteres):")
        print(f"   {resumen[:300]}...")
    else:
        print("\n❌ No se encontró resumen")
    
    # 3. AUTORES - Buscar patrones comunes
    # Patrón 1: Lista de nombres antes de la fecha
    # Patrón 2: Después de "Autores:" o similar
    
    # Buscar sección que podría tener autores
    # Generalmente están entre el título y "Sobre esta publicación"
    titulo_match = re.search(r'Publicaciones científicas\s+(.+?)\s+\d{1,2}\s+\w+\s+\d{4}', clean_text)
    if titulo_match:
        titulo = titulo_match.group(1).strip()
        print(f"\n📌 TÍTULO: {titulo[:100]}...")
    
    # Buscar texto entre fecha y "Sobre esta publicación"
    autores_section = re.search(r'\d{1,2}\s+\w+\s+\d{4}\s+(.+?)\s+Sobre esta publicación', clean_text)
    if autores_section:
        posible_autores = autores_section.group(1).strip()
        print(f"\n👥 POSIBLE SECCIÓN DE AUTORES:")
        print(f"   {posible_autores[:500]}")
    
    # Mostrar contexto alrededor de la fecha
    print("\n\n📍 CONTEXTO ALREDEDOR DE LA FECHA:")
    print("-" * 80)
    if fecha_match:
        start = max(0, fecha_match.start() - 200)
        end = min(len(clean_text), fecha_match.end() + 500)
        context = clean_text[start:end]
        print(context)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

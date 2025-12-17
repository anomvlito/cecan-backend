"""
Script para listar los modelos de Gemini disponibles con tu API key
"""
import os
from dotenv import load_dotenv
import google.generativeai as genai

# Cargar variables de entorno
load_dotenv()

# Configurar API key
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    print("❌ ERROR: GOOGLE_API_KEY no encontrada en el archivo .env")
    exit(1)

genai.configure(api_key=api_key)

# Listar modelos
print("\n" + "="*70)
print(" MODELOS DE GEMINI DISPONIBLES CON TU API KEY")
print("="*70 + "\n")

models = genai.list_models()

# Filtrar solo los que soportan generación de contenido
generation_models = [m for m in models if 'generateContent' in m.supported_generation_methods]

if not generation_models:
    print("No se encontraron modelos disponibles")
else:
    print(f"Total de modelos disponibles: {len(generation_models)}\n")
    
    for model in generation_models:
        model_id = model.name.split('/')[-1]
        print(f"[OK] {model_id}")
        print(f"  Nombre: {model.display_name}")
        print(f"  Descripcion: {model.description}")
        print()

print("="*70)
print("\nTip: Para usar un modelo especifico, configura:")
print("   GEMINI_MODEL_NAME=<nombre_del_modelo>")
print("   en tu archivo .env\n")

#!/usr/bin/env python3
"""
Script auxiliar para obtener token de autenticación JWT
"""

import sys
import os
import requests
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = "http://localhost:8000/api"

def get_auth_token(username="admin@cecan.cl", password=None):
    """Obtiene token JWT del backend."""
    
    if not password:
        password = input(f"Contraseña para {username}: ")
    
    login_url = f"{API_URL}/auth/login"
    
    payload = {
        "email": username,
        "password": password
    }
    
    try:
        response = requests.post(login_url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"\n✅ Token obtenido exitosamente")
            print(f"\nExporta esta variable en tu terminal:")
            print(f"\nexport AUTH_TOKEN='{token}'")
            print(f"\nO úsala directamente en el script:")
            print(f"\nAUTH_TOKEN=\"{token}\" python scripts/test_author_inference.py")
            return token
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    # Intentar con credenciales por defecto o pedir input
    token = get_auth_token()

#!/usr/bin/env python3
"""
Script completo para verificar servidor y sincronizar publicaciones
"""
import requests
import sys
import time

# Configuración
BASE_URL = "http://localhost:8000"
ADMIN_EMAIL = "admin@cecan.cl"
ADMIN_PASSWORD = "admin123"

def check_server():
    """Verifica si el servidor está corriendo"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def main():
    print("=" * 80)
    print("🔄 SINCRONIZACIÓN DE PUBLICACIONES CECAN")
    print("=" * 80)
    
    # 1. Verificar servidor
    print("\n🔍 Verificando servidor...")
    if not check_server():
        print("❌ El servidor NO está corriendo")
        print("\n💡 Para iniciar el servidor, abre otra terminal y ejecuta:")
        print("   cd /mnt/d/0\\ one\\ drive\\ fgortega\\ microsoft/OneDrive\\ -\\ Universidad\\ Católica\\ de\\ Chile/0\\ antigravity/cecan-agent/backend")
        print("   python3 main.py")
        print("\n   Luego vuelve a ejecutar este script.")
        sys.exit(1)
    
    print("✅ Servidor está corriendo")
    
    # 2. Login
    print("\n🔐 Autenticando como admin...")
    try:
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={
                "username": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            },
            timeout=10
        )
        
        if login_response.status_code != 200:
            print(f"❌ Error en login: {login_response.status_code}")
            print(f"   Respuesta: {login_response.text}")
            print("\n💡 Verifica las credenciales en el script")
            sys.exit(1)
        
        token = login_response.json()["access_token"]
        print("✅ Autenticación exitosa")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {e}")
        sys.exit(1)
    
    # 3. Sincronizar publicaciones
    print("\n📚 Iniciando sincronización de publicaciones...")
    print("   (Esto puede tomar varios minutos)")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        sync_response = requests.post(
            f"{BASE_URL}/api/publications/sync",
            headers=headers,
            timeout=30
        )
        
        if sync_response.status_code == 200:
            result = sync_response.json()
            print(f"\n✅ {result.get('message', 'Sincronización iniciada')}")
            print("\n⏳ El proceso está corriendo en segundo plano.")
            print("   Esto puede tomar 5-15 minutos dependiendo de la cantidad de datos.")
            
            print("\n" + "=" * 80)
            print("📊 MONITOREO DEL PROGRESO")
            print("=" * 80)
            print("\nPara verificar el progreso, ejecuta en otra terminal:")
            print("   python3 scripts/check_db_status.py")
            print("\nO ejecuta este comando cada minuto:")
            print("   watch -n 60 'python3 scripts/check_db_status.py'")
            
        elif sync_response.status_code == 403:
            print("❌ Error: No tienes permisos de Editor")
            print("   El usuario admin debería tener estos permisos por defecto.")
        else:
            print(f"❌ Error: {sync_response.status_code}")
            print(f"   Respuesta: {sync_response.text}")
            
    except requests.exceptions.Timeout:
        print("⚠️  Timeout - pero la sincronización probablemente se inició")
        print("   Verifica con: python3 scripts/check_db_status.py")
    except Exception as e:
        print(f"❌ Error durante la sincronización: {e}")
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("✅ PROCESO COMPLETADO")
    print("=" * 80)

if __name__ == "__main__":
    main()

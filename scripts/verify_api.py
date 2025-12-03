import requests
import sys

# Configuration
BASE_URL = "http://localhost:8000/api"
USERNAME = "admin@cecan.cl"  # Default admin user
PASSWORD = "admin123"        # Default admin password

def test_health():
    """Test health check endpoint"""
    print("\n[1] Testing Health Check...")
    try:
        response = requests.get("http://localhost:8000/health")
        if response.status_code == 200:
            print("   ✅ Health check passed:", response.json())
            return True
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return False

def get_token():
    """Get authentication token"""
    print("\n[2] Getting Access Token...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": USERNAME, "password": PASSWORD}
        )
        if response.status_code == 200:
            token = response.json()["access_token"]
            print("   ✅ Login successful")
            return token
        else:
            print(f"   ❌ Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"   ❌ Login error: {e}")
        return None

def test_endpoints(token):
    """Test various protected endpoints"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: Get Current User
    print("\n[3] Testing Get Current User...")
    resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    if resp.status_code == 200:
        print(f"   ✅ User info: {resp.json()['email']} ({resp.json()['role']})")
    else:
        print(f"   ❌ Failed: {resp.status_code}")

    # Test 2: Get Members
    print("\n[4] Testing Get Members...")
    resp = requests.get(f"{BASE_URL}/members", headers=headers)
    if resp.status_code == 200:
        members = resp.json()
        print(f"   ✅ Retrieved {len(members)} members")
    else:
        print(f"   ❌ Failed: {resp.status_code}")

    # Test 3: Get Reports Summary
    print("\n[5] Testing Reports Summary...")
    resp = requests.get(f"{BASE_URL}/reports/summary", headers=headers)
    if resp.status_code == 200:
        print("   ✅ Reports summary retrieved")
    else:
        print(f"   ❌ Failed: {resp.status_code}")

    # Test 4: RAG Stats (Protected)
    print("\n[6] Testing RAG Stats...")
    resp = requests.get(f"{BASE_URL}/rag/stats", headers=headers)
    if resp.status_code == 200:
        print(f"   ✅ RAG Stats: {resp.json()}")
    else:
        print(f"   ❌ Failed: {resp.status_code}")

    # Test 5: Public Researchers
    print("\n[7] Testing Public Researchers...")
    resp = requests.get(f"{BASE_URL}/public/researchers")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ Retrieved {len(data)} public researchers")
        if len(data) > 0:
            print(f"   ℹ️ Sample: {data[0]['full_name']} - {data[0].get('wp_name', 'No WP')}")
    else:
        print(f"   ❌ Failed: {resp.status_code}")

    # Test 6: Public Graph
    print("\n[8] Testing Public Graph...")
    resp = requests.get(f"{BASE_URL}/public/graph")
    if resp.status_code == 200:
        data = resp.json()
        nodes = len(data.get('nodes', []))
        edges = len(data.get('edges', []))
        print(f"   ✅ Graph Data: {nodes} nodes, {edges} edges")
    else:
        print(f"   ❌ Failed: {resp.status_code}")

    # Test 7: Catalogs (WPs)
    print("\n[9] Testing Catalogs (WPs)...")
    resp = requests.get(f"{BASE_URL}/catalogs/working-packages")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ Retrieved {len(data)} WPs")
        if len(data) > 0:
            print(f"   ℹ️ Sample: {data[0]['name']} ({data[0]['color']})")
    else:
        print(f"   ❌ Failed: {resp.status_code}")

    # Test 8: Export Excel
    print("\n[10] Testing Export Excel...")
    resp = requests.get(f"{BASE_URL}/reports/compliance/export", headers=headers)
    if resp.status_code == 200:
        content_type = resp.headers.get('content-type', '')
        content_len = len(resp.content)
        print(f"   ✅ Export successful ({content_len} bytes)")
        print(f"   ℹ️ Content-Type: {content_type}")
    else:
        print(f"   ❌ Failed: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    print("🚀 Starting API Verification Script")
    print("===================================")
    
    if test_health():
        token = get_token()
        if token:
            test_endpoints(token)
    
    print("\n===================================")
    print("🏁 Verification Complete")

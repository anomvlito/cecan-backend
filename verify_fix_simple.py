
import requests
import sys
import json

BASE_URL = "http://localhost:8000/api"

def get_token(email, password):
    response = requests.post(f"{BASE_URL}/auth/login", data={"username": email, "password": password})
    if response.status_code != 200:
        print(f"Failed to login {email}: {response.text}")
        return None
    return response.json()["access_token"]

def verify_permission_fix():
    print("🧪 Verifying Permission Fix...")
    
    # 1. Login as PI
    pi_token = get_token("pi@cecan.cl", "pi123")
    if not pi_token:
        print("❌ Could not login as PI")
        return

    print("✅ PI Logged in")

    # 2. Key Step: Find a researcher to assign
    # We'll use a hardcoded researcher if we can't query, or just assume ID 3 exists as per previous context
    # Let's try to list users if possible, or just use 3
    researcher_id = 3
    
    # 3. Create Project
    # Let's try to list projects and use the first one
    headers_pi = {"Authorization": f"Bearer {pi_token}"}
    projects_resp = requests.get(f"{BASE_URL}/scientific-projects", headers=headers_pi)
    if projects_resp.status_code != 200:
        print(f"❌ Failed to list projects: {projects_resp.text}")
        return
        
    projects = projects_resp.json()
    if not projects:
        print("❌ No projects found")
        return
        
    project_id = projects[0]['id']
    print(f"Using Project ID: {project_id}")

    # 4. Create Activity with Assignment
    activity_data = {
        "description": "Test Permission Activity",
        "start_month": "2025-06-01",
        "end_month": "2025-07-01",
        "assigned_user_ids": [researcher_id]
    }
    
    act_resp = requests.post(f"{BASE_URL}/scientific-projects/{project_id}/activities", 
                           headers=headers_pi, json=activity_data)
                           
    if act_resp.status_code != 200:
        print(f"❌ Failed to create activity: {act_resp.text}")
        return
        
    activity_id = act_resp.json()['id']
    print(f"✅ Created Activity {activity_id} assigned to user {researcher_id}")

    # 5. Login as Researcher
    # Assuming user 3 has email 'researcher@cecan.cl' password 'res123' based on previous context 
    # (previous turn mentioned: "Login como researcher@cecan.cl / res123")
    res_token = get_token("researcher@cecan.cl", "res123")
    if not res_token:
         # Try creating a token for user 3 if possible? No, can't easily.
         # Let's try to fallback to another user if this fails?
         print("❌ Could not login as Researcher. Verification blocked.")
         return

    print("✅ Researcher Logged in")
    
    # 6. Attempt Update as Researcher
    headers_res = {"Authorization": f"Bearer {res_token}"}
    update_data = {
        "progress": 0.5,
        "status": "in_progress"
    }
    
    print(f"Attempting to update Activity {activity_id} as Researcher...")
    update_resp = requests.put(f"{BASE_URL}/scientific-projects/{project_id}/activities/{activity_id}",
                             headers=headers_res, json=update_data)
                             
    if update_resp.status_code == 200:
        print("✅ SUCCESS: Researcher updated the activity!")
        print(json.dumps(update_resp.json(), indent=2))
    else:
        print(f"❌ FAILED: Researcher update failed with {update_resp.status_code}")
        print(update_resp.text)

if __name__ == "__main__":
    verify_permission_fix()

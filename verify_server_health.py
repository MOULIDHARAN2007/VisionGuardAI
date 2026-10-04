import urllib.request
import json

def test_endpoints():
    endpoints = [
        ("Root Page", "http://127.0.0.1:8000/"),
        ("Login Page (127.0.0.1)", "http://127.0.0.1:8000/login"),
        ("Login Page (localhost)", "http://localhost:8000/login"),
        ("Health Endpoint", "http://127.0.0.1:8000/api/health"),
    ]
    
    for name, url in endpoints:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as res:
            body = res.read()
            print(f"[{name}] {url} -> HTTP {res.status} (bytes: {len(body)})")
            if "api/health" in url:
                parsed = json.loads(body)
                print(f"  Health status: {parsed.get('status')}")
                print(f"  Device: {parsed.get('device')}")
                print(f"  Loaded Models: {list(parsed.get('models', {}).keys())}")

def test_login_api():
    login_url = "http://127.0.0.1:8000/api/auth/login"
    accounts = [
        ("ADMIN", "admin@visionguard.ai", "AdminSecurePass123!"),
        ("CITIZEN", "user@visionguard.ai", "UserPassword123!"),
        ("WORKER", "worker@visionguard.ai", "WorkerPassword123!"),
        ("SUPERVISOR", "supervisor@visionguard.ai", "SupervisorPassword123!")
    ]
    
    for role_name, email, password in accounts:
        payload = json.dumps({"email": email, "password": password}).encode("utf-8")
        req = urllib.request.Request(
            login_url,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            res_data = json.loads(res.read())
            print(f"[LOGIN API - {role_name}] {email} -> HTTP {res.status}, Role: {res_data.get('role')}, Token Acquired: {bool(res_data.get('access_token'))}")

if __name__ == "__main__":
    print("--- Testing Server Endpoints ---")
    test_endpoints()
    print("\n--- Testing Login Authentication API ---")
    test_login_api()
    print("\nAll verifications successful!")

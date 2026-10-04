"""
VisionGuard AI 2.0 - Comprehensive Login Page & Responsive Verification Test Suite
"""
import urllib.request
import json
import re

def test_login_page_redesign():
    print("=" * 70)
    print("VISIONGUARD AI 2.0 LOGIN REDESIGN AUDIT & RESPONSIVE VERIFICATION")
    print("=" * 70)

    # 1. Fetch live index.html and style.css
    with urllib.request.urlopen("http://127.0.0.1:8000/") as response:
        html = response.read().decode("utf-8")
    
    with urllib.request.urlopen("http://127.0.0.1:8000/static/style.css") as response:
        css = response.read().decode("utf-8")

    with urllib.request.urlopen("http://127.0.0.1:8000/static/app.js") as response:
        js = response.read().decode("utf-8")

    # 2. Check HTML Elements & Branding
    html_checks = [
        ("Auth View Container", 'id="view_auth"'),
        ("Auth Page Container", 'class="auth-page-container"'),
        ("Auth Layout Wrapper", 'class="auth-layout-wrapper"'),
        ("Left Visual Pane", 'class="auth-visual-pane"'),
        ("Hero Tag Header", 'AI &bull; SMART CITIES &bull; SAFE ROADS'),
        ("Main Title", 'VISIONGUARD <span class="ai-highlight">AI 2.0</span>'),
        ("Hero Tagline", 'Detect &bull; Report &bull; Resolve &bull; Safer Tomorrow'),
        ("Hero Description", 'AI-powered road infrastructure monitoring for cleaner, safer and smarter cities.'),
        ("Scene Canvas", 'class="auth-scene-canvas"'),
        ("Hero Image Asset", 'src="/static/hero_smart_city.jpg"'),
        ("CCTV Scanner Overlay", 'class="cctv-scanner-overlay"'),
        ("Pothole AI Box (92%)", 'Pothole 92%'),
        ("Traffic Signal AI Box (98%)", 'Traffic Signal 98%'),
        ("Speed Sign AI Box (95%)", 'Speed Sign 95%'),
        ("Bottom Scene Badge", 'Cleaner Roads. Greener Cities. Better Lives.'),
        ("Center Card Pane", 'class="auth-card-pane"'),
        ("Login Card Modal", 'class="auth-card-modal"'),
        ("Card Brand Title", 'VISIONGUARD AI 2.0'),
        ("Email Input", 'id="authEmail"'),
        ("Password Input", 'id="authPassword"'),
        ("Remember Me Checkbox", 'id="rememberMeCheckbox"'),
        ("Forgot Password Link", 'Forgot Password?'),
        ("Sign In Button", 'id="btnLoginSubmit"'),
        ("Create Account Link", 'id="createAccountLink"'),
        ("Right Features Pane", 'class="auth-features-pane"'),
        ("Quote Text", 'Together<br>for a Safer<br>Tomorrow"'),
        ("Feature 1: AI Detection", 'AI Detection'),
        ("Feature 2: Report Instantly", 'Report Instantly'),
        ("Feature 3: Real-time Monitoring", 'Real-time Monitoring'),
        ("Feature 4: Better Communities", 'Better Communities'),
        ("Skyline Motif & Text", 'INFRASTRUCTURE'),
    ]

    all_html_passed = True
    print("\n--- HTML & UI REFERENCE DESIGN CHECKS ---")
    for name, pattern in html_checks:
        if pattern in html:
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name} (missing pattern: '{pattern}')")
            all_html_passed = False

    # 3. CSS Responsive Rules & Breakpoint Verification
    css_checks = [
        ("Desktop 3-column Layout (1.05fr / 0.85fr / 0.65fr)", 'grid-template-columns: minmax(0, 1.05fr) minmax(420px, 0.85fr) minmax(260px, 0.65fr)'),
        ("Centered Max Width Container", 'width: min(100% - 48px, 1600px)'),
        ("Responsive Padding Inline", 'padding-inline: clamp(20px, 3.5vw, 64px)'),
        ("Scene Canvas Aspect Ratio 16/9", 'aspect-ratio: 16 / 9'),
        ("Scene Canvas Max Width", 'max-width: 620px'),
        ("Pothole Glow Box", '.ai-pothole-box'),
        ("Traffic Signal Glow Box", '.ai-signal-box'),
        ("Speed Sign Glow Box", '.ai-speedsign-box'),
        ("Card Border Radius & Shadow", '.auth-card-modal'),
        ("Input Icon Positioning", '.input-leading-icon'),
        ("Laptop Breakpoint (max-width: 1366px)", '@media (max-width: 1366px)'),
        ("Laptop 2-column Breakpoint (max-width: 1199px)", '@media (max-width: 1199px)'),
        ("Tablet Portrait Breakpoint (max-width: 1023px)", '@media (max-width: 1023px)'),
        ("Mobile Breakpoint (max-width: 767px)", '@media (max-width: 767px)'),
        ("Small Mobile Breakpoint (max-width: 360px)", '@media (max-width: 360px)'),
        ("No Horizontal Overflow Rules", 'overflow-x: hidden'),
    ]

    all_css_passed = True
    print("\n--- CSS RESPONSIVE & BREAKPOINT CHECKS ---")
    for name, pattern in css_checks:
        if pattern in css:
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name} (missing pattern: '{pattern}')")
            all_css_passed = False

    # 4. JS Authentication & Modal Functionality
    js_checks = [
        ("handleLoginSubmit Function", 'async function handleLoginSubmit(event)'),
        ("openCreateAccountModal Function", 'function openCreateAccountModal(e)'),
        ("selectRegistrationType Function", 'function selectRegistrationType(role)'),
        ("Token & Role Persistence", 'localStorage.setItem("vg_token", authToken)'),
        ("Role Based Redirection", 'navigateHome()'),
    ]

    all_js_passed = True
    print("\n--- JAVASCRIPT & MODAL HOOK CHECKS ---")
    for name, pattern in js_checks:
        if pattern in js:
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name} (missing pattern: '{pattern}')")
            all_js_passed = False

    # 5. Live Authentication API Verification for All 4 Roles
    print("\n--- AUTHENTICATION API & ROLE DETECTION CHECKS ---")
    import uuid
    uid = uuid.uuid4().hex[:6]
    test_creds = [
        ("CITIZEN", f"cit_{uid}@visionguard.ai", "Pass1234!", "USER", "CITIZEN"),
        ("WORKER", f"wrk_{uid}@visionguard.ai", "Pass1234!", "WORKER", "WORKER"),
        ("SUPERVISOR", f"sup_{uid}@visionguard.ai", "Pass1234!", "SUPERVISOR", "SUPERVISOR"),
        ("ADMIN", "admin@visionguard.ai", "AdminPassword123!", "ADMIN", "ADMIN"),
    ]

    all_auth_passed = True
    for role_label, email, password, expected_role, reg_type in test_creds:
        # Register citizen/worker/supervisor if needed
        if reg_type == "CITIZEN":
            try:
                reg_req = urllib.request.Request(
                    "http://127.0.0.1:8000/api/auth/register",
                    data=json.dumps({
                        "full_name": "Test Citizen",
                        "email": email,
                        "password": password,
                        "phone": "+1-555-0199"
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(reg_req)
            except Exception as e:
                pass
        elif reg_type in ("WORKER", "SUPERVISOR"):
            endpoint = "/api/auth/register-worker" if reg_type == "WORKER" else "/api/auth/register-supervisor"
            payload = {
                "full_name": f"Test {role_label}",
                "email": email,
                "password": password,
                "phone": "+1-555-0199",
                "employee_id": f"EMP-{uid}",
                "department": "Road Maintenance",
                "zone": "North Zone"
            }
            if reg_type == "WORKER":
                payload["skills"] = "Pothole Repair"
            else:
                payload["specialization"] = "Road Safety"
            try:
                reg_req = urllib.request.Request(
                    f"http://127.0.0.1:8000{endpoint}",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(reg_req)
            except Exception as e:
                pass

        # If Worker or Supervisor, use Admin to approve them first
        if reg_type in ("WORKER", "SUPERVISOR"):
            try:
                # Login as admin to get token
                adm_req = urllib.request.Request(
                    "http://127.0.0.1:8000/api/auth/login",
                    data=json.dumps({"email": "admin@visionguard.ai", "password": "AdminPassword123!"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(adm_req) as adm_resp:
                    adm_token = json.loads(adm_resp.read().decode("utf-8"))["access_token"]
                
                # Fetch pending and approve
                list_ep = "/api/admin/worker-approvals" if reg_type == "WORKER" else "/api/admin/supervisor-approvals"
                get_req = urllib.request.Request(
                    f"http://127.0.0.1:8000{list_ep}",
                    headers={"Authorization": f"Bearer {adm_token}"}
                )
                with urllib.request.urlopen(get_req) as list_resp:
                    items = json.loads(list_resp.read().decode("utf-8"))
                    target = next((item for item in items if item.get("email") == email), None)
                    if target:
                        t_id = target.get("worker_id") or target.get("supervisor_id") or target.get("id")
                        approve_ep = f"/api/admin/worker-approvals/{t_id}/approve" if reg_type == "WORKER" else f"/api/admin/supervisor-approvals/{t_id}/approve"
                        app_req = urllib.request.Request(
                            f"http://127.0.0.1:8000{approve_ep}",
                            data=b"{}",
                            headers={"Authorization": f"Bearer {adm_token}", "Content-Type": "application/json"}
                        )
                        urllib.request.urlopen(app_req)
            except Exception as e:
                print(f"  [Note] Approval step exception: {e}")

        # Now test login
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8000/api/auth/login",
                data=json.dumps({"email": email, "password": password}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data.get("access_token") is not None, "Missing access_token"
                assert data.get("role") == expected_role, f"Expected role {expected_role}, got {data.get('role')}"
                print(f"  [PASS] {role_label} Login -> Role: {data.get('role')} (Token received)")
        except Exception as e:
            print(f"  [FAIL] {role_label} Login -> Error: {e}")
            all_auth_passed = False

    # Test Invalid Login Rejection
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/auth/login",
            data=json.dumps({"email": "invalid@visionguard.gov", "password": "wrongpassword"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req)
        print("  [FAIL] Invalid Login was accepted when it should be rejected!")
        all_auth_passed = False
    except urllib.error.HTTPError as e:
        if e.code in (400, 401):
            print(f"  [PASS] Invalid Login Rejected Correctly (HTTP {e.code})")
        else:
            print(f"  [FAIL] Unexpected HTTP error {e.code}")
            all_auth_passed = False

    print("\n" + "=" * 70)
    if all_html_passed and all_css_passed and all_js_passed and all_auth_passed:
        print("ALL LOGIN REDESIGN AND RESPONSIVE CRITERIA PASSED!")
    else:
        print("SOME CHECKS FAILED - PLEASE REVIEW LOGS")
    print("=" * 70)

if __name__ == "__main__":
    test_login_page_redesign()

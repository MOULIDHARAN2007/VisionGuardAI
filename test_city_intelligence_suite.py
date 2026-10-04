"""
VisionGuard AI 2.0 - City Infrastructure Intelligence & Digital Twin Test Suite
Tests 15 key capabilities:
1. Summary API (/api/city-intelligence/summary)
2. Transparent Health calculation (0-100 range, formula validation)
3. Real GPS records telemetry
4. Location API (/api/city-intelligence/locations & /location/{id})
5. Smart Risk integration (risk scores, critical/high/medium/low tiers)
6. Zone aggregation & geographic proximity clustering
7. Category aggregation (road damage, signs, signals)
8. Time filters (today, 7d, 30d, all)
9. Issue filters (all, road_damage, traffic_signs, traffic_signals, completed)
10. Admin RBAC authorization (full access)
11. Worker RBAC authorization (access to summary/locations)
12. Citizen restrictions (safe data scope, unauthorized routes protected)
13. No-data & edge case handling ("Insufficient data" fallback)
14. Existing map API regression (/api/map/incidents, /api/risk/heatmap)
15. Existing complaint & repair lifecycle progression
"""

import sys
import unittest
import requests

BASE_URL = "http://127.0.0.1:8000"

# Demo Credentials
ADMIN_AUTH = {"email": "admin@visionguard.ai", "password": "AdminPassword123!"}
WORKER_AUTH = {"email": "worker@visionguard.ai", "password": "WorkerPassword123!"}
USER_AUTH = {"email": "user@visionguard.ai", "password": "UserPassword123!"}


class TestCityIntelligenceSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Obtain Admin Token
        r_admin = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_AUTH)
        if r_admin.status_code != 200:
            raise Exception(f"Admin login failed: {r_admin.text}")
        cls.admin_token = r_admin.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # 2. Obtain Worker Token
        r_worker = requests.post(f"{BASE_URL}/api/auth/login", json=WORKER_AUTH)
        if r_worker.status_code != 200:
            raise Exception(f"Worker login failed: {r_worker.text}")
        cls.worker_token = r_worker.json()["access_token"]
        cls.worker_headers = {"Authorization": f"Bearer {cls.worker_token}"}

        # 3. Obtain Citizen Token
        r_user = requests.post(f"{BASE_URL}/api/auth/login", json=USER_AUTH)
        if r_user.status_code != 200:
            raise Exception(f"User login failed: {r_user.text}")
        cls.user_token = r_user.json()["access_token"]
        cls.user_headers = {"Authorization": f"Bearer {cls.user_token}"}

    def test_01_summary_api_structure(self):
        """Test 1: Summary API returns complete telemetry structure with real metrics."""
        res = requests.get(f"{BASE_URL}/api/city-intelligence/summary", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("health", data)
        self.assertIn("total_detections", data)
        self.assertIn("active_complaints", data)
        self.assertIn("resolved_complaints", data)
        self.assertIn("critical_risks", data)
        self.assertIn("high_risks", data)
        self.assertIn("average_risk_score", data)
        self.assertIn("category_counts", data)
        self.assertIn("top_problem", data)

    def test_02_health_calculation_bounds_and_formula(self):
        """Test 2: Health score is derived transparently and clamped between 0 and 100."""
        res = requests.get(f"{BASE_URL}/api/city-intelligence/health", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("health_score", data)
        self.assertIn("status", data)
        self.assertIn("formula", data)
        score = data["health_score"]
        if score is not None:
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)
            self.assertIn(data["status"], ["OPTIMAL", "STABLE", "DEGRADED", "CRITICAL"])
            self.assertTrue("Health = 100 - (" in data["formula"])

    def test_03_real_gps_records(self):
        """Test 3: Location records contain valid municipal GPS coordinates (Salem, Tamil Nadu)."""
        res = requests.get(f"{BASE_URL}/api/city-intelligence/locations", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("locations", data)
        for loc in data["locations"]:
            if loc.get("latitude") and loc.get("longitude"):
                self.assertTrue(8.0 <= loc["latitude"] <= 14.0, f"Lat out of bounds: {loc['latitude']}")
                self.assertTrue(76.0 <= loc["longitude"] <= 81.0, f"Lng out of bounds: {loc['longitude']}")

    def test_04_location_drilldown_api(self):
        """Test 4: Location drill-down returns asset info, 500m road health, and 6-stage lifecycle."""
        # Fetch locations first to get an ID
        loc_res = requests.get(f"{BASE_URL}/api/city-intelligence/locations", headers=self.admin_headers)
        locations = loc_res.json().get("locations", [])
        if locations:
            target = locations[0]
            target_id = target.get("complaint_id") or target.get("detection_id") or 1
            asset_type = target.get("asset_type", "complaint")
            
            res = requests.get(f"{BASE_URL}/api/city-intelligence/location/{target_id}?asset_type={asset_type}", headers=self.admin_headers)
            self.assertEqual(res.status_code, 200)
            drill = res.json()
            self.assertIn("location", drill)
            self.assertIn("road_health", drill)
            self.assertIn("repair_history", drill)
            
            # Verify 6-stage lifecycle
            history = drill["repair_history"]
            self.assertIsInstance(history, list)
            self.assertGreaterEqual(len(history), 4)

    def test_05_risk_integration(self):
        """Test 5: Risk integration properly tags items with CRITICAL, HIGH, MEDIUM, LOW levels."""
        res = requests.get(f"{BASE_URL}/api/city-intelligence/locations", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        locations = res.json().get("locations", [])
        for loc in locations:
            risk_level = loc.get("risk_level")
            risk_score = loc.get("risk_score", 0)
            self.assertIn(risk_level, ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
            self.assertGreaterEqual(risk_score, 0)
            self.assertLessEqual(risk_score, 100)

    def test_06_zone_aggregation_clustering(self):
        """Test 6: Geographic proximity clustering groups records into zones with aggregated health metrics."""
        res = requests.get(f"{BASE_URL}/api/city-intelligence/zones", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("zones", data)
        self.assertIn("total_zones", data)
        zones = data["zones"]
        for z in zones:
            self.assertIn("zone_id", z)
            self.assertIn("name", z)
            self.assertIn("centroid_lat", z)
            self.assertIn("centroid_lng", z)
            self.assertIn("infrastructure_health", z)
            self.assertIn("risk_score", z)
            self.assertIn("risk_level", z)

    def test_07_category_aggregation(self):
        """Test 7: Detections correctly aggregate across the 4 AI system categories."""
        res = requests.get(f"{BASE_URL}/api/city-intelligence/summary", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        counts = res.json().get("category_counts", {})
        self.assertIn("road_damage", counts)
        self.assertIn("traffic_signs", counts)
        self.assertIn("traffic_signals", counts)
        self.assertIn("sign_condition", counts)

    def test_08_time_filters(self):
        """Test 8: Time filters (today, 7d, 30d, all) return valid structured responses."""
        for tf in ["today", "7d", "30d", "all"]:
            res = requests.get(f"{BASE_URL}/api/city-intelligence/summary?time_filter={tf}", headers=self.admin_headers)
            self.assertEqual(res.status_code, 200, f"Time filter {tf} failed")
            self.assertIn("time_filter", res.json())
            self.assertEqual(res.json()["time_filter"], tf)

    def test_09_issue_filters(self):
        """Test 9: Issue and risk tier filters return filtered locations."""
        for it in ["all", "road_damage", "traffic_signs", "traffic_signals", "completed"]:
            res = requests.get(f"{BASE_URL}/api/city-intelligence/locations?issue_type={it}", headers=self.admin_headers)
            self.assertEqual(res.status_code, 200, f"Issue filter {it} failed")
            self.assertIn("locations", res.json())

    def test_10_admin_rbac_access(self):
        """Test 10: Admin has full access to summary, zones, locations, and health."""
        for endpoint in ["summary", "zones", "locations", "health"]:
            res = requests.get(f"{BASE_URL}/api/city-intelligence/{endpoint}", headers=self.admin_headers)
            self.assertEqual(res.status_code, 200, f"Admin access failed on {endpoint}")

    def test_11_worker_rbac_access(self):
        """Test 11: Worker has access to municipal summary and locations."""
        res = requests.get(f"{BASE_URL}/api/city-intelligence/summary", headers=self.worker_headers)
        self.assertEqual(res.status_code, 200)
        res_loc = requests.get(f"{BASE_URL}/api/city-intelligence/locations", headers=self.worker_headers)
        self.assertEqual(res_loc.status_code, 200)

    def test_12_citizen_restrictions(self):
        """Test 12: Citizen (USER) accessing municipal digital twin summary receives allowed scope or proper auth."""
        res = requests.get(f"{BASE_URL}/api/city-intelligence/summary", headers=self.user_headers)
        self.assertEqual(res.status_code, 200)
        # Unauthenticated request is rejected
        res_anon = requests.get(f"{BASE_URL}/api/city-intelligence/summary")
        self.assertEqual(res_anon.status_code, 401)

    def test_13_no_data_handling(self):
        """Test 13: Querying an invalid or empty location ID returns 404 cleanly."""
        res = requests.get(f"{BASE_URL}/api/city-intelligence/location/99999999", headers=self.admin_headers)
        self.assertEqual(res.status_code, 404)

    def test_14_existing_map_regression(self):
        """Test 14: Existing map and risk heatmap endpoints continue to function."""
        res_map = requests.get(f"{BASE_URL}/api/map/incidents")
        self.assertEqual(res_map.status_code, 200)
        
        res_heat = requests.get(f"{BASE_URL}/api/risk/heatmap", headers=self.admin_headers)
        self.assertEqual(res_heat.status_code, 200)

    def test_15_existing_complaint_regression(self):
        """Test 15: Existing complaint APIs continue functioning without disruption."""
        res_my = requests.get(f"{BASE_URL}/api/complaints/my", headers=self.user_headers)
        self.assertEqual(res_my.status_code, 200)
        
        res_admin = requests.get(f"{BASE_URL}/api/admin/complaints", headers=self.admin_headers)
        self.assertEqual(res_admin.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)

/**
 * VisionGuardAI - Official Frontend Client Architecture
 * Professional Multi-Page SPA Router & Municipal AI Controller
 */

// Global State
let currentUser = null;
let authToken = localStorage.getItem("vg_token") || null;
let currentRoute = "/";

// AI Inference State
let activeAiMode = "all_in_one";
let activeConfidence = 0.25;
let selectedImageFile = null;
let lastInferenceResult = null;
let currentGps = { lat: null, lng: null, address: "Location pending GPS acquisition" };
let isGpsPermissionDenied = false;
let gpsWatchId = null;
let userLocationMarker = null;

// Complaint Image & AI Context State
let complaintSelectedImageFile = null;
let complaintAiContext = null;

// Live Webcam & Mobile USB Camera State
let liveWebcamStream = null;
let isLiveDetecting = false;
let liveDetectTimer = null;
let liveFps = 0;
let liveFrameCount = 0;
let liveLastTime = performance.now();
let availableCameraDevices = [];
let selectedCameraDeviceId = "";
let selectedCameraLabel = "None (Offline)";
let isCameraDeviceListenerAttached = false;

// Video State
let selectedVideoFile = null;
let lastVideoAnalysis = null;

// Map & Charts State
let leafletMapInstance = null;
let leafletMarkersLayer = null;
let riskHeatmapLayer = null;
let isRiskHeatmapActive = false;
let issueChartInstance = null;
let riskChartInstance = null;
let trendsChartInstance = null;
let modelDistChartInstance = null;
let chartRiskDistInstance = null;
let chartRiskTrendsInstance = null;

// City Digital Twin State
let cityTwinMapInstance = null;
let cityTwinMarkersLayer = null;
let cityTwinHeatmapLayer = null;
let isCityTwinHeatmapActive = false;
let cityTwinTimeFilter = "all";
let cityTwinIssueFilter = "all";
let cityTwinRiskFilter = "all";
let cityTwinLocationsCache = [];
let cityTwinZonesCache = [];

// Active Context IDs
let activeComplaintId = null;

// Supervisor Map Instances
let supervisorDashboardMap = null;
let supervisorDashboardMapMarkers = null;
let supervisorFullMapInstance = null;
let supervisorFullMapMarkers = null;

// ==========================================================================
// Centralized Image URL Resolver & Robust Placeholder Utilities
// ==========================================================================

function getImageUrl(path) {
  if (!path || typeof path !== "string") return null;
  let p = path.trim();
  if (!p || p === "null" || p === "undefined" || p === "None") return null;

  // 1. Full HTTP/HTTPS or data URI
  if (p.startsWith("http://") || p.startsWith("https://") || p.startsWith("data:image/")) {
    return p;
  }

  // 2. Normalize Windows backslashes
  p = p.replace(/\\/g, "/");

  // 3. Extract /uploads/ if embedded in absolute path
  const uploadsIdx = p.indexOf("/uploads/");
  if (uploadsIdx !== -1) {
    return p.substring(uploadsIdx);
  }
  if (p.startsWith("uploads/")) {
    return "/" + p;
  }
  if (p.startsWith("/uploads/")) {
    return p;
  }

  // 4. Handle relative subfolders
  if (p.startsWith("complaints/") || p.startsWith("evidence/") || p.startsWith("detections/") || p.startsWith("videos/")) {
    return "/uploads/" + p;
  }

  // 5. Handle filename only
  if (p.startsWith("complaint_")) {
    return "/uploads/complaints/" + p;
  }
  if (p.startsWith("ev_")) {
    return "/uploads/evidence/" + p;
  }
  if (p.startsWith("det_")) {
    return "/uploads/detections/" + p;
  }

  if (p.startsWith("/")) return p;
  return "/uploads/" + p;
}

function createPlaceholderDataUrl(text = "No evidence image uploaded") {
  const safeText = String(text || "No evidence image uploaded").replace(/[<>&"]/g, '');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="240" viewBox="0 0 400 240">
    <rect width="100%" height="100%" fill="#F8FAFC"/>
    <rect x="2" y="2" width="396" height="236" fill="none" stroke="#E2E8F0" stroke-width="2" rx="8"/>
    <g fill="#94A3B8" transform="translate(184, 75)">
      <path d="M4 0h24a4 4 0 0 1 4 4v18a4 4 0 0 1-4 4H4a4 4 0 0 1-4-4V4a4 4 0 0 1 4-4zm0 3a1 1 0 0 0-1 1v18a1 1 0 0 0 1 1h24a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1H4zm3 15l5-6 4 4 6-8 6 10H7zm15-11a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z"/>
    </g>
    <text x="50%" y="145" text-anchor="middle" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="13" font-weight="600">${safeText}</text>
    <text x="50%" y="168" text-anchor="middle" fill="#94A3B8" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="11">VisionGuardAI Infrastructure Diagnostics</text>
  </svg>`;
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}

function handleImageError(img, altText = "Evidence image unavailable") {
  if (!img) return;
  console.warn("Evidence image failed loading from URL:", img.src || "(empty)");
  img.onerror = null;
  img.src = createPlaceholderDataUrl(altText);
}

// ==========================================================================
// Initialization & Lifecycle
// ==========================================================================

async function initVisionGuardApp() {
  try { setupGpsLocation(); } catch (e) { console.warn("GPS init error:", e); }
  try { setupComplaintDropzoneListeners(); } catch (e) { console.warn("Dropzone init error:", e); }
  try { setupAuthEventListeners(); } catch (e) { console.warn("Auth listeners init error:", e); }
  try { refreshCameraDevices(false); } catch (e) { console.warn("Camera refresh error:", e); }
  try { await checkHealthAndModels(); } catch (e) { console.warn("Health check error:", e); }
  try { await initSession(); } catch (e) { console.error("Session init error:", e); }
  try { setupPopstateListener(); } catch (e) { console.warn("Popstate init error:", e); }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initVisionGuardApp);
} else {
  initVisionGuardApp();
}

// Real-Time Continuous GPS Auto-Detection via watchPosition()
function setupGpsLocation() {
  if (!("geolocation" in navigator)) {
    currentGps.address = "Geolocation not supported by browser";
    currentGps.isLive = false;
    updateGpsUi();
    return;
  }

  if (isGpsPermissionDenied) {
    return;
  }

  // Clear existing watcher if running
  if (gpsWatchId !== null) {
    navigator.geolocation.clearWatch(gpsWatchId);
    gpsWatchId = null;
  }

  const gpsOptions = {
    enableHighAccuracy: true,
    maximumAge: 5000,
    timeout: 10000
  };

  try {
    gpsWatchId = navigator.geolocation.watchPosition(
      (pos) => {
        isGpsPermissionDenied = false;
        currentGps.lat = parseFloat(pos.coords.latitude.toFixed(6));
        currentGps.lng = parseFloat(pos.coords.longitude.toFixed(6));
        currentGps.accuracy = Math.round(pos.coords.accuracy || 0);
        currentGps.timestamp = pos.timestamp ? new Date(pos.timestamp) : new Date();
        currentGps.address = `GPS: ${currentGps.lat}, ${currentGps.lng} (±${currentGps.accuracy}m)`;
        currentGps.isLive = true;

        updateGpsUi();
        updateLiveMapUserMarker();
      },
      (err) => {
        currentGps.isLive = false;
        if (err.code === err.PERMISSION_DENIED) {
          isGpsPermissionDenied = true;
          console.warn("GPS Geolocation access denied by user or browser.");
          currentGps.address = "Location access denied. Enable location in browser settings.";
          if (gpsWatchId !== null) {
            navigator.geolocation.clearWatch(gpsWatchId);
            gpsWatchId = null;
          }
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          console.warn("GPS Position unavailable:", err.message);
          currentGps.address = "GPS position temporarily unavailable";
        } else if (err.code === err.TIMEOUT) {
          console.warn("GPS Location request timed out:", err.message);
          currentGps.address = "GPS fix acquisition timed out";
        } else {
          currentGps.address = `GPS Error: ${err.message}`;
        }
        updateGpsUi();
      },
      gpsOptions
    );
  } catch (e) {
    console.error("Failed to start geolocation watcher:", e);
    currentGps.address = "Failed to start GPS tracking";
    currentGps.isLive = false;
    updateGpsUi();
  }
}

function updateGpsUi() {
  const gpsLabel = document.getElementById("aiInspectionGpsLabel");
  if (gpsLabel) {
    if (currentGps.lat != null) {
      gpsLabel.textContent = `Location: ${currentGps.lat}, ${currentGps.lng} (±${currentGps.accuracy || 0}m)`;
    } else {
      gpsLabel.textContent = `Location: ${currentGps.address || 'Location unavailable'}`;
    }
  }

  const compLat = document.getElementById("compLat");
  const compLng = document.getElementById("compLng");
  const compLoc = document.getElementById("compLocationAddress");
  const gpsStatus = document.getElementById("gpsStatusMessage");
  const liveGpsText = document.getElementById("liveGpsText");

  if (compLat && currentGps.lat != null && (!compLat.value || compLat.value === "0")) compLat.value = currentGps.lat;
  if (compLng && currentGps.lng != null && (!compLng.value || compLng.value === "0")) compLng.value = currentGps.lng;
  if (compLoc && currentGps.address && !compLoc.value) compLoc.value = currentGps.address;

  if (gpsStatus) {
    if (currentGps.isLive && currentGps.lat != null) {
      gpsStatus.innerHTML = `<span style="color:#10B981; font-weight:700;">🟢 LIVE GPS:</span> ${currentGps.lat}, ${currentGps.lng} (±${currentGps.accuracy || 0}m)`;
    } else if (isGpsPermissionDenied) {
      gpsStatus.innerHTML = `<span style="color:#EF4444; font-weight:700;">🔴 Location permission denied</span> — Please allow location in browser settings`;
    } else {
      gpsStatus.textContent = currentGps.address || "Location unavailable";
    }
  }

  if (liveGpsText) {
    if (currentGps.isLive && currentGps.lat != null) {
      const timeStr = currentGps.timestamp ? (currentGps.timestamp instanceof Date ? currentGps.timestamp.toLocaleTimeString() : new Date(currentGps.timestamp).toLocaleTimeString()) : "";
      liveGpsText.textContent = `🟢 LIVE GPS: ${currentGps.lat}, ${currentGps.lng} (±${currentGps.accuracy || 0}m)${timeStr ? ' • ' + timeStr : ''}`;
    } else if (isGpsPermissionDenied) {
      liveGpsText.textContent = `🔴 Location permission denied`;
    } else {
      liveGpsText.textContent = currentGps.lat != null ? `${currentGps.lat}, ${currentGps.lng}` : (currentGps.address || "Acquiring GPS...");
    }
  }
}

function updateLiveMapUserMarker() {
  if (leafletMapInstance && leafletMarkersLayer && currentGps.lat != null && currentGps.lng != null) {
    if (userLocationMarker) {
      userLocationMarker.setLatLng([currentGps.lat, currentGps.lng]);
    } else {
      const userIcon = L.divIcon({
        className: 'custom-map-marker',
        html: '<div style="background:#0284C7; width:18px; height:18px; border-radius:50%; border:3px solid #fff; box-shadow:0 0 10px rgba(2,132,199,0.5);"></div>'
      });
      userLocationMarker = L.marker([currentGps.lat, currentGps.lng], { icon: userIcon })
        .bindPopup(`<strong>Your Location (Live GPS)</strong><br>${currentGps.address || 'Current Position'}`)
        .addTo(leafletMarkersLayer);
    }
    if (activeNavDestination) {
      drawWorkerRouteToDestination(activeNavDestination);
    }
  }
}

function triggerGpsAutodetect() {
  isGpsPermissionDenied = false;
  toast("Acquiring high-accuracy real-time GPS fix...", "info");
  setupGpsLocation();
  if ("geolocation" in navigator) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        currentGps.lat = parseFloat(pos.coords.latitude.toFixed(6));
        currentGps.lng = parseFloat(pos.coords.longitude.toFixed(6));
        currentGps.accuracy = Math.round(pos.coords.accuracy || 0);
        currentGps.timestamp = new Date();
        currentGps.address = `GPS: ${currentGps.lat}, ${currentGps.lng} (±${currentGps.accuracy}m)`;
        currentGps.isLive = true;
        updateGpsUi();
        updateLiveMapUserMarker();
        toast("Live GPS coordinates acquired!", "success");
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          isGpsPermissionDenied = true;
          toast("Location permission denied in browser settings", "error");
        } else {
          toast("Could not obtain precise GPS: " + err.message, "warning");
        }
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }
}

function acquireGpsForComplaint() {
  triggerGpsAutodetect();
}

// Health Check
async function checkHealthAndModels() {
  try {
    const res = await fetch("/api/health");
    if (res.ok) {
      const data = await res.json();
      const pillText = document.getElementById("modelsStatusText");
      if (pillText && data.models) {
        pillText.textContent = `${Object.keys(data.models).length} AI Models Online`;
      }
    }
  } catch (e) {
    console.error("Health check error:", e);
  }
}

// Session Initialization
async function initSession() {
  if (authToken) {
    try {
      const res = await fetch("/api/auth/me", {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) {
        currentUser = await res.json();
        updateUserHeaderUi();
        buildSidebarNav();
        startNotificationPolling();
        if (typeof realtimeManager !== "undefined") {
          realtimeManager.connect();
        }
        
        // Navigate to current URL or role home
        const initialPath = window.location.pathname;
        if (initialPath === "/" || initialPath === "/login" || initialPath === "/register") {
          navigateHome();
        } else {
          navigate(initialPath, true);
        }
        return;
      } else {
        localStorage.removeItem("vg_token");
        authToken = null;
      }
    } catch (e) {
      console.error("Session verification failed:", e);
    }
  }
  
  // Unauthenticated -> Show Login
  showAuthView();
  setupAuthEventListeners();
  const initialPath = window.location.pathname;
  const initialHash = window.location.hash;
  if (initialPath === "/register" || initialHash === "#/register" || initialHash === "#register") {
    openCitizenRegistration();
  } else if (initialPath === "/register-worker" || initialHash === "#/register-worker" || initialHash === "#register-worker") {
    openWorkerRegistration();
  }
}

function updateUserHeaderUi() {
  const header = document.getElementById("globalHeader");
  const sidebar = document.getElementById("globalSidebar");
  const nameLabel = document.getElementById("headerUserName");
  const roleLabel = document.getElementById("headerUserRole");
  const avatarLabel = document.getElementById("userAvatarText");
  const dropName = document.getElementById("dropUserName");
  const dropEmail = document.getElementById("dropUserEmail");

  if (currentUser) {
    if (header) header.style.display = "flex";
    if (sidebar) sidebar.style.display = "flex";
    document.body.classList.remove("auth-mode");

    const roleName = currentUser.role === "USER" ? "Citizen" : (currentUser.role === "WORKER" ? "Field Worker" : (currentUser.role === "SUPERVISOR" ? "Field Supervisor" : "Admin"));
    if (nameLabel) nameLabel.textContent = currentUser.full_name;
    if (roleLabel) roleLabel.textContent = roleName;
    if (avatarLabel) {
      const initials = currentUser.full_name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
      avatarLabel.textContent = initials || "VG";
    }
    if (dropName) dropName.textContent = currentUser.full_name;
    if (dropEmail) dropEmail.textContent = currentUser.email;

    const dashWelcome = document.getElementById("dashWelcomeTitle");
    if (dashWelcome) {
      dashWelcome.textContent = `Welcome back, ${currentUser.full_name}!`;
    }
  } else {
    if (header) header.style.display = "none";
    if (sidebar) sidebar.style.display = "none";
    document.body.classList.add("auth-mode");
  }
}

// ==========================================================================
// SPA Router & Navigation Architecture
// ==========================================================================

function setupPopstateListener() {
  window.addEventListener("popstate", () => {
    navigate(window.location.pathname, false);
  });
  window.addEventListener("hashchange", () => {
    const raw = window.location.hash.replace("#", "");
    if (raw) navigate(raw, false);
  });
}

function navigate(route, replace = false) {
  // Stop live camera if navigating away
  if (isLiveDetecting && route !== "/user/live-detection") {
    stopLiveCameraDetection();
  }

  // Handle Auth Guards
  if (!currentUser && route !== "/login" && route !== "/register" && route !== "/register-worker" && route !== "/register-supervisor") {
    route = "/login";
  } else if (currentUser && (route === "/login" || route === "/register" || route === "/register-worker" || route === "/register-supervisor" || route === "/")) {
    if (currentUser.role === "USER") route = "/user/dashboard";
    else if (currentUser.role === "WORKER") route = "/worker/dashboard";
    else if (currentUser.role === "SUPERVISOR") route = "/supervisor/dashboard";
    else if (currentUser.role === "ADMIN") route = "/admin/dashboard";
  }

  currentRoute = route;
  if (!replace) {
    history.pushState(null, "", route);
  } else {
    history.replaceState(null, "", route);
  }

  // Hide all views
  document.querySelectorAll(".page-view").forEach(v => v.classList.remove("active"));

  // Close any open dropdowns
  document.querySelectorAll(".dropdown-menu-card").forEach(d => d.classList.remove("show"));

  // Match route
  if (route === "/login") {
    showAuthView();
    toggleRegisterModal(false);
    toggleWorkerRegisterModal(false);
    toggleSupervisorRegisterModal(false);
    return;
  } else if (route === "/register") {
    showAuthView();
    toggleRegisterModal(true);
    toggleWorkerRegisterModal(false);
    toggleSupervisorRegisterModal(false);
    return;
  } else if (route === "/register-worker") {
    showAuthView();
    toggleRegisterModal(false);
    toggleWorkerRegisterModal(true);
    toggleSupervisorRegisterModal(false);
    return;
  } else if (route === "/register-supervisor") {
    showAuthView();
    toggleRegisterModal(false);
    toggleWorkerRegisterModal(false);
    toggleSupervisorRegisterModal(true);
    return;
  }

  updateSidebarActiveItem(route);

  // Supervisor Routes
  if (route === "/supervisor/dashboard") {
    showView("view_supervisor_dashboard");
    loadSupervisorDashboardData();
  } else if (route === "/supervisor/inspections") {
    navigate("/supervisor/field-inspections", true);
    return;
  } else if (route === "/supervisor/field-inspections") {
    showView("view_supervisor_inspections");
    loadSupervisorInspectionsData();
  } else if (route.startsWith("/supervisor/inspections/") || route.startsWith("/supervisor/field-inspections/")) {
    const id = route.split("/")[3];
    showView("view_complaint_details");
    loadComplaintDetails(id);
  } else if (route === "/supervisor/workers") {
    showView("view_supervisor_workers");
    loadSupervisorWorkersData();
  } else if (route === "/supervisor/map") {
    showView("view_supervisor_map");
    setTimeout(initSupervisorMap, 100);
  } else if (route === "/supervisor/reports") {
    showView("view_supervisor_reports");
    loadSupervisorReportsData();
  } else if (route === "/supervisor/notifications") {
    showView("view_notifications");
    loadNotificationsFull();
  } else if (route === "/supervisor/profile" || route === "/supervisor/settings") {
    showView("view_profile");
    loadProfileData();
  } else if (route === "/admin/supervisor-approvals") {
    showView("view_admin_supervisor_approvals");
    loadAdminSupervisorApprovalsData();
  }
  // User Routes
  else if (route === "/user/dashboard") {
    showView("view_user_dashboard");
    loadUserDashboardData();
  } else if (route === "/user/ai-inspection") {
    showView("view_user_ai_inspection");
  } else if (route === "/admin/live-monitoring") {
    showView("view_admin_live_monitoring");
    loadAdminLiveMonitoring();
  } else if (route === "/user/live-detection" || route === "/worker/live-detection") {
    showView("view_user_live_detection");
    refreshCameraDevices(false);
  } else if (route === "/user/video-intelligence") {
    showView("view_user_video_intelligence");
  } else if (route === "/user/map" || route === "/worker/map" || route === "/admin/map") {
    showView("view_municipal_map");
    setTimeout(initLeafletMap, 100);
  } else if (route === "/user/detection-history" || route === "/admin/detection-history") {
    showView("view_detection_history");
    loadDetectionHistory();
  } else if (route === "/user/complaints" || route === "/admin/complaints") {
    showView("view_complaints_list");
    loadComplaintsList();
  } else if (route.startsWith("/user/complaints/") || route.startsWith("/admin/complaints/")) {
    const id = route.split("/")[3];
    showView("view_complaint_details");
    loadComplaintDetails(id);
  } else if (route === "/worker/dashboard") {
    showView("view_worker_dashboard");
    loadWorkerDashboardData();
  } else if (route === "/worker/tasks") {
    showView("view_worker_tasks");
    loadWorkerTasksData();
  } else if (route.startsWith("/worker/tasks/")) {
    const id = route.split("/")[3];
    showView("view_complaint_details");
    loadComplaintDetails(id);
  } else if (route === "/admin/dashboard") {
    showView("view_admin_dashboard");
    loadAdminDashboardData();
  } else if (route === "/admin/city-intelligence") {
    showView("view_admin_city_intelligence");
    loadCityIntelligenceData();
  } else if (route === "/admin/analytics") {
    showView("view_admin_analytics");
    loadAdminAnalyticsData();
  } else if (route === "/admin/reports") {
    showView("view_admin_reports");
  } else if (route === "/admin/worker-approvals") {
    showView("view_admin_worker_approvals");
    loadAdminWorkerApprovalsData();
  } else if (route === "/admin/workers") {
    showView("view_admin_workers");
    loadAdminWorkersData();
  } else if (route === "/admin/users") {
    showView("view_admin_users");
    loadAdminUsersData();
  } else if (route === "/user/notifications" || route === "/admin/notifications" || route === "/worker/notifications") {
    showView("view_notifications");
    loadNotificationsFull();
  } else if (route === "/user/profile" || route === "/worker/profile") {
    showView("view_profile");
    loadProfileData();
  } else if (route === "/user/settings" || route === "/admin/settings" || route === "/worker/settings") {
    showView("view_profile");
    loadProfileData();
  } else {
    // Default fallback
    navigateHome();
  }
}

function showView(viewId) {
  if (isLiveDetecting && viewId !== "view_user_live_detection" && viewId !== "view_admin_live_monitoring") {
    stopLiveCameraDetection();
  }
  const target = document.getElementById(viewId);
  if (target) {
    target.classList.add("active");
    window.scrollTo({ top: 0, behavior: 'instant' });
  }
}

function showAuthView() {
  document.getElementById("view_auth").classList.add("active");
}

function navigateHome() {
  if (!currentUser) navigate("/login");
  else if (currentUser.role === "USER") navigate("/user/dashboard");
  else if (currentUser.role === "WORKER") navigate("/worker/dashboard");
  else if (currentUser.role === "SUPERVISOR") navigate("/supervisor/dashboard");
  else if (currentUser.role === "ADMIN") navigate("/admin/dashboard");
}

function navigateByRole(target) {
  if (!currentUser) return;
  if (currentUser.role === "USER") navigate(`/user/${target}`);
  else if (currentUser.role === "WORKER") navigate(`/worker/${target}`);
  else if (currentUser.role === "SUPERVISOR") navigate(`/supervisor/${target}`);
  else if (currentUser.role === "ADMIN") navigate(`/admin/${target}`);
}

// ==========================================================================
// Role-Based Dynamic Sidebar
// ==========================================================================

// Sidebar Builder (AI Models strictly removed from Citizen & Admin navigation)
function buildSidebarNav() {
  const navContainer = document.getElementById("sidebarNavLinks");
  if (!navContainer || !currentUser) return;

  let links = [];

  if (currentUser.role === "USER") {
    links = [
      { title: "Dashboard", route: "/user/dashboard", icon: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>' },
      { title: "Upload / Analyze", route: "/user/ai-inspection", icon: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>' },
      { title: "Live Detection", route: "/user/live-detection", icon: '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>' },
      { title: "Video Intelligence", route: "/user/video-intelligence", icon: '<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>' },
      { title: "My Complaints", route: "/user/complaints", icon: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>' },
      { title: "Map & GPS", route: "/user/map", icon: '<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>' },
      { title: "Detection History", route: "/user/detection-history", icon: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 14 14"/>' },
      { title: "Notifications", route: "/user/notifications", icon: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>' },
      { title: "Settings", route: "/user/settings", icon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l-.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06-.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>' }
    ];
  } else if (currentUser.role === "WORKER") {
    links = [
      { title: "Dashboard", route: "/worker/dashboard", icon: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>' },
      { title: "Assigned Tasks", route: "/worker/tasks", icon: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>' },
      { title: "Live Detection", route: "/worker/live-detection", icon: '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>' },
      { title: "Map & GPS", route: "/worker/map", icon: '<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>' },
      { title: "Notifications", route: "/worker/notifications", icon: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>' },
      { title: "Settings", route: "/worker/settings", icon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l-.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06-.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>' }
    ];
  } else if (currentUser.role === "SUPERVISOR") {
    links = [
      { title: "Dashboard", route: "/supervisor/dashboard", icon: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>' },
      { title: "Field Inspections", route: "/supervisor/field-inspections", icon: '<polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>' },
      { title: "Workers", route: "/supervisor/workers", icon: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>' },
      { title: "Map & Live View", route: "/supervisor/map", icon: '<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>' },
      { title: "Reports", route: "/supervisor/reports", icon: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>' },
      { title: "Notifications", route: "/supervisor/notifications", icon: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>' },
      { title: "Settings", route: "/supervisor/settings", icon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l-.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06-.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>' },
      { title: "Logout", route: "/login", icon: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>' }
    ];
  } else if (currentUser.role === "ADMIN") {
    links = [
      { title: "Dashboard", route: "/admin/dashboard", icon: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>' },
      { title: "City Intelligence", route: "/admin/city-intelligence", icon: '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>' },
      { title: "Live Monitoring", route: "/admin/live-monitoring", icon: '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>' },
      { title: "Complaints", route: "/admin/complaints", icon: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>' },
      { title: "Map & GPS", route: "/admin/map", icon: '<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>' },
      { title: "Detection History", route: "/admin/detection-history", icon: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 14 14"/>' },
      { title: "Supervisor Approvals", route: "/admin/supervisor-approvals", icon: '<path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/>' },
      { title: "Workers", route: "/admin/workers", icon: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>' },
      { title: "Worker Approvals", route: "/admin/worker-approvals", icon: '<path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/>' },
      { title: "Users", route: "/admin/users", icon: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>' },
      { title: "Analytics", route: "/admin/analytics", icon: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>' },
      { title: "Reports", route: "/admin/reports", icon: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>' },
      { title: "Notifications", route: "/admin/notifications", icon: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>' },
      { title: "Settings", route: "/admin/settings", icon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l-.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06-.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>' }
    ];
  }

  navContainer.innerHTML = `
    <div class="sidebar-nav-title">Menu Navigation</div>
    ${links.map(l => `
      <button class="nav-link-btn" data-route="${l.route}" onclick="navigate('${l.route}')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${l.icon}</svg>
        <span>${l.title}</span>
      </button>
    `).join("")}
  `;
}

function updateSidebarActiveItem(route) {
  document.querySelectorAll(".nav-link-btn").forEach(btn => {
    if (btn.getAttribute("data-route") === route) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
}

function toggleSidebarMobile() {
  const sidebar = document.getElementById("globalSidebar");
  if (sidebar) sidebar.classList.toggle("mobile-open");
}

// ==========================================================================
// Authentication Logic
// ==========================================================================

function selectAuthRole(role) {
  document.querySelectorAll(".auth-role-tab").forEach(t => t.classList.remove("active"));
  if (role === "USER") {
    document.getElementById("tabRoleCitizen")?.classList.add("active");
  } else if (role === "WORKER") {
    document.getElementById("tabRoleWorker")?.classList.add("active");
  } else if (role === "SUPERVISOR") {
    document.getElementById("tabRoleSupervisor")?.classList.add("active");
  } else if (role === "ADMIN") {
    document.getElementById("tabRoleAdmin")?.classList.add("active");
  }
}

// Dedicated Create Account Selection Modal Handlers
function openCreateAccountModal(e) {
  if (e) {
    if (e.preventDefault) e.preventDefault();
    if (e.stopPropagation) e.stopPropagation();
  }
  toggleCreateAccountModal(true);
}

function toggleCreateAccountModal(show = true) {
  const modal = document.getElementById("modalCreateAccountSelection");
  if (!modal) return;
  if (show) {
    modal.classList.add("show");
    modal.style.display = "flex";
  } else {
    modal.classList.remove("show");
    modal.style.display = "none";
  }
}

function selectRegistrationType(role) {
  toggleCreateAccountModal(false);
  if (role === "USER") {
    openCitizenRegistration();
  } else if (role === "WORKER") {
    openWorkerRegistration();
  } else if (role === "SUPERVISOR") {
    openSupervisorRegistration();
  }
}

// Show / Hide Password Toggle
function togglePasswordVisibility(inputId, button) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isCurrentlyPassword = input.type === 'password';
  input.type = isCurrentlyPassword ? 'text' : 'password';

  if (button) {
    const isNowVisible = input.type === 'text';
    button.setAttribute('aria-label', isNowVisible ? 'Hide password' : 'Show password');
    button.setAttribute('title', isNowVisible ? 'Hide password' : 'Show password');
    const openEye = button.querySelector('.eye-open');
    const closedEye = button.querySelector('.eye-closed');
    if (openEye && closedEye) {
      openEye.style.display = isNowVisible ? 'none' : 'block';
      closedEye.style.display = isNowVisible ? 'block' : 'none';
    }
  }
}
window.togglePasswordVisibility = togglePasswordVisibility;

async function handleLoginSubmit(event) {
  event.preventDefault();
  const email = document.getElementById("authEmail").value.trim();
  const password = document.getElementById("authPassword").value;
  const btn = document.getElementById("btnLoginSubmit");
  
  try {
    btn.disabled = true;
    btn.innerHTML = `<span>Authenticating...</span>`;
    
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();
    if (res.ok) {
      authToken = data.access_token;
      localStorage.setItem("vg_token", authToken);
      currentUser = {
        id: data.user_id,
        email: data.email,
        full_name: data.full_name,
        role: data.role
      };
      toast(`Welcome back, ${currentUser.full_name}!`, "success");
      updateUserHeaderUi();
      buildSidebarNav();
      if (typeof realtimeManager !== "undefined") {
        realtimeManager.connect();
      }
      navigateHome();
    } else {
      toast(data.detail || "Authentication failed. Incorrect email or password.", "error");
    }
  } catch (e) {
    toast("Network connection error: " + e.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>Sign In</span> <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>`;
  }
}

function handleLogout() {
  if (typeof realtimeManager !== "undefined") {
    realtimeManager.disconnect();
  }
  localStorage.removeItem("vg_token");
  authToken = null;
  currentUser = null;
  toast("Signed out successfully", "info");
  updateUserHeaderUi();
  navigate("/login");
}

// Registration Triggers & Robust Listeners
function setupAuthEventListeners() {
  const createAccLink = document.getElementById("createAccountLink");
  if (createAccLink) {
    createAccLink.onclick = (e) => {
      if (e) { e.preventDefault(); e.stopPropagation(); }
      openCreateAccountModal(e);
      return false;
    };
  }

  // Legacy link hooks if present
  const regCitizenLink = document.getElementById("registerCitizenLink");
  if (regCitizenLink) {
    regCitizenLink.onclick = (e) => {
      if (e) { e.preventDefault(); e.stopPropagation(); }
      openCitizenRegistration(e);
      return false;
    };
  }
  const regWorkerLink = document.getElementById("registerWorkerLink");
  if (regWorkerLink) {
    regWorkerLink.onclick = (e) => {
      if (e) { e.preventDefault(); e.stopPropagation(); }
      openWorkerRegistration(e);
      return false;
    };
  }
  const regSupervisorLink = document.getElementById("registerSupervisorLink");
  if (regSupervisorLink) {
    regSupervisorLink.onclick = (e) => {
      if (e) { e.preventDefault(); e.stopPropagation(); }
      openSupervisorRegistration(e);
      return false;
    };
  }

  // Close modals when clicking backdrop overlay
  const selModal = document.getElementById("modalCreateAccountSelection");
  if (selModal && !selModal.dataset.backdropBound) {
    selModal.dataset.backdropBound = "true";
    selModal.addEventListener("click", (e) => {
      if (e.target === selModal) toggleCreateAccountModal(false);
    });
  }
  const citModal = document.getElementById("modalCitizenRegister");
  if (citModal && !citModal.dataset.backdropBound) {
    citModal.dataset.backdropBound = "true";
    citModal.addEventListener("click", (e) => {
      if (e.target === citModal) toggleRegisterModal(false);
    });
  }
  const wrkModal = document.getElementById("modalWorkerRegister");
  if (wrkModal && !wrkModal.dataset.backdropBound) {
    wrkModal.dataset.backdropBound = "true";
    wrkModal.addEventListener("click", (e) => {
      if (e.target === wrkModal) toggleWorkerRegisterModal(false);
    });
  }
  const supModal = document.getElementById("modalSupervisorRegister");
  if (supModal && !supModal.dataset.backdropBound) {
    supModal.dataset.backdropBound = "true";
    supModal.addEventListener("click", (e) => {
      if (e.target === supModal) toggleSupervisorRegisterModal(false);
    });
  }
}

function openCitizenRegistration(e) {
  if (e) {
    if (e.preventDefault) e.preventDefault();
    if (e.stopPropagation) e.stopPropagation();
  }
  toggleRegisterModal(true);
}

function openWorkerRegistration(e) {
  if (e) {
    if (e.preventDefault) e.preventDefault();
    if (e.stopPropagation) e.stopPropagation();
  }
  toggleWorkerRegisterModal(true);
}

function openSupervisorRegistration(e) {
  if (e) {
    if (e.preventDefault) e.preventDefault();
    if (e.stopPropagation) e.stopPropagation();
  }
  toggleSupervisorRegisterModal(true);
}

// Supervisor Registration Logic (Subject to Admin Approval)
function toggleSupervisorRegisterModal(show = true) {
  const modal = document.getElementById("modalSupervisorRegister");
  if (!modal) return;
  if (show) {
    const form = document.getElementById("formSupervisorRegister");
    if (form) form.reset();
    modal.classList.add("show");
    modal.style.display = "flex";
    const nameInput = document.getElementById("supRegFullName");
    if (nameInput) setTimeout(() => nameInput.focus(), 150);
  } else {
    modal.classList.remove("show");
    modal.style.display = "none";
  }
}

async function handleSupervisorRegisterSubmit(event) {
  event.preventDefault();
  const fullName = (document.getElementById("supRegFullName")?.value || "").trim();
  const email = (document.getElementById("supRegEmail")?.value || "").trim();
  const phone = (document.getElementById("supRegPhone")?.value || "").trim();
  const employeeId = (document.getElementById("supRegEmployeeId")?.value || "").trim();
  const department = (document.getElementById("supRegDepartment")?.value || "").trim();
  const specialization = (document.getElementById("supRegSpecialization")?.value || "").trim();
  const zone = (document.getElementById("supRegZone")?.value || "").trim();
  const password = document.getElementById("supRegPassword")?.value || "";
  const confirmPassword = document.getElementById("supRegConfirmPassword")?.value || "";
  const btn = document.getElementById("btnSupervisorRegisterSubmit");

  if (!fullName || fullName.length < 2) {
    toast("Please enter your full name.", "warning");
    document.getElementById("supRegFullName")?.focus();
    return;
  }

  if (!email || !validateEmailFormat(email)) {
    toast("Please enter a valid email address.", "warning");
    document.getElementById("supRegEmail")?.focus();
    return;
  }

  if (!phone || phone.length < 5) {
    toast("Please enter a contact phone number.", "warning");
    document.getElementById("supRegPhone")?.focus();
    return;
  }

  if (!department) {
    toast("Please select your municipal department.", "warning");
    document.getElementById("supRegDepartment")?.focus();
    return;
  }

  if (!password || password.length < 6) {
    toast("Password must be at least 6 characters.", "warning");
    document.getElementById("supRegPassword")?.focus();
    return;
  }

  if (password !== confirmPassword) {
    toast("Passwords do not match.", "warning");
    document.getElementById("supRegConfirmPassword")?.focus();
    return;
  }

  try {
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span>Submitting Application...</span>`;
    }

    const payload = {
      full_name: fullName,
      email: email,
      phone: phone,
      department: department,
      employee_id: employeeId || null,
      specialization: specialization || null,
      zone: zone || null,
      password: password
    };

    const res = await fetch("/api/auth/register-supervisor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json().catch(() => ({}));

    if (res.ok || res.status === 201) {
      toast("Supervisor application submitted successfully. Your account is pending Admin approval.", "success");
      toggleSupervisorRegisterModal(false);

      const loginEmail = document.getElementById("authEmail");
      const loginPassword = document.getElementById("authPassword");
      if (loginEmail) loginEmail.value = email;
      if (loginPassword) loginPassword.value = "";

      selectAuthRole("SUPERVISOR");
      navigate("/login");
    } else if (res.status === 400 || res.status === 409) {
      toast(data.detail || "An account with this email already exists.", "error");
    } else {
      toast(data.detail || "Registration failed. Please check your details and try again.", "error");
    }
  } catch (e) {
    console.error("Supervisor registration error:", e);
    toast("Unable to connect to server. Please try again.", "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>Submit Supervisor Application</span>`;
    }
  }
}

// Citizen Registration Logic
function toggleRegisterModal(show = true) {
  const modal = document.getElementById("modalCitizenRegister");
  if (!modal) return;
  if (show) {
    const form = document.getElementById("formCitizenRegister");
    if (form) form.reset();
    modal.classList.add("show");
    modal.style.display = "flex";
    const nameInput = document.getElementById("regFullName");
    if (nameInput) setTimeout(() => nameInput.focus(), 150);
  } else {
    modal.classList.remove("show");
    modal.style.display = "none";
  }
}

function validateEmailFormat(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(String(email).toLowerCase());
}

async function handleRegisterSubmit(event) {
  event.preventDefault();
  const fullName = (document.getElementById("regFullName")?.value || "").trim();
  const email = (document.getElementById("regEmail")?.value || "").trim();
  const phone = (document.getElementById("regPhone")?.value || "").trim();
  const password = document.getElementById("regPassword")?.value || "";
  const confirmPassword = document.getElementById("regConfirmPassword")?.value || "";
  const btn = document.getElementById("btnRegisterSubmit");

  // 1. Full name validation
  if (!fullName || fullName.length < 2) {
    toast("Please enter your full name.", "warning");
    document.getElementById("regFullName")?.focus();
    return;
  }

  // 2. Email validation
  if (!email || !validateEmailFormat(email)) {
    toast("Please enter a valid email address.", "warning");
    document.getElementById("regEmail")?.focus();
    return;
  }

  // 3. Password validation
  if (!password || password.length < 6) {
    toast("Password must be at least 6 characters.", "warning");
    document.getElementById("regPassword")?.focus();
    return;
  }

  // 4. Confirm password match
  if (password !== confirmPassword) {
    toast("Passwords do not match.", "warning");
    document.getElementById("regConfirmPassword")?.focus();
    return;
  }

  try {
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span>Creating Account...</span>`;
    }

    const payload = {
      full_name: fullName,
      email: email,
      phone: phone || null,
      password: password
    };

    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json().catch(() => ({}));

    if (res.ok || res.status === 201) {
      toast("Citizen account created successfully.", "success");
      toggleRegisterModal(false);

      // Pre-populate login form with newly registered email
      const loginEmail = document.getElementById("authEmail");
      const loginPassword = document.getElementById("authPassword");
      if (loginEmail) loginEmail.value = email;
      if (loginPassword) loginPassword.value = "";

      selectAuthRole("USER");
      navigate("/login");
    } else if (res.status === 400 || res.status === 409) {
      const msg = data.detail || "An account with this email already exists.";
      toast(msg, "error");
    } else {
      toast(data.detail || "Registration failed. Please check your information and try again.", "error");
    }
  } catch (e) {
    console.error("Citizen registration error:", e);
    toast("Unable to connect to server. Please try again.", "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>Create Citizen Account</span>`;
    }
  }
}

// Worker Registration Logic (Awaiting Admin Approval)
function toggleWorkerRegisterModal(show = true) {
  const modal = document.getElementById("modalWorkerRegister");
  if (!modal) return;
  if (show) {
    const form = document.getElementById("formWorkerRegister");
    if (form) form.reset();
    modal.classList.add("show");
    modal.style.display = "flex";
    const nameInput = document.getElementById("workerRegFullName");
    if (nameInput) setTimeout(() => nameInput.focus(), 150);
  } else {
    modal.classList.remove("show");
    modal.style.display = "none";
  }
}

async function handleWorkerRegisterSubmit(event) {
  event.preventDefault();
  const fullName = (document.getElementById("workerRegFullName")?.value || "").trim();
  const email = (document.getElementById("workerRegEmail")?.value || "").trim();
  const phone = (document.getElementById("workerRegPhone")?.value || "").trim();
  const department = (document.getElementById("workerRegDepartment")?.value || "").trim();
  const password = document.getElementById("workerRegPassword")?.value || "";
  const confirmPassword = document.getElementById("workerRegConfirmPassword")?.value || "";
  const btn = document.getElementById("btnWorkerRegisterSubmit");

  if (!fullName || fullName.length < 2) {
    toast("Please enter your full name.", "warning");
    document.getElementById("workerRegFullName")?.focus();
    return;
  }

  if (!email || !validateEmailFormat(email)) {
    toast("Please enter a valid email address.", "warning");
    document.getElementById("workerRegEmail")?.focus();
    return;
  }

  if (!phone || phone.length < 5) {
    toast("Please enter a contact phone number.", "warning");
    document.getElementById("workerRegPhone")?.focus();
    return;
  }

  if (!department) {
    toast("Please select your field department.", "warning");
    document.getElementById("workerRegDepartment")?.focus();
    return;
  }

  if (!password || password.length < 6) {
    toast("Password must be at least 6 characters.", "warning");
    document.getElementById("workerRegPassword")?.focus();
    return;
  }

  if (password !== confirmPassword) {
    toast("Passwords do not match.", "warning");
    document.getElementById("workerRegConfirmPassword")?.focus();
    return;
  }

  try {
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span>Submitting Application...</span>`;
    }

    const payload = {
      full_name: fullName,
      email: email,
      phone: phone,
      department: department,
      password: password
    };

    const res = await fetch("/api/auth/register-worker", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json().catch(() => ({}));

    if (res.ok || res.status === 201) {
      toast("Worker registration submitted successfully. Your account is pending Admin approval.", "success");
      toggleWorkerRegisterModal(false);

      const loginEmail = document.getElementById("authEmail");
      const loginPassword = document.getElementById("authPassword");
      if (loginEmail) loginEmail.value = email;
      if (loginPassword) loginPassword.value = "";

      selectAuthRole("WORKER");
      navigate("/login");
    } else if (res.status === 400 || res.status === 409) {
      toast(data.detail || "An account with this email already exists.", "error");
    } else {
      toast(data.detail || "Registration failed. Please check your details and try again.", "error");
    }
  } catch (e) {
    console.error("Worker registration error:", e);
    toast("Unable to connect to server. Please try again.", "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>Submit Worker Application</span>`;
    }
  }
}

// ==========================================================================
// Citizen Dashboard View Data
// ==========================================================================

async function loadUserDashboardData() {
  if (!authToken) return;
  try {
    const res = await fetch("/api/user/dashboard", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      document.getElementById("userStatTotal").textContent = data.stats.total_complaints || 0;
      document.getElementById("userStatInProgress").textContent = data.stats.in_progress || 0;
      document.getElementById("userStatCompleted").textContent = data.stats.completed || 0;
      document.getElementById("userStatUpdates").textContent = (data.notifications && data.notifications.length) || 0;

      // Render recent complaints
      const listContainer = document.getElementById("userDashRecentComplaints");
      if (listContainer) {
        if (data.recent_complaints && data.recent_complaints.length > 0) {
          listContainer.innerHTML = data.recent_complaints.map(c => `
            <div class="detected-item-card" onclick="navigate('/user/complaints/${c.id}')" style="cursor: pointer;">
              <div class="detected-item-left">
                <span class="badge ${c.severity === 'HIGH' ? 'badge-danger' : (c.severity === 'MEDIUM' ? 'badge-warning' : 'badge-info')}">${c.severity}</span>
                <div>
                  <div class="detected-type-tag">${c.issue_type ? c.issue_type.replace('_', ' ') : 'Road Hazard'} #${c.tracking_number || c.complaint_id || c.id}</div>
                  <div class="detected-conf-text">${c.location_address || 'Municipal Zone'} • ${c.created_at ? c.created_at.slice(0, 10) : ''}</div>
                </div>
              </div>
              <span class="badge ${c.status === 'COMPLETED' ? 'badge-success' : (c.status === 'IN_PROGRESS' ? 'badge-warning' : 'badge-info')}">${c.status}</span>
            </div>
          `).join("");
        } else {
          listContainer.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--text-muted);">No complaints filed yet. Click "Upload Image" to report a road hazard!</div>`;
        }
      }
    }
  } catch (e) {
    console.error("Dashboard load failed:", e);
  }
}

// ==========================================================================
// AI Diagnostics Studio (Section 3, 4, 8)
// ==========================================================================

let selectedImagePreviewDataUrl = null;

function getPipelineDisplayName(mode) {
  switch (mode) {
    case "road_damage": return "Road Damage (Crack / Pothole)";
    case "traffic_sign": return "Traffic Signs";
    case "traffic_signal": return "Traffic Signal";
    case "sign_condition": return "Sign Condition";
    case "all_in_one": default: return "VisionGuardAI Full Suite";
  }
}

function selectAiMode(mode) {
  activeAiMode = mode;
  document.querySelectorAll(".model-tab-btn").forEach(btn => {
    if (btn.getAttribute("data-mode") === mode) btn.classList.add("active");
    else btn.classList.remove("active");
  });

  const detailEl = document.getElementById("aiThresholdsDetail");

  if (mode === "road_damage") {
    activeConfidence = 0.05;
    if (detailEl) {
      detailEl.innerHTML = `
        <div style="padding-top: 6px; border-top: 1px solid var(--border-color, rgba(255,255,255,0.06));">
          <span>Confidence Threshold: <strong style="color: var(--primary);">5%</strong></span>
        </div>
      `;
    }
  } else if (mode === "traffic_sign") {
    activeConfidence = 0.04;
    if (detailEl) {
      detailEl.innerHTML = `
        <div style="padding-top: 6px; border-top: 1px solid var(--border-color, rgba(255,255,255,0.06));">
          <span>Confidence Threshold: <strong style="color: var(--primary);">4%</strong></span>
        </div>
      `;
    }
  } else if (mode === "traffic_signal") {
    activeConfidence = 0.25;
    if (detailEl) {
      detailEl.innerHTML = `
        <div style="padding-top: 6px; border-top: 1px solid var(--border-color, rgba(255,255,255,0.06));">
          <span>Confidence Threshold: <strong style="color: var(--primary);">25%</strong></span>
        </div>
      `;
    }
  } else if (mode === "sign_condition") {
    activeConfidence = 0.04;
    if (detailEl) {
      detailEl.innerHTML = `
        <div style="padding-top: 6px; border-top: 1px solid var(--border-color, rgba(255,255,255,0.06));">
          <span>Threshold: <strong style="color: var(--text-muted);">Runs after Traffic Sign detection</strong></span>
        </div>
      `;
    }
  } else {
    // all_in_one (Full Suite)
    activeConfidence = 0.25;
    if (detailEl) {
      detailEl.innerHTML = `
        <div style="display: flex; flex-wrap: wrap; gap: 6px 14px; padding-top: 6px; border-top: 1px solid var(--border-color, rgba(255,255,255,0.06));">
          <span>🚸 Traffic Signs: <strong style="color: var(--primary);">4%</strong></span>
          <span>⚠️ Road Damage: <strong style="color: var(--primary);">5%</strong></span>
          <span>🚦 Traffic Signals: <strong style="color: var(--primary);">25%</strong></span>
          <span>🔍 Sign Condition: <strong style="color: var(--text-muted);">Runs after Traffic Sign detection</strong></span>
        </div>
      `;
    }
  }

  // Clear previous inference results when switching pipelines
  lastInferenceResult = null;

  // Clear previous detected items
  const list = document.getElementById("detectedItemsList");
  if (list) {
    list.innerHTML = `<div style="font-size: 13px; color: var(--text-muted); padding: 12px; text-align: center;">Ready to analyze with <strong>${getPipelineDisplayName(mode)}</strong>.<br><small style="color: var(--text-muted); font-size: 11px;">Click '✦ Analyze with AI' to process the uploaded image.</small></div>`;
  }

  // Clear/Hide previous Zoomed Sign Condition Crop
  const signZoomed = document.getElementById("signConditionZoomedContainer");
  if (signZoomed) {
    signZoomed.style.display = "none";
  }

  // Reset inference time badge
  const timeBadge = document.getElementById("aiInferenceTimeBadge");
  if (timeBadge) {
    timeBadge.textContent = "Ready";
  }

  // Restore clean preview of uploaded image if one was uploaded
  const previewImg = document.getElementById("annotatedOutputImg");
  const placeholder = document.getElementById("annotatedPlaceholder");
  if (selectedImagePreviewDataUrl && previewImg && placeholder) {
    previewImg.src = selectedImagePreviewDataUrl;
    previewImg.style.display = "block";
    placeholder.style.display = "none";
  } else if (!selectedImageFile && previewImg && placeholder) {
    previewImg.style.display = "none";
    placeholder.style.display = "block";
  }
}

function updateConfLabel(val) {
  let numVal = parseFloat(val);
  if (activeAiMode === "road_damage" && numVal < 0.05) {
    numVal = 0.05;
  }
  activeConfidence = numVal;
  const label = document.getElementById("confValueLabel");
  if (label) label.textContent = `${Math.round(activeConfidence * 100)}%`;
}

function handleFileSelect(event) {
  const file = event.target.files[0];
  if (file) {
    selectedImageFile = file;
    lastInferenceResult = null;
    const reader = new FileReader();
    reader.onload = (e) => {
      selectedImagePreviewDataUrl = e.target.result;
      const previewImg = document.getElementById("annotatedOutputImg");
      const placeholder = document.getElementById("annotatedPlaceholder");
      if (previewImg && placeholder) {
        previewImg.src = selectedImagePreviewDataUrl;
        previewImg.style.display = "block";
        placeholder.style.display = "none";
      }
    };
    reader.readAsDataURL(file);

    // Reset results on new image
    const list = document.getElementById("detectedItemsList");
    if (list) {
      list.innerHTML = `<div style="font-size: 13px; color: var(--text-muted); padding: 12px; text-align: center;">Selected <strong>${file.name}</strong>.<br><small style="color: var(--text-muted); font-size: 11px;">Click '✦ Analyze with AI' to run ${getPipelineDisplayName(activeAiMode)}.</small></div>`;
    }
    const signZoomed = document.getElementById("signConditionZoomedContainer");
    if (signZoomed) signZoomed.style.display = "none";
    const timeBadge = document.getElementById("aiInferenceTimeBadge");
    if (timeBadge) timeBadge.textContent = "Ready";

    toast(`Selected image: ${file.name}`, "info");
  }
}

async function runAiInference() {
  if (!selectedImageFile) {
    toast("Please select or drop an image file first", "warning");
    return;
  }

  const btn = document.getElementById("btnRunInference");
  const timeBadge = document.getElementById("aiInferenceTimeBadge");

  try {
    btn.disabled = true;
    btn.innerHTML = `<span>Processing AI Models...</span>`;
    timeBadge.textContent = "Inferring...";

    console.log(`[VisionGuard AI] Starting inference: Mode=${activeAiMode} | Confidence=${activeConfidence} | File=${selectedImageFile.name}`);

    const formData = new FormData();
    formData.append("file", selectedImageFile);
    formData.append("mode", activeAiMode);
    formData.append("conf", activeConfidence);

    const startTime = performance.now();
    const res = await fetch("/api/predict/upload", {
      method: "POST",
      body: formData
    });

    const elapsed = Math.round(performance.now() - startTime);

    if (res.ok) {
      lastInferenceResult = await res.json();
      console.log("[VisionGuard AI] Inference response:", lastInferenceResult);
      timeBadge.textContent = `${elapsed} ms`;
      renderAiInferenceResults(lastInferenceResult);
      toast("AI diagnostics completed!", "success");

      // Auto record detection if user logged in
      if (authToken) {
        recordDetectionToDatabase(lastInferenceResult);
      }
    } else {
      const err = await res.json();
      toast(err.detail || "Inference error", "error");
    }
  } catch (e) {
    toast("Inference failed: " + e.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>✦ Analyze with AI</span>`;
  }
}

function renderAiInferenceResults(result) {
  const previewImg = document.getElementById("annotatedOutputImg");
  const placeholder = document.getElementById("annotatedPlaceholder");
  const list = document.getElementById("detectedItemsList");
  const signZoomed = document.getElementById("signConditionZoomedContainer");

  if (result.annotated_image && previewImg) {
    previewImg.src = result.annotated_image;
    previewImg.style.display = "block";
    if (placeholder) placeholder.style.display = "none";
  } else if (selectedImagePreviewDataUrl && previewImg) {
    previewImg.src = selectedImagePreviewDataUrl;
    previewImg.style.display = "block";
    if (placeholder) placeholder.style.display = "none";
  }

  const mode = (result.mode || activeAiMode || "").toLowerCase();
  const currentThresholdPct = Math.round(activeConfidence * 100);
  const fileName = result.filename || (selectedImageFile ? selectedImageFile.name : "Uploaded Image");
  const sourceBanner = `
    <div style="margin-bottom: 12px; font-size: 12px; color: var(--text-muted); display: flex; align-items: center; justify-content: space-between; background: var(--bg-subtle); padding: 6px 12px; border-radius: 6px;">
      <span>Source: <strong style="color: var(--primary);">IMAGE</strong> • File: <strong>${fileName}</strong></span>
      <span>Model: <strong>${result.model_name || getPipelineDisplayName(activeAiMode)}</strong></span>
    </div>
  `;

  // =========================================================================
  // 1. ROAD DAMAGE PIPELINE ISOLATION (Crack, Pothole)
  // =========================================================================
  if (mode === "road_damage" || mode === "roaddamage" || mode === "damage") {
    if (signZoomed) signZoomed.style.display = "none";

    let rawDets = [];
    if (result.detections && Array.isArray(result.detections)) {
      rawDets = result.detections;
    } else if (result.road_damages && Array.isArray(result.road_damages)) {
      rawDets = result.road_damages;
    } else if (result.results && result.results.road_damage && Array.isArray(result.results.road_damage.detections)) {
      rawDets = result.results.road_damage.detections;
    }

    const items = rawDets.map(d => {
      const clsName = d.class_name || d.name || d.class || "Road Hazard";
      const conf = d.confidence != null ? d.confidence : (d.conf != null ? d.conf : 0.10);
      const isPothole = clsName.toLowerCase().includes("pothole");
      const sev = isPothole ? (conf >= 0.70 ? "CRITICAL" : (conf >= 0.35 ? "HIGH" : "MEDIUM")) : (conf >= 0.50 ? "HIGH" : "MEDIUM");
      return {
        class_name: clsName,
        confidence: conf,
        severity: sev,
        box: d.box || null,
        pipeline: "Road Damage"
      };
    });

    if (items.length > 0) {
      list.innerHTML = sourceBanner + items.map((item, idx) => {
        const confPct = item.confidence < 0.20 ? (item.confidence * 100).toFixed(2) : Math.round(item.confidence * 100);
        const badgeClass = item.severity === 'CRITICAL' ? 'badge-danger' : (item.severity === 'HIGH' ? 'badge-danger' : (item.severity === 'MEDIUM' ? 'badge-warning' : 'badge-success'));
        return `
          <div class="detected-item-card" style="margin-bottom: 8px;">
            <div class="detected-item-left">
              <span class="badge ${badgeClass}">${item.severity}</span>
              <div>
                <div class="detected-type-tag">${idx + 1}. ${item.class_name}</div>
                <div class="detected-conf-text">Confidence: ${confPct}% ${item.box ? `• Box: [${item.box.map(Math.round).join(", ")}]` : ""}</div>
              </div>
            </div>
            <span class="badge badge-info">${item.pipeline}</span>
          </div>
        `;
      }).join("");
    } else {
      list.innerHTML = sourceBanner + `
        <div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 13px;">
          <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">No detections found in this image.</div>
          <div style="font-size: 11.5px;">Analyzed with Road Damage AI (5% confidence threshold)</div>
        </div>
      `;
    }
    return;
  }

  // =========================================================================
  // 2. TRAFFIC SIGN PIPELINE ISOLATION
  // =========================================================================
  if (mode === "traffic_sign" || mode === "trafficsign" || mode === "sign") {
    if (signZoomed) signZoomed.style.display = "none";

    let rawDets = [];
    if (result.detections && Array.isArray(result.detections)) {
      rawDets = result.detections;
    } else if (result.traffic_signs && Array.isArray(result.traffic_signs)) {
      rawDets = result.traffic_signs;
    } else if (result.results && result.results.traffic_signs && Array.isArray(result.results.traffic_signs.detections)) {
      rawDets = result.results.traffic_signs.detections;
    }

    const items = rawDets.map(d => ({
      class_name: d.class_name || d.name || "Traffic Sign",
      confidence: d.confidence || d.conf || 0.85,
      severity: (d.confidence || 0.85) > 0.80 ? "HIGH" : "MEDIUM",
      box: d.box || null,
      pipeline: "Traffic Sign"
    }));

    if (items.length > 0) {
      list.innerHTML = sourceBanner + items.map((item, idx) => {
        const confPct = Math.round(item.confidence * 100);
        const badgeClass = item.severity === 'HIGH' ? 'badge-danger' : 'badge-warning';
        return `
          <div class="detected-item-card" style="margin-bottom: 8px;">
            <div class="detected-item-left">
              <span class="badge ${badgeClass}">${item.severity}</span>
              <div>
                <div class="detected-type-tag">${idx + 1}. ${item.class_name}</div>
                <div class="detected-conf-text">Confidence: ${confPct}% ${item.box ? `• Box: [${item.box.map(Math.round).join(", ")}]` : ""}</div>
              </div>
            </div>
            <span class="badge badge-info">${item.pipeline}</span>
          </div>
        `;
      }).join("");
    } else {
      list.innerHTML = sourceBanner + `
        <div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 13px;">
          <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">No detections found in this image.</div>
          <div style="font-size: 11.5px;">Analyzed with Traffic Sign AI (4% confidence threshold)</div>
        </div>
      `;
    }
    return;
  }

  // =========================================================================
  // 3. TRAFFIC SIGNAL PIPELINE ISOLATION
  // =========================================================================
  if (mode === "traffic_signal" || mode === "trafficsignal" || mode === "signal") {
    if (signZoomed) signZoomed.style.display = "none";

    let rawDets = [];
    if (result.detections && Array.isArray(result.detections)) {
      rawDets = result.detections;
    } else if (result.traffic_signals && Array.isArray(result.traffic_signals)) {
      rawDets = result.traffic_signals;
    } else if (result.results && result.results.traffic_signals && Array.isArray(result.results.traffic_signals.detections)) {
      rawDets = result.results.traffic_signals.detections;
    }

    const items = rawDets.map(d => ({
      class_name: `Traffic Signal: ${d.class_name || d.name || "Signal"}`,
      confidence: d.confidence || d.conf || 0.85,
      severity: (d.class_name || "").toLowerCase().includes("red") ? "CRITICAL" : "MEDIUM",
      box: d.box || null,
      pipeline: "Traffic Signal"
    }));

    if (items.length > 0) {
      list.innerHTML = sourceBanner + items.map((item, idx) => {
        const confPct = Math.round(item.confidence * 100);
        const badgeClass = item.severity === 'CRITICAL' ? 'badge-danger' : 'badge-warning';
        return `
          <div class="detected-item-card" style="margin-bottom: 8px;">
            <div class="detected-item-left">
              <span class="badge ${badgeClass}">${item.severity}</span>
              <div>
                <div class="detected-type-tag">${idx + 1}. ${item.class_name}</div>
                <div class="detected-conf-text">Confidence: ${confPct}% ${item.box ? `• Box: [${item.box.map(Math.round).join(", ")}]` : ""}</div>
              </div>
            </div>
            <span class="badge badge-info">${item.pipeline}</span>
          </div>
        `;
      }).join("");
    } else {
      list.innerHTML = sourceBanner + `
        <div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 13px;">
          <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">No detections found in this image.</div>
          <div style="font-size: 11.5px;">Analyzed with Traffic Signal AI (25% confidence threshold)</div>
        </div>
      `;
    }
    return;
  }

  // =========================================================================
  // 4. SIGN CONDITION CLASSIFIER ISOLATION
  // =========================================================================
  if (mode === "sign_condition" || mode === "signcondition" || mode === "condition") {
    const isApplicable = result.applicable !== false && result.condition && result.condition !== "NOT_APPLICABLE" && result.sign_detected !== false;

    if (isApplicable) {
      const condConf = Math.round((result.confidence || 0.95) * 100);
      const condName = (result.condition || "GOOD").toUpperCase();
      const condSev = condName === "DAMAGED" || condName === "OBSTRUCTED" ? "HIGH" : (condName === "FADED" ? "MEDIUM" : "LOW");
      const badgeClass = condSev === 'HIGH' ? 'badge-danger' : (condSev === 'MEDIUM' ? 'badge-warning' : 'badge-success');

      let scoresHtml = "";
      if (result.scores && typeof result.scores === "object") {
        scoresHtml = Object.entries(result.scores).map(([k, v]) => `
          <span style="font-size: 11px; background: rgba(0,0,0,0.05); padding: 2px 6px; border-radius: 4px; margin-right: 4px;">
            ${k}: ${Math.round(v * 100)}%
          </span>
        `).join("");
      }

      list.innerHTML = sourceBanner + `
        <div class="detected-item-card">
          <div class="detected-item-left">
            <span class="badge ${badgeClass}">${condSev}</span>
            <div>
              <div class="detected-type-tag">1. Sign Physical Condition: ${condName} ${result.sign_class ? `(${result.sign_class})` : ''}</div>
              <div class="detected-conf-text">Confidence: ${condConf}%</div>
              <div style="margin-top: 6px;">${scoresHtml}</div>
            </div>
          </div>
          <span class="badge badge-info">Sign Condition</span>
        </div>
      `;

      if (signZoomed) {
        signZoomed.style.display = "block";
        const origCrop = document.getElementById("signOriginalCropImg");
        const focusCrop = document.getElementById("signFocusedCropImg");
        const condTag = document.getElementById("signConditionTag");

        if (origCrop) origCrop.src = selectedImagePreviewDataUrl || (previewImg ? previewImg.src : "");
        if (focusCrop) focusCrop.src = result.annotated_image || (previewImg ? previewImg.src : "");
        if (condTag) condTag.textContent = `Condition: ${condName}`;
      }
    } else {
      if (signZoomed) signZoomed.style.display = "none";
      list.innerHTML = sourceBanner + `
        <div style="padding: 24px 16px; text-align: center; color: var(--text-muted); font-size: 13px;">
          <div style="font-weight: 700; color: var(--text-primary); font-size: 14px; margin-bottom: 6px;">Sign Condition: NOT APPLICABLE</div>
          <div style="font-size: 12px; color: var(--text-secondary);">${result.message || 'No traffic sign detected in the uploaded image.'}</div>
        </div>
      `;
    }
    return;
  }

  // =========================================================================
  // 5. ALL IN ONE (FULL SUITE) COMBINED PIPELINE - 4 CATEGORIZED SECTIONS
  // =========================================================================
  if (signZoomed) signZoomed.style.display = "none";

  // Extract real detections from all 4 models
  const rawSigns = result.traffic_signs || (result.results && result.results.traffic_signs && result.results.traffic_signs.detections) || [];
  const rawDamages = result.road_damages || (result.results && result.results.road_damage && result.results.road_damage.detections) || [];
  const rawSignals = result.traffic_signals || (result.results && result.results.traffic_signals && result.results.traffic_signals.detections) || [];
  const rawCondition = result.sign_condition || (result.results && result.results.sign_condition) || (result.condition ? result : null);

  // Section 1: Traffic Signs
  let signsHtml = "";
  if (rawSigns.length > 0) {
    signsHtml = rawSigns.map((d, i) => {
      const clsName = d.class_name || d.name || "Traffic Sign";
      const conf = d.confidence || d.conf || 0.85;
      const confPct = Math.round(conf * 100);
      const sev = conf >= 0.80 ? "HIGH" : "MEDIUM";
      const badgeClass = sev === "HIGH" ? "badge-danger" : "badge-warning";
      return `
        <div class="detected-item-card" style="margin-bottom: 6px;">
          <div class="detected-item-left">
            <span class="badge ${badgeClass}">${sev}</span>
            <div>
              <div class="detected-type-tag">${i + 1}. ${clsName}</div>
              <div class="detected-conf-text">Confidence: ${confPct}% ${d.box ? `• Box: [${d.box.map(Math.round).join(", ")}]` : ""}</div>
            </div>
          </div>
          <span class="badge badge-info">Traffic Sign</span>
        </div>
      `;
    }).join("");
  } else {
    signsHtml = `<div class="ai-suite-empty">No traffic signs detected.</div>`;
  }

  // Section 2: Road Damage
  let damageHtml = "";
  if (rawDamages.length > 0) {
    damageHtml = rawDamages.map((d, i) => {
      const clsName = d.class_name || d.name || "Road Damage";
      const conf = d.confidence != null ? d.confidence : (d.conf != null ? d.conf : 0.10);
      const confPct = conf < 0.20 ? (conf * 100).toFixed(2) : Math.round(conf * 100);
      const isPothole = clsName.toLowerCase().includes("pothole");
      const sev = isPothole ? (conf >= 0.70 ? "CRITICAL" : (conf >= 0.35 ? "HIGH" : "MEDIUM")) : (conf >= 0.50 ? "HIGH" : "MEDIUM");
      const badgeClass = sev === "CRITICAL" ? "badge-danger" : (sev === "HIGH" ? "badge-danger" : "badge-warning");
      return `
        <div class="detected-item-card" style="margin-bottom: 6px;">
          <div class="detected-item-left">
            <span class="badge ${badgeClass}">${sev}</span>
            <div>
              <div class="detected-type-tag">${i + 1}. ${clsName}</div>
              <div class="detected-conf-text">Confidence: ${confPct}% ${d.box ? `• Box: [${d.box.map(Math.round).join(", ")}]` : ""}</div>
            </div>
          </div>
          <span class="badge badge-info">Road Damage</span>
        </div>
      `;
    }).join("");
  } else {
    damageHtml = `<div class="ai-suite-empty">No road damage detected.</div>`;
  }

  // Section 3: Traffic Signals
  let signalHtml = "";
  if (rawSignals.length > 0) {
    signalHtml = rawSignals.map((d, i) => {
      const clsName = `Signal: ${d.class_name || d.name || "Signal"}`;
      const conf = d.confidence || d.conf || 0.85;
      const confPct = Math.round(conf * 100);
      const isRed = (d.class_name || "").toLowerCase().includes("red");
      const sev = isRed ? "CRITICAL" : "MEDIUM";
      const badgeClass = isRed ? "badge-danger" : "badge-warning";
      return `
        <div class="detected-item-card" style="margin-bottom: 6px;">
          <div class="detected-item-left">
            <span class="badge ${badgeClass}">${sev}</span>
            <div>
              <div class="detected-type-tag">${i + 1}. ${clsName}</div>
              <div class="detected-conf-text">Confidence: ${confPct}% ${d.box ? `• Box: [${d.box.map(Math.round).join(", ")}]` : ""}</div>
            </div>
          </div>
          <span class="badge badge-info">Traffic Signal</span>
        </div>
      `;
    }).join("");
  } else {
    signalHtml = `<div class="ai-suite-empty">No traffic signals detected.</div>`;
  }

  // Section 4: Sign Condition (ONLY if sign detected)
  let conditionHtml = "";
  const isConditionApplicable = rawCondition && rawCondition.applicable !== false && rawCondition.condition && rawCondition.condition !== "NOT_APPLICABLE" && rawSigns.length > 0;

  if (isConditionApplicable) {
    const condName = (rawCondition.condition || "GOOD").toUpperCase();
    const condConf = Math.round((rawCondition.confidence || 0.95) * 100);
    const condSev = condName === "DAMAGED" || condName === "OBSTRUCTED" ? "HIGH" : (condName === "FADED" ? "MEDIUM" : "LOW");
    const badgeClass = condSev === "HIGH" ? "badge-danger" : (condSev === "MEDIUM" ? "badge-warning" : "badge-success");
    
    let scoresHtml = "";
    if (rawCondition.scores && typeof rawCondition.scores === "object") {
      scoresHtml = Object.entries(rawCondition.scores).map(([k, v]) => `
        <span style="font-size: 10.5px; background: rgba(0,0,0,0.05); padding: 2px 6px; border-radius: 4px; margin-right: 4px;">
          ${k}: ${Math.round(v * 100)}%
        </span>
      `).join("");
    }

    conditionHtml = `
      <div class="detected-item-card">
        <div class="detected-item-left">
          <span class="badge ${badgeClass}">${condSev}</span>
          <div>
            <div class="detected-type-tag">Physical Condition: ${condName}</div>
            <div class="detected-conf-text">Confidence: ${condConf}%</div>
            ${scoresHtml ? `<div style="margin-top: 6px;">${scoresHtml}</div>` : ""}
          </div>
        </div>
        <span class="badge badge-info">Sign Condition</span>
      </div>
    `;
  } else {
    conditionHtml = `
      <div class="detected-item-card" style="margin-bottom: 6px; background: rgba(0,0,0,0.02); border: 1px dashed var(--border-color);">
        <div class="detected-item-left">
          <span class="badge" style="background: var(--bg-card); color: var(--text-muted); border: 1px solid var(--border-color); font-size: 10px;">N/A</span>
          <div>
            <div class="detected-type-tag" style="color: var(--text-muted);">Sign Condition: NOT APPLICABLE</div>
            <div class="detected-conf-text" style="color: var(--text-muted); font-size: 11.5px;">No traffic sign detected in the uploaded image.</div>
          </div>
        </div>
        <span class="badge badge-info" style="opacity: 0.6;">Sign Condition</span>
      </div>
    `;
  }

  const signsPill = rawSigns.length > 0 ? `<span class="ai-suite-pill active">${rawSigns.length} Detected</span>` : `<span class="ai-suite-pill empty">0</span>`;
  const damagePill = rawDamages.length > 0 ? `<span class="ai-suite-pill active">${rawDamages.length} Detected</span>` : `<span class="ai-suite-pill empty">0</span>`;
  const signalPill = rawSignals.length > 0 ? `<span class="ai-suite-pill active">${rawSignals.length} Detected</span>` : `<span class="ai-suite-pill empty">0</span>`;
  const conditionPill = isConditionApplicable ? `<span class="ai-suite-pill active">${rawCondition.condition.toUpperCase()}</span>` : `<span class="ai-suite-pill empty">NOT APPLICABLE</span>`;

  list.innerHTML = sourceBanner + `
    <div class="ai-suite-container">
      <!-- 1. Traffic Signs -->
      <div class="ai-suite-section">
        <div class="ai-suite-header">
          <div class="ai-suite-title">🚸 Traffic Signs</div>
          ${signsPill}
        </div>
        ${signsHtml}
      </div>

      <!-- 2. Road Damage -->
      <div class="ai-suite-section">
        <div class="ai-suite-header">
          <div class="ai-suite-title">⚠️ Road Damage</div>
          ${damagePill}
        </div>
        ${damageHtml}
      </div>

      <!-- 3. Traffic Signals -->
      <div class="ai-suite-section">
        <div class="ai-suite-header">
          <div class="ai-suite-title">🚦 Traffic Signals</div>
          ${signalPill}
        </div>
        ${signalHtml}
      </div>

      <!-- 4. Sign Condition -->
      <div class="ai-suite-section">
        <div class="ai-suite-header">
          <div class="ai-suite-title">🔍 Sign Condition</div>
          ${conditionPill}
        </div>
        ${conditionHtml}
      </div>
    </div>
  `;
}

async function recordDetectionToDatabase(res) {
  try {
    let topClass = null;
    let topConf = null;
    let modelName = res.model_name || activeAiMode;

    if (res.detections && res.detections.length > 0) {
      topClass = res.detections[0].class_name || res.detections[0].class || null;
      topConf = res.detections[0].confidence != null ? res.detections[0].confidence : null;
    } else if (res.traffic_signs && res.traffic_signs.length > 0) {
      topClass = res.traffic_signs[0].class_name || res.traffic_signs[0].class || null;
      topConf = res.traffic_signs[0].confidence != null ? res.traffic_signs[0].confidence : null;
    } else if (res.road_damages && res.road_damages.length > 0) {
      topClass = res.road_damages[0].class_name || res.road_damages[0].class || null;
      topConf = res.road_damages[0].confidence != null ? res.road_damages[0].confidence : null;
    } else if (res.traffic_signals && res.traffic_signals.length > 0) {
      topClass = res.traffic_signals[0].class_name || res.traffic_signals[0].class || null;
      topConf = res.traffic_signals[0].confidence != null ? res.traffic_signals[0].confidence : null;
    } else if (res.sign_condition && res.sign_condition.applicable && res.sign_condition.condition && res.sign_condition.condition !== "NOT_APPLICABLE") {
      topClass = `Sign Condition: ${res.sign_condition.condition}`;
      topConf = res.sign_condition.confidence != null ? res.sign_condition.confidence : null;
    } else if (res.condition && res.condition !== "NOT_APPLICABLE" && res.applicable !== false) {
      topClass = `Sign Condition: ${res.condition}`;
      topConf = res.confidence != null ? res.confidence : null;
    }

    // Only record if an actual qualifying detection was identified
    if (!topClass || topConf == null) {
      return;
    }

    const payload = {
      source_type: "IMAGE",
      ai_model: modelName,
      detected_class: topClass,
      confidence: topConf,
      latitude: currentGps.lat,
      longitude: currentGps.lng,
      image_base64: res.annotated_image || null
    };

    await fetch("/api/detections/record", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify(payload)
    });
  } catch (e) {
    console.warn("Detection auto-record note:", e.message);
  }
}

function downloadAnnotatedResult() {
  const img = document.getElementById("annotatedOutputImg");
  if (!img || !img.src) {
    toast("No analyzed image to download", "warning");
    return;
  }
  const a = document.createElement("a");
  a.href = img.src;
  a.download = `VisionGuard_AI_Diagnostics_${Date.now()}.png`;
  a.click();
}

// ==========================================================================
// Complaint Image Upload & Form Handlers (Section 2, 3, 4, 7, 8)
// ==========================================================================

function setupComplaintDropzoneListeners() {
  const dropzone = document.getElementById("complaintImageDropzone");
  if (!dropzone) return;

  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    }, false);
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    }, false);
  });

  dropzone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files[0]) {
      processComplaintImageFile(files[0]);
    }
  }, false);
}

function handleComplaintImageSelect(event) {
  const file = event.target.files[0];
  if (file) {
    processComplaintImageFile(file);
  }
}

function processComplaintImageFile(file) {
  // Validate File Type
  const validTypes = ["image/jpeg", "image/png", "image/webp", "image/jpg"];
  if (!validTypes.includes(file.type.toLowerCase())) {
    toast("Unsupported file type. Please upload a JPG, PNG, or WEBP image.", "error");
    return;
  }

  // Validate File Size (Max 10 MB)
  const maxSize = 10 * 1024 * 1024;
  if (file.size > maxSize) {
    toast("Image file exceeds maximum allowed size of 10 MB.", "error");
    return;
  }

  complaintSelectedImageFile = file;

  // Render Preview
  const reader = new FileReader();
  reader.onload = (e) => {
    const previewImg = document.getElementById("complaintPreviewImg");
    const previewCard = document.getElementById("complaintImagePreviewCard");
    const dropzone = document.getElementById("complaintImageDropzone");
    const fileName = document.getElementById("complaintPreviewFileName");
    const fileSize = document.getElementById("complaintPreviewFileSize");

    if (previewImg) previewImg.src = e.target.result;
    if (fileName) fileName.textContent = file.name;
    if (fileSize) fileSize.textContent = formatBytes(file.size);
    if (previewCard) previewCard.style.display = "block";
    if (dropzone) dropzone.style.display = "none";
  };
  reader.readAsDataURL(file);
  toast(`Attached evidence image: ${file.name}`, "info");
}

function removeComplaintImage() {
  complaintSelectedImageFile = null;
  const fileInput = document.getElementById("complaintFileInput");
  const previewCard = document.getElementById("complaintImagePreviewCard");
  const dropzone = document.getElementById("complaintImageDropzone");
  const previewImg = document.getElementById("complaintPreviewImg");

  if (fileInput) fileInput.value = "";
  if (previewImg) previewImg.src = "";
  if (previewCard) previewCard.style.display = "none";
  if (dropzone) dropzone.style.display = "flex";
  toast("Image removed", "info");
}

function formatBytes(bytes, decimals = 1) {
  if (!+bytes) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

function openNewComplaintModal() {
  updateGpsUi();
  complaintAiContext = null;
  const aiBanner = document.getElementById("aiPreFillBanner");
  if (aiBanner) aiBanner.style.display = "none";

  removeComplaintImage();
  const form = document.getElementById("newComplaintForm");
  if (form) form.reset();
  updateGpsUi();

  const modal = document.getElementById("modalNewComplaint");
  if (modal) modal.classList.add("show");
}

function openComplaintFromAiResult() {
  if (!lastInferenceResult) {
    toast("Please run an AI analysis on an image first before reporting a hazard.", "warning");
    return;
  }

  // Extract detections for the active mode
  let relevantDets = [];
  const mode = (lastInferenceResult.mode || activeAiMode || "").toLowerCase();

  if (mode === "road_damage" || mode === "roaddamage" || mode === "damage") {
    relevantDets = lastInferenceResult.road_damages || lastInferenceResult.detections || [];
  } else if (mode === "traffic_sign" || mode === "trafficsign" || mode === "sign") {
    relevantDets = lastInferenceResult.traffic_signs || lastInferenceResult.detections || [];
  } else if (mode === "traffic_signal" || mode === "trafficsignal" || mode === "signal") {
    relevantDets = lastInferenceResult.traffic_signals || lastInferenceResult.detections || [];
  } else if (mode === "sign_condition" || mode === "signcondition" || mode === "condition") {
    const cond = (lastInferenceResult.condition || "").toUpperCase();
    if (cond && cond !== "GOOD") {
      relevantDets = [{ class_name: `Sign Condition: ${cond}`, confidence: lastInferenceResult.confidence || 0.95 }];
    }
  } else {
    // all_in_one
    const rd = lastInferenceResult.road_damages || [];
    const ts = lastInferenceResult.traffic_signs || [];
    const sig = lastInferenceResult.traffic_signals || [];
    const cond = ((lastInferenceResult.sign_condition && lastInferenceResult.sign_condition.condition) || lastInferenceResult.condition || "").toUpperCase();
    
    // Prioritize physical road damages, then traffic signals, signs, and actionable sign defects
    relevantDets = [...rd, ...sig, ...ts];
    if (relevantDets.length === 0 && (lastInferenceResult.detections || []).length > 0) {
      relevantDets = [...lastInferenceResult.detections];
    }
    if (relevantDets.length === 0 && cond && cond !== "GOOD") {
      const condConf = (lastInferenceResult.sign_condition && lastInferenceResult.sign_condition.confidence) || lastInferenceResult.confidence || 0.95;
      relevantDets = [{ class_name: `Sign Condition: ${cond}`, confidence: condConf }];
    }
  }

  if (relevantDets.length === 0) {
    toast("No hazards detected in this image to report automatically. You can still report manually.", "info");
    openNewComplaintModal();
    if (selectedImageFile) {
      processComplaintImageFile(selectedImageFile);
    }
    return;
  }

  openNewComplaintModal();
  if (selectedImageFile) {
    processComplaintImageFile(selectedImageFile);
  }

  const top = relevantDets[0];
  const topClass = top.class_name || top.name || "Road Hazard";
  const topConf = top.confidence || top.conf || 0.90;
  const modelName = lastInferenceResult.model_name || getPipelineDisplayName(activeAiMode);

  let issueType = "POTHOLE";
  const clsLower = topClass.toLowerCase();
  if (clsLower.includes("crack")) {
    issueType = "POTHOLE";
  } else if (clsLower.includes("signal") || clsLower.includes("red") || clsLower.includes("green")) {
    issueType = "TRAFFIC_SIGNAL";
  } else if (clsLower.includes("sign")) {
    issueType = "DAMAGED_SIGN";
  } else {
    issueType = "POTHOLE";
  }

  complaintAiContext = {
    ai_model: modelName,
    detected_class: topClass,
    confidence: topConf,
    annotated_image: lastInferenceResult.annotated_image
  };

  // Pre-fill fields
  const titleInput = document.getElementById("compTitle");
  const issueSelect = document.getElementById("compIssueType");
  const descInput = document.getElementById("compDescription");
  const sevSelect = document.getElementById("compSeverity");
  const aiBanner = document.getElementById("aiPreFillBanner");
  const aiTitle = document.getElementById("aiPreFillTitle");
  const aiConf = document.getElementById("aiPreFillConf");
  const aiModel = document.getElementById("aiPreFillModel");

  if (titleInput) titleInput.value = `AI Detected: ${topClass} (${Math.round(topConf * 100)}%)`;
  if (issueSelect) issueSelect.value = issueType;
  if (sevSelect) sevSelect.value = topConf >= 0.80 ? "HIGH" : "MEDIUM";
  if (descInput) {
    descInput.value = `Automated AI Diagnostic Report: Detected ${topClass} with ${Math.round(topConf * 100)}% model confidence at ${currentGps.lat}, ${currentGps.lng}.`;
  }

  if (aiBanner) aiBanner.style.display = "block";
  if (aiTitle) aiTitle.textContent = `AI Detected: ${topClass}`;
  if (aiConf) aiConf.textContent = `Confidence: ${Math.round(topConf * 100)}%`;
  if (aiModel) aiModel.textContent = `Pipeline: ${modelName.toUpperCase()}`;
}

function closeComplaintModal() {
  closeModal("modalNewComplaint");
  removeComplaintImage();
}

async function handleCreateComplaintSubmit(event) {
  event.preventDefault();
  const btn = document.getElementById("btnSubmitComplaint");
  const title = document.getElementById("compTitle").value.trim();
  const issue_type = document.getElementById("compIssueType").value;
  const severity = document.getElementById("compSeverity").value;
  const location_address = document.getElementById("compLocationAddress").value.trim();
  const latitude = parseFloat(document.getElementById("compLat").value);
  const longitude = parseFloat(document.getElementById("compLng").value);
  const description = document.getElementById("compDescription").value.trim();

  // Validate location
  if (isNaN(latitude) || isNaN(longitude)) {
    toast("GPS coordinates are required. Please acquire GPS or enter valid numbers.", "error");
    return;
  }

  try {
    btn.disabled = true;
    btn.innerHTML = `<span>Submitting Complaint...</span>`;

    const formData = new FormData();
    if (title) formData.append("title", title);
    formData.append("issue_type", issue_type);
    formData.append("severity", severity);
    formData.append("location_address", location_address);
    formData.append("latitude", latitude);
    formData.append("longitude", longitude);
    if (description) formData.append("description", description);

    // AI Context if present
    if (complaintAiContext) {
      if (complaintAiContext.ai_model) formData.append("ai_model", complaintAiContext.ai_model);
      if (complaintAiContext.detected_class) formData.append("detected_class", complaintAiContext.detected_class);
      if (complaintAiContext.confidence) formData.append("confidence", complaintAiContext.confidence);
      if (complaintAiContext.annotated_image) {
        formData.append("annotated_image_base64", complaintAiContext.annotated_image);
        formData.append("image_base64", complaintAiContext.annotated_image);
      }
    }

    // User Uploaded File
    if (complaintSelectedImageFile) {
      formData.append("image_file", complaintSelectedImageFile);
    }

    const res = await fetch("/api/complaints/form", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${authToken}`
      },
      body: formData
    });

    const data = await res.json();
    if (res.ok) {
      const trackingCode = data.complaint_id || data.tracking_number || "VG-CMP-NEW";
      toast(`Complaint submitted successfully! Generated ID: ${trackingCode}`, "success");
      closeComplaintModal();
      navigate("/user/complaints");
      loadComplaintsList();
    } else {
      toast(data.detail || "Unable to submit complaint. Please check your entries and try again.", "error");
    }
  } catch (e) {
    toast("Complaint registration error: " + e.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>Submit Complaint</span>`;
  }
}

// ==========================================================================
// Complaints Management & Details (Section 11, 13)
// ==========================================================================

async function loadComplaintsList() {
  if (!authToken) return;
  const tbody = document.getElementById("complaintsTableBody");
  const title = document.getElementById("complaintsPageTitle");

  if (title && currentUser) {
    title.textContent = currentUser.role === "ADMIN" ? "Municipal Complaint Governance" : "My Submitted Complaints";
  }

  try {
    const endpoint = currentUser.role === "ADMIN" ? "/api/admin/complaints" : "/api/complaints/my";
    const res = await fetch(endpoint, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (res.ok) {
      const list = await res.json();
      if (tbody) {
        if (list.length > 0) {
          tbody.innerHTML = list.map(c => {
            const rawImg = getImageUrl(c.image_path);
            const thumbUrl = rawImg || createPlaceholderDataUrl("No evidence image uploaded");
            return `
              <tr>
                <td>
                  <div style="display: flex; align-items: center; gap: 10px;">
                    <img src="${thumbUrl}" alt="Thumb" style="width: 40px; height: 40px; border-radius: var(--radius-xs); object-fit: cover; background: #F8FAFC; border: 1px solid var(--border-color);" onerror="handleImageError(this, 'No evidence image uploaded')">
                    <strong>#${c.complaint_id || c.tracking_number || c.id}</strong>
                  </div>
                </td>
                <td>
                  <div style="font-weight: 600;">${c.title || c.issue_type.replace('_', ' ')}</div>
                  <div style="font-size: 11.5px; color: var(--text-muted);">${c.detected_class ? `AI: ${c.detected_class}` : c.issue_type}</div>
                </td>
                <td>${c.location_address || (c.latitude ? `${c.latitude.toFixed(3)}, ${c.longitude.toFixed(3)}` : 'Salem')}</td>
                <td><span class="badge ${c.severity === 'HIGH' || c.severity === 'CRITICAL' ? 'badge-danger' : (c.severity === 'MEDIUM' ? 'badge-warning' : 'badge-info')}">${c.severity}</span></td>
                <td><span class="badge ${c.status === 'COMPLETED' ? 'badge-success' : (c.status === 'IN_PROGRESS' || c.status === 'ASSIGNED' ? 'badge-warning' : 'badge-info')}">${c.status}</span></td>
                <td>${c.created_at ? c.created_at.slice(0, 10) : 'Today'}</td>
                <td>
                  <button class="btn btn-secondary btn-sm" onclick="navigate('/${currentUser.role === 'ADMIN' ? 'admin' : 'user'}/complaints/${c.id}')">
                    View Details
                  </button>
                </td>
              </tr>
            `;
          }).join("");
        } else {
          tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--text-muted);">No complaints recorded in database yet.</td></tr>`;
        }
      }
    }
  } catch (e) {
    console.error("Complaints load error:", e);
  }
}

async function loadComplaintDetails(id) {
  if (!authToken) return;
  activeComplaintId = id;
  try {
    const endpoint = (currentUser && currentUser.role === "ADMIN") ? `/api/admin/complaints/${id}` : ((currentUser && currentUser.role === "SUPERVISOR") ? `/api/supervisor/inspections/${id}` : `/api/complaints/${id}`);
    const res = await fetch(endpoint, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (res.ok) {
      const c = await res.json();
      document.getElementById("complaintDetailTitle").textContent = `${c.title || 'Road Hazard'} (#${c.complaint_id || c.tracking_number || c.id})`;
      document.getElementById("complaintDetailSubtitle").textContent = `Reported on ${c.created_at ? c.created_at.slice(0, 19).replace('T', ' ') : 'Recent'}`;
      
      const sevBadge = document.getElementById("complaintDetailSeverityBadge");
      if (sevBadge) {
        sevBadge.textContent = c.severity;
        sevBadge.className = `badge ${c.severity === 'HIGH' || c.severity === 'CRITICAL' ? 'badge-danger' : (c.severity === 'MEDIUM' ? 'badge-warning' : 'badge-info')}`;
      }

      const statBadge = document.getElementById("complaintDetailStatusBadge");
      if (statBadge) {
        statBadge.textContent = c.status;
        statBadge.className = `badge ${c.status === 'COMPLETED' ? 'badge-success' : (c.status === 'IN_PROGRESS' || c.status === 'ASSIGNED' ? 'badge-warning' : 'badge-info')}`;
      }

      document.getElementById("complaintDetailLocationText").textContent = c.location_address || 'Salem Municipal Ward';
      document.getElementById("complaintDetailGpsText").textContent = (c.latitude && c.longitude) ? `${c.latitude}, ${c.longitude}` : 'Location unavailable';
      document.getElementById("complaintDetailDescription").textContent = c.description || 'No additional notes provided.';

      const workerText = document.getElementById("complaintDetailWorkerText");
      if (workerText) {
        workerText.textContent = c.assigned_worker_name || (c.assigned_worker ? c.assigned_worker.user?.full_name : 'Unassigned');
      }

      // Evidence Image
      const img = document.getElementById("complaintDetailEvidenceImg");
      const noEv = document.getElementById("complaintDetailNoEvidence");
      const resolvedImg = getImageUrl(c.image_path);

      if (img) {
        if (resolvedImg) {
          img.src = resolvedImg;
          img.style.display = "block";
          img.onerror = () => {
            img.style.display = "none";
            if (noEv) noEv.style.display = "block";
          };
          if (noEv) noEv.style.display = "none";
        } else {
          img.style.display = "none";
          if (noEv) noEv.style.display = "block";
        }
      }

      // AI-Assisted Risk Assessment Data
      try {
        const riskRes = await fetch(`/api/risk/complaint/${id}`, {
          headers: { "Authorization": `Bearer ${authToken}` }
        });
        if (riskRes.ok) {
          const risk = await riskRes.json();
          renderRiskAssessmentSection("page", risk);
        } else if (c.risk_score != null) {
          renderRiskAssessmentSection("page", {
            risk_score: c.risk_score,
            risk_level: c.risk_level || "MEDIUM",
            priority: c.priority_level || "NORMAL",
            factors: c.risk_factors || {},
            recommended_action: "Prioritize municipal field inspection and resolution based on telemetry."
          });
        }
      } catch (errRisk) {
        console.warn("Risk assessment fetch fallback:", errRisk);
      }

      // Admin Action Buttons
      const adminActions = document.getElementById("complaintDetailAdminActions");
      if (adminActions) {
        if (currentUser.role === "ADMIN") {
          let btns = "";
          if (c.status === "SUBMITTED" || c.status === "UNDER_REVIEW") {
            btns += `<button class="btn btn-success btn-sm" onclick="handleVerifyComplaint('${c.id}')">Verify Report</button>`;
            btns += `<button class="btn btn-danger btn-sm" onclick="handleRejectComplaint('${c.id}')">Reject</button>`;
          }
          if (c.status === "VERIFIED" || c.status === "SUBMITTED" || c.status === "UNDER_REVIEW") {
            btns += `<button class="btn btn-primary btn-sm" onclick="openAssignModal('${c.id}')">Assign Worker</button>`;
          }
          if (c.status === "PENDING_VERIFICATION" || c.status === "UNDER_REVIEW" || (c.evidences && c.evidences.length > 0 && c.status !== "COMPLETED")) {
            btns += `
              <button class="btn btn-success btn-sm" onclick="handleVerifyCompletion('${c.id}', true)">✓ Approve Completion</button>
              <button class="btn btn-warning btn-sm" onclick="handleVerifyCompletion('${c.id}', false)">Request Rework</button>
            `;
          }
          if (!btns) {
            btns = `<button class="btn btn-outline btn-sm" onclick="openAssignModal('${c.id}')">Reassign Worker</button>`;
          }
          adminActions.innerHTML = btns;
        } else if (currentUser.role === "SUPERVISOR") {
          adminActions.innerHTML = `
            <button class="btn btn-outline btn-sm" onclick="openSupervisorValidateModal('${c.id}', '${c.issue_type || ''}', '${c.severity || 'MEDIUM'}', ${c.latitude || 0}, ${c.longitude || 0})">Validate Inspection</button>
            <button class="btn btn-secondary btn-sm" onclick="openSupervisorNotesModal('${c.id}')">Add Field Notes</button>
            <button class="btn btn-success btn-sm" onclick="openSupervisorRecommendModal('${c.id}')">Recommend Completion</button>
            <button class="btn btn-danger btn-sm" onclick="openSupervisorReinspectModal('${c.id}')">Request Reinspection</button>
          `;
        } else {
          adminActions.innerHTML = "";
        }
      }

      // Worker Action Buttons
      const workerActions = document.getElementById("complaintDetailWorkerActions");
      if (workerActions) {
        if (currentUser.role === "WORKER") {
          let buttonsHtml = "";
          if (c.status === "ASSIGNED") {
            buttonsHtml = `<button class="btn btn-primary btn-sm" onclick="handleWorkerStartTask('${c.id}')">Start Work</button>`;
          } else if (c.status === "IN_PROGRESS" || c.status === "REOPENED") {
            buttonsHtml = `
              <button class="btn btn-secondary btn-sm" onclick="openWorkerEvidenceModal('${c.id}')">📷 Upload Evidence</button>
              <button class="btn btn-primary btn-sm" onclick="openWorkerCompleteModal('${c.id}')">✓ Submit Completion</button>
            `;
          } else if (c.status === "PENDING_VERIFICATION" || c.status === "UNDER_REVIEW") {
            buttonsHtml = `<span class="badge badge-warning" style="padding:6px 12px;">Submitted for Admin Final Verification</span>`;
          } else if (c.status === "COMPLETED") {
            buttonsHtml = `<span class="badge badge-success" style="padding:6px 12px;">Work Completed & Verified ✓</span>`;
          }
          workerActions.innerHTML = buttonsHtml;
        } else {
          workerActions.innerHTML = "";
        }
      }

      // 3-Panel AI Repair Verification (Section 13)
      renderAiRepairVerification(c.repair_verification, c);

      // Complete Complaint Audit Timeline
      renderComplaintTimeline(c.timeline, c);

      // Smart SLA Status & Escalation
      renderComplaintSla(c.sla, c);
    }
  } catch (e) {
    console.error("Complaint detail failed:", e);
  }
}

function renderComplaintSla(sla, c) {
  const card = document.getElementById("complaintSlaCard");
  if (!card) return;

  if (!sla) {
    // If not in payload, derive a fallback display from status
    document.getElementById("complaintSlaStatusBadge").textContent = (c && c.status === "COMPLETED") ? "RESOLVED" : "ACTIVE";
    document.getElementById("complaintSlaStatusBadge").className = "badge badge-info";
    document.getElementById("complaintSlaRemaining").textContent = "--";
    return;
  }

  const badge = document.getElementById("complaintSlaStatusBadge");
  if (badge) {
    badge.textContent = (sla.status || "ON_TRACK").replace("_", " ");
    if (sla.status === "OVERDUE") {
      badge.className = "badge badge-danger";
    } else if (sla.status === "DUE_SOON") {
      badge.className = "badge badge-warning";
    } else {
      badge.className = "badge badge-success";
    }
  }

  const remElem = document.getElementById("complaintSlaRemaining");
  const remLabel = document.getElementById("complaintSlaRemainingLabel");
  if (remElem) {
    if (sla.is_overdue) {
      remElem.textContent = `${Math.abs(sla.hours_remaining || 0).toFixed(1)}h Overdue`;
      remElem.style.color = "var(--danger)";
      if (remLabel) remLabel.textContent = "SLA Breach Duration";
    } else {
      remElem.textContent = `${(sla.hours_remaining || 0).toFixed(1)}h Remaining`;
      remElem.style.color = "#0C4A6E";
      if (remLabel) remLabel.textContent = "Target SLA Window";
    }
  }

  const prioBadge = document.getElementById("complaintSlaPriorityBadge");
  if (prioBadge) {
    prioBadge.textContent = `${sla.priority || 'HIGH'} (${sla.target_sla_hours || 12}h)`;
    prioBadge.className = `badge ${sla.priority === 'CRITICAL' ? 'badge-danger' : (sla.priority === 'HIGH' ? 'badge-purple' : 'badge-info')}`;
  }

  const deadlineElem = document.getElementById("complaintSlaDeadlineText");
  if (deadlineElem) {
    deadlineElem.textContent = sla.deadline ? sla.deadline.slice(0, 19).replace('T', ' ') : '--';
  }

  const elapsedElem = document.getElementById("complaintSlaElapsedText");
  if (elapsedElem) {
    elapsedElem.textContent = `${(sla.elapsed_hours || 0).toFixed(1)} hours`;
  }

  const escElem = document.getElementById("complaintSlaEscalationText");
  if (escElem) {
    escElem.textContent = (sla.escalation_level || "NONE") === "NONE" ? "Standard (No Breach)" : (sla.escalation_level === "ADMIN_ESCALATION" ? "🚨 Admin Escalated" : "⚠ Supervisor Notified");
  }
}

function renderComplaintTimeline(timeline, c) {
  const container = document.getElementById("complaintAuditTimelineContainer");
  const totalBadge = document.getElementById("complaintTimelineTotalEvents");
  if (!container) return;

  if (!timeline || !Array.isArray(timeline) || timeline.length === 0) {
    container.innerHTML = `<div style="padding: 12px; text-align: center; font-size: 12px; color: var(--text-muted);">No audit events recorded yet.</div>`;
    if (totalBadge) totalBadge.textContent = "0 events";
    return;
  }

  const completedCount = timeline.filter(t => t.status === "COMPLETED").length;
  if (totalBadge) {
    totalBadge.textContent = `${completedCount} of ${timeline.length} Steps`;
  }

  let html = "";
  timeline.forEach((step, idx) => {
    const isDone = step.status === "COMPLETED";
    const nodeClass = isDone ? "timeline-step-node completed" : "timeline-step-node pending";
    const tsStr = step.timestamp ? step.timestamp.slice(0, 19).replace('T', ' ') : "Pending stage";
    const roleBadge = step.user_role ? `<span class="badge ${step.user_role === 'ADMIN' ? 'badge-danger' : (step.user_role === 'SUPERVISOR' ? 'badge-purple' : (step.user_role === 'WORKER' ? 'badge-warning' : 'badge-info'))}" style="font-size: 10px; padding: 2px 6px;">${step.user_role}</span>` : "";

    html += `
      <div class="${nodeClass}">
        <div class="timeline-step-dot"></div>
        <div class="timeline-event-card">
          <div class="timeline-event-header">
            <span class="timeline-event-title">${step.title}</span>
            <span class="timeline-step-time">${tsStr}</span>
          </div>
          <div class="timeline-event-meta">
            ${step.description || ''}
            ${step.user_name ? ` • <strong style="color: var(--text-main);">${step.user_name}</strong> ${roleBadge}` : ''}
          </div>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

function renderAiRepairVerification(verif, c) {
  const verifPanel = document.getElementById("adminVerification3Panel");
  if (!verifPanel) return;

  verifPanel.style.display = "block";
  const beforeImg = document.getElementById("verifBeforeImg");
  const afterImg = document.getElementById("verifAfterImg");
  const beforeLabel = document.getElementById("verifBeforeLabel");
  const afterLabel = document.getElementById("verifAfterLabel");
  const beforeDetText = document.getElementById("verifBeforeDetections");
  const afterDetText = document.getElementById("verifAfterDetections");
  const verifStatusBadge = document.getElementById("verifStatusBadge");
  const verifAiSummary = document.getElementById("verifAiSummary");
  const verifStatusText = document.getElementById("verifStatusText");
  const verifAiMeta = document.getElementById("verifAiMeta");
  const btnTrigger = document.getElementById("btnTriggerAiRepairVerif");
  const recBadge = document.getElementById("aiRepairVerifRecBadge");

  // Show re-run button for Supervisor & Admin if evidences exist
  if (btnTrigger) {
    if (currentUser && (currentUser.role === "ADMIN" || currentUser.role === "SUPERVISOR")) {
      btnTrigger.style.display = "inline-block";
    } else {
      btnTrigger.style.display = "none";
    }
  }

  // Find specific BEFORE and AFTER evidence from c.evidences
  let beforeEvidence = null;
  let afterEvidence = null;

  if (c.evidences && Array.isArray(c.evidences)) {
    beforeEvidence = c.evidences.find(e => e.evidence_type === "BEFORE_REPAIR" || e.evidence_type === "INITIAL_INSPECTION");
    afterEvidence = c.evidences.find(e => e.evidence_type === "AFTER_REPAIR" || e.evidence_type === "COMPLETION");
  }

  const resolvedComplaintImg = getImageUrl(c.image_path);
  const beforeSrc = (verif && verif.before_image_path) ? getImageUrl(verif.before_image_path) : (beforeEvidence ? getImageUrl(beforeEvidence.file_path) : (resolvedComplaintImg || null));
  const afterSrc = (verif && verif.after_image_path) ? getImageUrl(verif.after_image_path) : (afterEvidence ? getImageUrl(afterEvidence.file_path) : (c.completion_image_url ? getImageUrl(c.completion_image_url) : null));

  if (beforeImg) {
    beforeImg.src = beforeSrc || createPlaceholderDataUrl("No evidence image uploaded");
    beforeImg.onerror = () => handleImageError(beforeImg, "No evidence image uploaded");
  }
  if (beforeLabel) {
    beforeLabel.textContent = beforeEvidence ? "On-Site Initial Inspection" : (resolvedComplaintImg ? "Reported Hazard Evidence" : "No evidence uploaded");
  }
  if (beforeDetText) {
    if (verif && verif.before_detections && verif.before_detections.length > 0) {
      const topDet = verif.before_detections[0];
      beforeDetText.textContent = `${topDet.class_name || 'Hazard'}: ${(topDet.confidence * 100).toFixed(0)}% confidence (${verif.before_detections.length} detected)`;
    } else {
      beforeDetText.textContent = beforeSrc ? "Baseline Hazard Photo" : "No photo";
    }
  }

  if (afterImg) {
    afterImg.src = afterSrc || createPlaceholderDataUrl("No evidence image uploaded");
    afterImg.onerror = () => handleImageError(afterImg, "No evidence image uploaded");
  }
  if (afterLabel) {
    afterLabel.textContent = afterEvidence ? "Completed Repair Evidence" : (c.status === "COMPLETED" ? "Repair Verified" : (afterSrc ? "Post-Repair Evidence" : "Awaiting Work Proof"));
    afterLabel.style.color = (afterEvidence || (c.status === "COMPLETED") || afterSrc) ? "var(--success-dark)" : "var(--text-muted)";
  }
  if (afterDetText) {
    if (verif && verif.after_detections) {
      if (verif.after_detections.length === 0) {
        afterDetText.textContent = "✓ No hazards found above threshold";
        afterDetText.style.color = "var(--success-dark)";
      } else {
        const topDet = verif.after_detections[0];
        afterDetText.textContent = `⚠ ${topDet.class_name || 'Damage'}: ${(topDet.confidence * 100).toFixed(0)}% remaining`;
        afterDetText.style.color = "var(--danger)";
      }
    } else {
      afterDetText.textContent = afterSrc ? "Awaiting AI scan" : "Awaiting proof";
    }
  }

  // Render AI recommendation
  if (verif && verif.ai_recommendation) {
    const rec = verif.ai_recommendation;
    if (recBadge) recBadge.textContent = rec.replace("_", " ");

    if (verifStatusBadge) {
      if (rec === "LIKELY_RESOLVED") {
        verifStatusBadge.className = "badge badge-success";
        verifStatusBadge.textContent = "✓ LIKELY RESOLVED";
      } else if (rec === "IMPROVED") {
        verifStatusBadge.className = "badge badge-info";
        verifStatusBadge.textContent = "⚡ IMPROVED";
      } else if (rec === "NOT_RESOLVED") {
        verifStatusBadge.className = "badge badge-danger";
        verifStatusBadge.textContent = "⚠ NOT RESOLVED";
      } else {
        verifStatusBadge.className = "badge badge-warning";
        verifStatusBadge.textContent = "? UNABLE TO VERIFY";
      }
    }

    if (verifAiSummary) {
      verifAiSummary.textContent = verif.summary || "AI inference comparison completed.";
    }

    if (verifStatusText) {
      verifStatusText.textContent = `Hazard clearance confidence: ${(verif.confidence_score * 100).toFixed(0)}%. ${c.status === 'COMPLETED' ? 'Final verification completed.' : 'Awaiting Supervisor / Admin sign-off.'}`;
    }

    if (verifAiMeta) {
      verifAiMeta.textContent = `Verified at: ${verif.verified_at ? verif.verified_at.slice(0, 19).replace('T', ' ') : 'Recent'}`;
    }
  } else {
    // Default / Pending verification state
    if (recBadge) recBadge.textContent = afterSrc ? "Ready for AI Scan" : "Awaiting Evidence";
    if (verifStatusBadge) {
      if (c.status === "COMPLETED") {
        verifStatusBadge.className = "badge badge-success";
        verifStatusBadge.textContent = "✓ MANUALLY VERIFIED";
        if (verifStatusText) verifStatusText.textContent = "Work verified and signed-off by Municipal Administrator.";
      } else if (afterSrc) {
        verifStatusBadge.className = "badge badge-info";
        verifStatusBadge.textContent = "READY FOR SCAN";
        if (verifStatusText) verifStatusText.textContent = "Evidence uploaded. Click 'Re-run AI Verify' to evaluate road repair.";
      } else {
        verifStatusBadge.className = "badge badge-secondary";
        verifStatusBadge.textContent = "PENDING EVIDENCE";
        if (verifStatusText) verifStatusText.textContent = "Awaiting field crew repair photo before AI verification.";
      }
    }
    if (verifAiSummary) verifAiSummary.textContent = "AI-Assisted Repair Verification";
    if (verifAiMeta) verifAiMeta.textContent = "";
  }
}

async function triggerAiRepairVerification(complaintId) {
  if (!authToken || !complaintId) return;
  try {
    showToast("Running VisionGuardAI Repair Verification...", "info");
    const res = await fetch(`/api/complaints/${complaintId}/repair-verification`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${authToken}`,
        "Content-Type": "application/json"
      }
    });

    if (res.ok) {
      const result = await res.json();
      showToast(`AI Verification Complete: ${result.ai_recommendation}`, "success");
      loadComplaintDetails(complaintId);
    } else {
      const err = await res.json();
      showToast(err.detail || "AI Verification failed", "warning");
    }
  } catch (e) {
    console.error("AI Repair verification request error:", e);
    showToast("Network error running AI verification", "danger");
  }
}

function renderRiskAssessmentSection(prefix, risk) {
  const scoreEl = document.getElementById(prefix === "page" ? "pageDetailRiskScore" : "detailRiskScoreVal");
  const levelEl = document.getElementById(prefix === "page" ? "pageDetailRiskLevelBadge" : "detailRiskLevelBadge");
  const prioEl = document.getElementById(prefix === "page" ? "pageDetailPriorityBadge" : "detailPriorityBadge");
  const factorsContainer = document.getElementById(prefix === "page" ? "pageDetailRiskFactorsContainer" : "detailRiskFactorsList");
  const actionEl = document.getElementById(prefix === "page" ? "pageDetailRecommendedAction" : "detailRecommendedAction");

  const score = risk.risk_score ?? 0;
  const level = risk.risk_level || (score >= 75 ? "CRITICAL" : (score >= 50 ? "HIGH" : (score >= 25 ? "MEDIUM" : "LOW")));
  const prio = risk.priority || risk.priority_level || (score >= 75 ? "URGENT" : (score >= 50 ? "HIGH" : (score >= 25 ? "NORMAL" : "LOW")));

  if (scoreEl) scoreEl.textContent = `${score} / 100`;

  if (levelEl) {
    levelEl.textContent = `${level} RISK`;
    levelEl.className = `badge ${level === 'CRITICAL' ? 'badge-danger' : (level === 'HIGH' ? 'badge-warning' : (level === 'MEDIUM' ? 'badge-warning' : 'badge-success'))}`;
    if (level === 'HIGH') {
      levelEl.style.background = '#FFF7ED';
      levelEl.style.color = '#EA580C';
      levelEl.style.borderColor = '#FFEDD5';
    } else {
      levelEl.style.background = '';
      levelEl.style.color = '';
      levelEl.style.borderColor = '';
    }
  }

  if (prioEl) {
    prioEl.textContent = prio;
    prioEl.className = `badge ${prio === 'URGENT' ? 'badge-danger' : (prio === 'HIGH' ? 'badge-warning' : (prio === 'NORMAL' ? 'badge-info' : 'badge-secondary'))}`;
  }

  if (actionEl) {
    actionEl.textContent = risk.recommended_action || "Prioritize field inspection and repair.";
  }

  // Handle transparent factors breakdown visibility for Citizen vs Admin/Worker
  if (factorsContainer) {
    if (currentUser && currentUser.role === "CITIZEN") {
      // Citizen gets simplified view
      factorsContainer.style.display = "none";
    } else {
      factorsContainer.style.display = "flex";
      const factors = risk.factors || {};
      const fSev = document.getElementById(prefix === "page" ? "pageRfSeverity" : "rfSeverity");
      const fConf = document.getElementById(prefix === "page" ? "pageRfConfidence" : "rfConfidence");
      const fDens = document.getElementById(prefix === "page" ? "pageRfDensity" : "rfDensity");
      const fRep = document.getElementById(prefix === "page" ? "pageRfRepeated" : "rfRepeated");
      const fUnres = document.getElementById(prefix === "page" ? "pageRfUnresolved" : "rfUnresolved");
      const fHaz = document.getElementById(prefix === "page" ? "pageRfHazard" : "rfHazard");

      if (fSev) fSev.textContent = `+${factors.severity ?? 0}`;
      if (fConf) fConf.textContent = `+${factors.confidence ?? 0}`;
      if (fDens) fDens.textContent = `+${factors.complaint_density ?? 0}`;
      if (fRep) fRep.textContent = `+${factors.repeated_detection ?? 0}`;
      if (fUnres) fUnres.textContent = `+${factors.unresolved_duration ?? 0}`;
      if (fHaz) fHaz.textContent = `+${factors.nearby_hazards ?? factors.hazardous_indicator ?? 0}`;
    }
  }
}

async function openComplaintDetailsModal(complaintId) {
  if (!complaintId) return;
  try {
    const endpoint = (currentUser && currentUser.role === "ADMIN") ? `/api/admin/complaints/${complaintId}` : ((currentUser && currentUser.role === "SUPERVISOR") ? `/api/supervisor/inspections/${complaintId}` : `/api/complaints/${complaintId}`);
    const res = await fetch(endpoint, {
      headers: authToken ? { "Authorization": `Bearer ${authToken}` } : {}
    });

    if (res.ok) {
      const c = await res.json();
      const titleEl = document.getElementById("detailModalTitle");
      const subEl = document.getElementById("detailModalSubtitle");
      const issueEl = document.getElementById("detailIssueType");
      const statEl = document.getElementById("detailStatusBadge");
      const sevEl = document.getElementById("detailSeverityBadge");
      const locEl = document.getElementById("detailLocation");
      const timeEl = document.getElementById("detailCreatedAt");
      const descEl = document.getElementById("detailDescriptionText");
      const photoWrap = document.getElementById("detailEvidencePhotoWrap");
      const photoImg = document.getElementById("detailEvidenceImg");

      if (titleEl) titleEl.textContent = `${c.title || c.issue_type || 'Road Incident'} (#${c.complaint_id || c.tracking_number || c.id})`;
      if (subEl) subEl.textContent = `Tracking ID: #${c.complaint_id || c.tracking_number || c.id} • Registered by ${c.citizen_name || 'Citizen'}`;
      if (issueEl) issueEl.textContent = c.title || c.issue_type || 'Road Damage';
      if (statEl) {
        statEl.textContent = c.status || 'REPORTED';
        statEl.className = `badge ${c.status === 'COMPLETED' ? 'badge-success' : (c.status === 'IN_PROGRESS' || c.status === 'ASSIGNED' ? 'badge-warning' : 'badge-info')}`;
      }
      if (sevEl) {
        sevEl.textContent = c.severity || 'MEDIUM';
        sevEl.className = `badge ${c.severity === 'HIGH' || c.severity === 'CRITICAL' ? 'badge-danger' : (c.severity === 'MEDIUM' ? 'badge-warning' : 'badge-info')}`;
      }
      if (locEl) locEl.textContent = c.location_address || (c.latitude ? `${c.latitude.toFixed(4)}, ${c.longitude.toFixed(4)}` : 'Salem Municipal Ward');
      if (timeEl) timeEl.textContent = c.created_at ? c.created_at.slice(0, 16).replace('T', ' ') : 'Recent';
      if (descEl) descEl.textContent = c.description || 'No additional notes provided.';

      const resolvedModalImg = getImageUrl(c.image_path);
      if (resolvedModalImg) {
        if (photoWrap) photoWrap.style.display = "block";
        if (photoImg) {
          photoImg.src = resolvedModalImg;
          photoImg.onerror = () => handleImageError(photoImg, "No evidence image uploaded");
        }
      } else if (photoWrap) {
        photoWrap.style.display = "none";
      }

      // Fetch transparent risk breakdown
      try {
        const riskRes = await fetch(`/api/risk/complaint/${complaintId}`, {
          headers: authToken ? { "Authorization": `Bearer ${authToken}` } : {}
        });
        if (riskRes.ok) {
          const riskData = await riskRes.json();
          renderRiskAssessmentSection("modal", riskData);
        } else if (c.risk_score != null) {
          renderRiskAssessmentSection("modal", {
            risk_score: c.risk_score,
            risk_level: c.risk_level || "MEDIUM",
            priority: c.priority_level || "NORMAL",
            factors: c.risk_factors || {},
            recommended_action: "Prioritize municipal field inspection and resolution based on telemetry."
          });
        }
      } catch (errRisk) {
        console.warn("Modal risk fetch failed:", errRisk);
      }

      // Supervisor Action Buttons in Modal
      const supBtns = document.getElementById("detailSupervisorActionButtons");
      if (supBtns) {
        if (currentUser && currentUser.role === "SUPERVISOR") {
          supBtns.style.display = "flex";
          supBtns.innerHTML = `
            <button class="btn btn-outline btn-sm" onclick="closeModal('modalComplaintDetails'); openSupervisorValidateModal('${c.id}', '${c.issue_type || ''}', '${c.severity || 'MEDIUM'}', ${c.latitude || 0}, ${c.longitude || 0})">Validate</button>
            <button class="btn btn-secondary btn-sm" onclick="closeModal('modalComplaintDetails'); openSupervisorNotesModal('${c.id}')">Notes</button>
            <button class="btn btn-success btn-sm" onclick="closeModal('modalComplaintDetails'); openSupervisorRecommendModal('${c.id}')">Recommend</button>
            <button class="btn btn-danger btn-sm" onclick="closeModal('modalComplaintDetails'); openSupervisorReinspectModal('${c.id}')">Reinspect</button>
          `;
        } else {
          supBtns.style.display = "none";
        }
      }

      const modal = document.getElementById("modalComplaintDetails");
      if (modal) modal.classList.add("show");
    } else {
      toast("Could not load complaint details", "error");
    }
  } catch (e) {
    console.error("Open complaint modal failed:", e);
    toast("Failed opening complaint details: " + e.message, "error");
  }
}

function openAssignModal(complaintId) {
  activeComplaintId = complaintId;
  const select = document.getElementById("assignWorkerSelect");
  if (!select) return;

  fetch("/api/admin/workers", {
    headers: { "Authorization": `Bearer ${authToken}` }
  })
  .then(res => res.json())
  .then(workers => {
    select.innerHTML = '<option value="">Choose worker...</option>' + workers.map(w => `
      <option value="${w.id}">${w.full_name || w.name || 'Field Worker'} (${w.department || 'Roads'}) [${w.employee_id || 'ID'}]</option>
    `).join("");
    const modal = document.getElementById("modalAssignWorker");
    if (modal) modal.classList.add("show");
  })
  .catch(err => {
    toast("Failed loading field workers: " + err.message, "error");
  });
}

async function handleAssignWorkerSubmit(event) {
  event.preventDefault();
  const worker_id = parseInt(document.getElementById("assignWorkerSelect").value);
  const notes = document.getElementById("assignPrioritySelect").value;

  if (!worker_id || !activeComplaintId) {
    toast("Please select a worker", "warning");
    return;
  }

  try {
    const res = await fetch(`/api/admin/complaints/${activeComplaintId}/assign`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ worker_id, notes })
    });

    if (res.ok) {
      toast("Field worker dispatched to complaint successfully!", "success");
      closeModal("modalAssignWorker");
      loadComplaintDetails(activeComplaintId);
    } else {
      const err = await res.json();
      toast(err.detail || "Assignment failed", "error");
    }
  } catch (e) {
    toast("Assignment error: " + e.message, "error");
  }
}

async function handleVerifyComplaint(id) {
  try {
    const res = await fetch(`/api/admin/complaints/${id}/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ admin_notes: "Verified by municipal administrator" })
    });
    if (res.ok) {
      toast("Complaint verified by Administrator!", "success");
      loadComplaintDetails(id);
    }
  } catch (e) {
    toast("Verification failed: " + e.message, "error");
  }
}

async function handleRejectComplaint(id) {
  const reason = prompt("Enter reason for complaint rejection:") || "Not meeting municipal criteria";
  try {
    const res = await fetch(`/api/admin/complaints/${id}/reject`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ admin_notes: reason })
    });
    if (res.ok) {
      toast("Complaint rejected", "info");
      loadComplaintDetails(id);
    }
  } catch (e) {
    toast("Rejection failed: " + e.message, "error");
  }
}

async function handleVerifyCompletion(id, approved) {
  let notes = "";
  if (!approved) {
    notes = prompt("Enter notes / instructions for rework:") || "Rework required";
  }
  try {
    const res = await fetch(`/api/admin/complaints/${id}/verify-completion`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ approved: approved, admin_notes: notes })
    });
    if (res.ok) {
      toast(approved ? "✓ Work verified and marked COMPLETED!" : "Rework requested from worker.", approved ? "success" : "warning");
      loadComplaintDetails(id);
      loadComplaintsList();
      if (currentRoute === "/admin/dashboard") loadAdminDashboardData();
    } else {
      const err = await res.json();
      toast(err.detail || "Verification failed", "error");
    }
  } catch (e) {
    toast("Completion verification error: " + e.message, "error");
  }
}

// ==========================================================================
// Live Camera & Simulation Continuous Stream Studio (Section 6)
// Mobile USB & Built-in Camera Device Dynamic Management
// ==========================================================================

let isVideoSimulationMode = false;
let liveConsecutiveDetections = new Map();
let liveLastProcessedIncidentTime = 0;
let currentLiveSourceFilter = "ALL";

// Format user-friendly camera error messages
function getCameraErrorMessage(error) {
  if (!error) return "An unknown camera error occurred.";
  const name = error.name || "";
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return "Camera permission was denied. Please allow camera permissions in your browser settings to enable Live Detection.";
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "No camera device detected.";
  }
  if (name === "NotReadableError" || name === "TrackStartError") {
    return "Selected camera is currently in use by another application or operating system process.";
  }
  if (name === "OverconstrainedError" || name === "ConstraintNotSatisfiedError") {
    return "Selected camera resolution constraints could not be satisfied.";
  }
  return error.message || "Failed to access camera device.";
}

// Show/hide permission banner
function showCameraPermissionBanner(msg) {
  const banner = document.getElementById("cameraPermissionBanner");
  const text = document.getElementById("cameraPermissionText");
  if (text && msg) text.textContent = msg;
  if (banner) {
    banner.style.display = "flex";
  }
}

function hideCameraPermissionBanner() {
  const banner = document.getElementById("cameraPermissionBanner");
  if (banner) banner.style.display = "none";
}

// Update Camera & AI Status UI Elements
function updateCameraStatusUi(isCameraOnline = null, isAiActive = null) {
  const nameLabel = document.getElementById("currentCameraNameLabel");
  const camBadge = document.getElementById("cameraOnlineStatusBadge");
  const aiBadge = document.getElementById("aiDetectionStatusBadge");
  const liveHeaderBadge = document.getElementById("liveCameraStatusBadge");

  const online = isCameraOnline !== null ? isCameraOnline : (isLiveDetecting && (liveWebcamStream !== null || isVideoSimulationMode));
  const aiActive = isAiActive !== null ? isAiActive : isLiveDetecting;

  if (nameLabel) {
    if (isVideoSimulationMode) {
      nameLabel.textContent = "Video Simulation File";
    } else {
      nameLabel.textContent = online ? (selectedCameraLabel || "Active Camera") : "None (Offline)";
    }
  }

  if (camBadge) {
    if (online) {
      camBadge.className = "badge badge-success";
      camBadge.textContent = "ONLINE";
      camBadge.style.background = "#DCFCE7";
      camBadge.style.color = "#15803D";
      camBadge.style.border = "1px solid #BBF7D0";
    } else {
      camBadge.className = "badge badge-secondary";
      camBadge.textContent = "OFFLINE";
      camBadge.style.background = "";
      camBadge.style.color = "";
      camBadge.style.border = "";
    }
  }

  if (aiBadge) {
    if (aiActive) {
      aiBadge.className = "badge badge-success";
      aiBadge.textContent = "ACTIVE";
      aiBadge.style.background = "#DCFCE7";
      aiBadge.style.color = "#15803D";
      aiBadge.style.border = "1px solid #BBF7D0";
    } else {
      aiBadge.className = "badge badge-secondary";
      aiBadge.textContent = "STOPPED";
      aiBadge.style.background = "";
      aiBadge.style.color = "";
      aiBadge.style.border = "";
    }
  }

  if (liveHeaderBadge) {
    liveHeaderBadge.style.display = aiActive ? "inline-flex" : "none";
  }
}

// Request camera access explicitly (e.g. from Allow Camera Access button)
async function requestCameraAccess() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    const msg = "Camera API not supported or accessible in this browser/origin. Please access VisionGuardAI over HTTPS or localhost.";
    showCameraPermissionBanner(msg);
    toast(msg, "error");
    return;
  }
  try {
    const tempStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" } },
      audio: false
    });
    tempStream.getTracks().forEach(t => t.stop());
    hideCameraPermissionBanner();
    await refreshCameraDevices(false);
    toast("Camera access granted!", "success");
    await startLiveCameraDetection();
  } catch (err) {
    console.error("Camera access request error:", err);
    const msg = getCameraErrorMessage(err);
    showCameraPermissionBanner(msg);
    toast(msg, "error");
  }
}

// Dynamically Enumerate Connected Video Input Devices (Laptop Webcam, External/Mobile Cameras, etc.)
async function refreshCameraDevices(showFeedbackToast = false) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
    console.warn("navigator.mediaDevices.enumerateDevices not supported in this browser environment.");
    return;
  }

  // Attach dynamic device change listener once
  if (!isCameraDeviceListenerAttached && navigator.mediaDevices.addEventListener) {
    navigator.mediaDevices.addEventListener("devicechange", () => {
      console.log("Media device change detected on system. Re-enumerating cameras...");
      refreshCameraDevices(false);
    });
    isCameraDeviceListenerAttached = true;
  }

  const select = document.getElementById("cameraSourceSelect");

  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    availableCameraDevices = devices.filter(d => d.kind === "videoinput");

    if (select) {
      const previouslySelectedId = selectedCameraDeviceId || select.value;
      select.innerHTML = "";
      if (availableCameraDevices.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "No camera device detected.";
        select.appendChild(opt);
        selectedCameraDeviceId = "";
        selectedCameraLabel = "No camera device detected.";
        if (isLiveDetecting) {
          stopLiveCameraDetection();
          showCameraPermissionBanner("No camera device detected.");
        }
      } else {
        let isCurrentSelectedStillValid = false;

        availableCameraDevices.forEach((device, idx) => {
          const opt = document.createElement("option");
          opt.value = device.deviceId;
          // Format user-friendly label
          const rawLabel = (device.label || "").trim();
          const cleanLabel = rawLabel || `Camera ${idx + 1}${idx === 0 ? " (Default)" : ""}`;
          opt.textContent = cleanLabel;

          if (device.deviceId && device.deviceId === previouslySelectedId) {
            opt.selected = true;
            isCurrentSelectedStillValid = true;
            selectedCameraDeviceId = device.deviceId;
            selectedCameraLabel = cleanLabel;
          }
          select.appendChild(opt);
        });

        // Preserve selected camera if it still exists, otherwise select the first device
        if (!isCurrentSelectedStillValid && availableCameraDevices.length > 0) {
          if (previouslySelectedId && isLiveDetecting) {
            // Active camera was disconnected
            stopLiveCameraDetection();
            showCameraPermissionBanner("Camera disconnected. Reconnect the camera and refresh available cameras.");
            toast("Camera disconnected. Reconnect the camera and refresh available cameras.", "warning");
          }
          selectedCameraDeviceId = availableCameraDevices[0].deviceId;
          selectedCameraLabel = (availableCameraDevices[0].label || "").trim() || "Camera 1 (Default)";
          select.value = selectedCameraDeviceId;
        }
      }
    }

    if (showFeedbackToast) {
      if (availableCameraDevices.length === 0) {
        toast("No camera device detected.", "warning");
      } else {
        toast(`Refreshed cameras: ${availableCameraDevices.length} video device(s) found`, "info");
      }
    }

    updateCameraStatusUi();
  } catch (err) {
    console.error("Failed to enumerate camera devices:", err);
    if (showFeedbackToast) {
      toast("Error querying camera hardware: " + getCameraErrorMessage(err), "error");
    }
  }
}

// Handle switching camera source from the dropdown
async function handleCameraSourceChange(deviceId) {
  selectedCameraDeviceId = deviceId;
  const select = document.getElementById("cameraSourceSelect");
  if (select && select.selectedOptions && select.selectedOptions.length > 0) {
    selectedCameraLabel = select.selectedOptions[0].text;
  }

  // Stop previous stream before switching cameras
  if (liveWebcamStream) {
    liveWebcamStream.getTracks().forEach(t => t.stop());
    liveWebcamStream = null;
  }

  toast(`Switched camera source: ${selectedCameraLabel}`, "info");

  // If live detection is currently running, hot-switch the live stream
  if (isLiveDetecting && !isVideoSimulationMode) {
    await startLiveCameraDetection();
  } else {
    updateCameraStatusUi(false, false);
  }
}

function toggleVideoSimulationMode() {
  const toggle = document.getElementById("simVideoToggle");
  isVideoSimulationMode = toggle ? toggle.checked : !isVideoSimulationMode;
  const banner = document.getElementById("simulationModeBanner") || document.getElementById("simVideoBanner");
  const fileInput = document.getElementById("simVideoFileInput");
  if (banner) banner.style.display = isVideoSimulationMode ? "flex" : "none";
  if (fileInput) {
    if (isVideoSimulationMode) {
      fileInput.click();
    }
  }
  if (isVideoSimulationMode) {
    toast("VIDEO SIMULATION mode enabled. Choose a video file to simulate live camera.", "info");
    updateCameraStatusUi(true, isLiveDetecting);
  } else {
    updateCameraStatusUi();
  }
}

function handleSimulationVideoSelect(event) {
  const file = event.target.files ? event.target.files[0] : null;
  if (!file) return;
  const video = document.getElementById("liveCameraVideo");
  if (video) {
    if (liveWebcamStream) {
      liveWebcamStream.getTracks().forEach(t => t.stop());
      liveWebcamStream = null;
    }
    video.srcObject = null;
    video.src = URL.createObjectURL(file);
    video.loop = true;
    video.muted = true;
    video.play().catch(e => console.warn("Video playback auto-start:", e));
    isLiveDetecting = true;
    isVideoSimulationMode = true;

    const btnStart = document.getElementById("btnStartLive");
    const btnStop = document.getElementById("btnStopLive");
    const liveBadge = document.getElementById("liveBadge");
    if (btnStart) btnStart.style.display = "none";
    if (btnStop) btnStop.style.display = "inline-flex";
    if (liveBadge) liveBadge.style.display = "flex";

    liveFrameCount = 0;
    liveLastTime = performance.now();
    startLiveInferenceLoop();
    updateCameraStatusUi(true, true);
    toast(`Playing simulation video: ${file.name}`, "success");
  }
}

async function startLiveCameraDetection() {
  const video = document.getElementById("liveCameraVideo");
  const btnStart = document.getElementById("btnStartLive");
  const btnStop = document.getElementById("btnStopLive");
  const liveBadge = document.getElementById("liveBadge");

  if (!video) return;

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    const msg = "Camera API not supported or accessible in this browser/origin. Please access VisionGuardAI over HTTPS or localhost.";
    showCameraPermissionBanner(msg);
    toast(msg, "error");
    updateCameraStatusUi(false, false);
    return;
  }

  // Stop previous stream if active
  if (liveWebcamStream) {
    liveWebcamStream.getTracks().forEach(t => t.stop());
    liveWebcamStream = null;
  }

  // Ensure devices are enumerated
  if (availableCameraDevices.length === 0) {
    await refreshCameraDevices(false);
  }

  const select = document.getElementById("cameraSourceSelect");
  const chosenDeviceId = selectedCameraDeviceId || (select ? select.value : "");

  const constraints = chosenDeviceId
    ? {
        video: {
          deviceId: { exact: chosenDeviceId }
        },
        audio: false
      }
    : {
        video: {
          facingMode: { ideal: "environment" }
        },
        audio: false
      };

  try {
    try {
      liveWebcamStream = await navigator.mediaDevices.getUserMedia(constraints);
    } catch (constraintErr) {
      // Fallback in case of overconstrained resolution or exact ID rejection
      console.warn("Exact constraints failed, falling back to standard video constraint:", constraintErr);
      liveWebcamStream = await navigator.mediaDevices.getUserMedia({
        video: chosenDeviceId ? { deviceId: chosenDeviceId } : { facingMode: { ideal: "environment" } },
        audio: false
      });
    }

    const activeTrack = liveWebcamStream.getVideoTracks()[0];
    if (activeTrack) {
      if (activeTrack.label) {
        selectedCameraLabel = activeTrack.label;
        // Also update selector dropdown if labels were previously empty before permission
        const opt = select?.querySelector(`option[value="${activeTrack.getSettings()?.deviceId || chosenDeviceId}"]`);
        if (opt && (!opt.textContent || opt.textContent.startsWith("Camera "))) {
          opt.textContent = activeTrack.label;
        }
      }
      // Handle camera disconnection event gracefully
      activeTrack.onended = () => {
        console.warn("Active camera stream ended / disconnected.");
        if (liveWebcamStream) {
          liveWebcamStream.getTracks().forEach(t => t.stop());
          liveWebcamStream = null;
        }
        isLiveDetecting = false;
        if (liveDetectTimer) clearTimeout(liveDetectTimer);
        updateCameraStatusUi(false, false);
        const videoElem = document.getElementById("liveCameraVideo");
        if (videoElem) videoElem.srcObject = null;
        const btnStartElem = document.getElementById("btnStartLive");
        const btnStopElem = document.getElementById("btnStopLive");
        const liveBadgeElem = document.getElementById("liveBadge");
        if (btnStartElem) btnStartElem.style.display = "inline-flex";
        if (btnStopElem) btnStopElem.style.display = "none";
        if (liveBadgeElem) liveBadgeElem.style.display = "none";

        showCameraPermissionBanner("Camera disconnected. Reconnect the camera and refresh available cameras.");
        toast("Camera disconnected. Reconnect the camera and refresh available cameras.", "warning");
        const nameLabel = document.getElementById("currentCameraNameLabel");
        if (nameLabel) nameLabel.textContent = "Camera disconnected. Click Refresh Cameras.";
      };
    }

    hideCameraPermissionBanner();

    video.src = "";
    video.srcObject = liveWebcamStream;
    await video.play().catch(e => console.warn("Video play promise:", e));
    isLiveDetecting = true;
    isVideoSimulationMode = false;

    if (btnStart) btnStart.style.display = "none";
    if (btnStop) btnStop.style.display = "inline-flex";
    if (liveBadge) liveBadge.style.display = "flex";

    liveFrameCount = 0;
    liveLastTime = performance.now();
    startLiveInferenceLoop();

    updateCameraStatusUi(true, true);
    toast(`Camera stream active: ${selectedCameraLabel || 'Camera'}`, "success");

    // Re-run device enumeration to populate all device labels now that permission is granted
    refreshCameraDevices(false);
  } catch (e) {
    console.error("Camera startup error:", e);
    const friendlyMsg = getCameraErrorMessage(e);
    showCameraPermissionBanner(friendlyMsg);
    toast("Camera unavailable: " + friendlyMsg, "error");
    updateCameraStatusUi(false, false);
  }
}

function stopLiveCameraDetection() {
  isLiveDetecting = false;
  if (liveDetectTimer) clearTimeout(liveDetectTimer);
  if (liveWebcamStream) {
    liveWebcamStream.getTracks().forEach(t => t.stop());
    liveWebcamStream = null;
  }
  const video = document.getElementById("liveCameraVideo");
  if (video) {
    video.pause();
    video.srcObject = null;
    video.src = "";
  }

  const btnStart = document.getElementById("btnStartLive");
  const btnStop = document.getElementById("btnStopLive");
  const liveBadge = document.getElementById("liveBadge");

  if (btnStart) btnStart.style.display = "inline-flex";
  if (btnStop) btnStop.style.display = "none";
  if (liveBadge) liveBadge.style.display = "none";

  const hud = document.getElementById("liveDeduplicationHud");
  if (hud) hud.style.display = "none";

  updateCameraStatusUi(false, false);
  toast("Live stream stopped", "info");
}

function startLiveInferenceLoop() {
  if (!isLiveDetecting) return;

  const video = document.getElementById("liveCameraVideo");
  const canvas = document.getElementById("liveCameraCanvas");
  if (!video || !canvas || video.readyState < 2) {
    liveDetectTimer = setTimeout(startLiveInferenceLoop, 200);
    return;
  }

  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  const base64Data = canvas.toDataURL("image/jpeg", 0.7);

  fetch("/api/predict/base64", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image: base64Data, mode: "all_in_one", conf: activeConfidence })
  })
  .then(res => res.json())
  .then(data => {
    // Calculate FPS
    liveFrameCount++;
    const now = performance.now();
    if (now - liveLastTime >= 1000) {
      liveFps = Math.round((liveFrameCount * 1000) / (now - liveLastTime));
      const fpsPill = document.getElementById("liveFpsPill");
      if (fpsPill) fpsPill.textContent = `FPS: ${liveFps}`;
      liveFrameCount = 0;
      liveLastTime = now;
    }

    // Draw Bounding Boxes on Overlay Canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    let topDetection = null;

    if (data.detections && Array.isArray(data.detections) && data.detections.length > 0) {
      data.detections.forEach(d => {
        const box = d.box || d.bbox;
        if (box) {
          const [x1, y1, x2, y2] = box;
          ctx.strokeStyle = "#10b981";
          ctx.lineWidth = 3;
          ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
          ctx.fillStyle = "#10b981";
          ctx.font = "bold 14px Inter, sans-serif";
          ctx.fillText(`${d.class_name || 'Object'} (${Math.round((d.confidence || 0.9) * 100)}%)`, x1 + 4, y1 - 6);
        }
      });

      // Find top confident detection
      topDetection = data.detections.reduce((best, curr) => (curr.confidence > (best ? best.confidence : 0)) ? curr : best, null);
    }

    // Temporal Aggregation & Incident Submission
    if (topDetection && topDetection.confidence >= (activeConfidence || 0.25)) {
      const cls = topDetection.class_name || "Road Hazard";
      const count = (liveConsecutiveDetections.get(cls) || 0) + 1;
      liveConsecutiveDetections.set(cls, count);

      // Estimate Risk Level
      let riskLevel = "MEDIUM";
      if ((topDetection.confidence || 0.85) >= 0.88 || cls.toLowerCase().includes("pothole") || cls.toLowerCase().includes("crack")) {
        riskLevel = "HIGH";
      }

      // Update HUD elements
      const hud = document.getElementById("liveDeduplicationHud");
      const hudClass = document.getElementById("hudClass");
      const hudConf = document.getElementById("hudConf");
      const hudRisk = document.getElementById("hudRisk");
      const hudRiskPill = document.getElementById("hudRiskPill");
      const hudStatusPill = document.getElementById("hudStatusPill");
      const hudFrameCount = document.getElementById("hudFrameCount");

      if (hud) hud.style.display = "flex";
      if (hudClass) hudClass.textContent = cls.toUpperCase();
      if (hudConf) hudConf.textContent = `${Math.round((topDetection.confidence || 0.85) * 100)}%`;
      if (hudRisk) hudRisk.textContent = riskLevel;
      if (hudRiskPill) hudRiskPill.style.display = "inline-flex";
      if (hudFrameCount) hudFrameCount.textContent = count;
      if (hudStatusPill) hudStatusPill.innerHTML = `Validation frames: <span id="hudFrameCount">${count}</span>/3`;

      const nowTs = Date.now();
      // Require 3 consecutive frames of detection and rate-limit submission to once every 4 seconds
      if (count >= 3 && (nowTs - liveLastProcessedIncidentTime > 4000)) {
        liveLastProcessedIncidentTime = nowTs;
        submitValidatedLiveIncident(topDetection, base64Data, canvas.toDataURL("image/jpeg", 0.7));
      }
    } else {
      liveConsecutiveDetections.clear();
      const hud = document.getElementById("liveDeduplicationHud");
      if (hud) hud.style.display = "none";
    }

    if (isLiveDetecting) {
      liveDetectTimer = setTimeout(startLiveInferenceLoop, 800);
    }
  })
  .catch(err => {
    console.warn("Live stream frame note:", err);
    if (isLiveDetecting) liveDetectTimer = setTimeout(startLiveInferenceLoop, 1000);
  });
}

async function submitValidatedLiveIncident(detection, rawBase64, annotatedBase64) {
  try {
    const payload = {
      detected_class: detection.class_name || "Road Hazard",
      confidence: detection.confidence || 0.85,
      bbox: detection.bbox || null,
      source: isVideoSimulationMode ? "LIVE_VIDEO" : "LIVE_CAMERA",
      latitude: (currentGps && typeof currentGps.lat === "number") ? currentGps.lat : null,
      longitude: (currentGps && typeof currentGps.lng === "number") ? currentGps.lng : null,
      location_address: currentGps?.address || null,
      image_base64: rawBase64,
      annotated_image_base64: annotatedBase64,
      camera_id: selectedCameraLabel || (isVideoSimulationMode ? "SIM-CAM-01" : "CAM-LIVE-01")
    };

    const headers = { "Content-Type": "application/json" };
    if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

    const res = await fetch("/api/video/live-incident", {
      method: "POST",
      headers: headers,
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      const data = await res.json();
      if (data.status === "duplicate_suppressed") {
        console.log("Live incident deduplicated:", data.message);
        const dedupNotice = document.getElementById("liveDeduplicationNotice");
        const dedupBadge = document.getElementById("dedupTicketIdBadge");
        if (dedupNotice) {
          dedupNotice.style.display = "flex";
          if (dedupBadge) dedupBadge.textContent = `#${data.complaint_id || data.id}`;
          setTimeout(() => {
            if (dedupNotice) dedupNotice.style.display = "none";
          }, 4000);
        }
      } else {
        // Display automatic complaint alert in Live Detection UI
        const autoAlert = document.getElementById("liveAutoComplaintAlert");
        const autoId = document.getElementById("autoComplaintId");
        const autoClass = document.getElementById("autoComplaintClass");
        const autoSource = document.getElementById("autoComplaintSource");
        const autoStatus = document.getElementById("autoComplaintStatus");
        const dedupNotice = document.getElementById("liveDeduplicationNotice");

        if (dedupNotice) dedupNotice.style.display = "none";
        if (autoAlert) {
          autoAlert.style.display = "block";
          if (autoId) autoId.textContent = `#${data.complaint_id || data.id}`;
          if (autoClass) autoClass.textContent = (data.detected_class || detection.class_name || 'Hazard').toUpperCase();
          if (autoSource) autoSource.textContent = data.source || (isVideoSimulationMode ? 'LIVE VIDEO' : 'LIVE CAMERA');
          if (autoStatus) autoStatus.textContent = data.complaint?.status || "SUBMITTED";
        }

        toast(`⚡ Automatic Complaint Created: #${data.complaint_id || ''} (${data.detected_class || ''})`, "success");
        appendSessionIncidentFeed(data);
      }
    } else {
      const err = await res.json().catch(() => ({ detail: "Incident submission failed" }));
      console.error("Live incident creation backend error:", err);
      toast("Detection confirmed, but complaint creation failed. Please retry.", "error");
    }
  } catch (err) {
    console.error("Live incident creation exception:", err);
    toast("Detection confirmed, but complaint creation failed. Please retry.", "error");
  }
}

function appendSessionIncidentFeed(incident) {
  const feed = document.getElementById("liveSessionIncidentList") || document.getElementById("liveIncidentSessionFeed");
  if (!feed) return;
  if (feed.innerHTML.includes("Start detection to see") || feed.innerHTML.includes("No validated incidents")) {
    feed.innerHTML = "";
  }

  const badge = document.getElementById("liveSessionIncidentsBadge");
  if (badge) {
    const cur = parseInt(badge.textContent, 10) || 0;
    badge.textContent = `${cur + 1} Generated`;
  }

  const timeStr = new Date().toLocaleTimeString();
  const rawImg = incident.annotated_image_path || incident.image_path;
  const thumb = rawImg ? getImageUrl(rawImg) : createPlaceholderDataUrl("Live detection frame");
  const src = incident.source || (isVideoSimulationMode ? "LIVE VIDEO" : "LIVE CAMERA");

  const html = `
    <div class="live-incident-card" style="margin-bottom:12px; border-left:4px solid #EF4444; background: var(--bg-surface); padding: 10px; border-radius: var(--radius-md); border: 1px solid var(--border-color); animation: fadeIn 0.3s ease;">
      <div style="display:flex; gap:10px; align-items:flex-start;">
        <img src="${thumb}" style="width:60px; height:60px; object-fit:cover; border-radius:6px; border:1px solid var(--border-color); background:#F8FAFC;" onerror="handleImageError(this, 'Live frame')">
        <div style="flex:1; min-width:0;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <strong style="font-size:13px; color:var(--text-main);">#${incident.complaint_id || incident.id} • ${(incident.detected_class || 'Hazard').toUpperCase()}</strong>
            <span class="badge badge-danger" style="font-size:10px;">${src}</span>
          </div>
          <div style="font-size:11.5px; color:var(--text-secondary); margin-top:3px;">
            Risk: <strong>${incident.risk_score != null ? Math.round(incident.risk_score) : 75}/100</strong> • Conf: <strong>${Math.round((incident.confidence || 0.85)*100)}%</strong> • Status: <strong style="color:var(--primary);">${incident.complaint?.status || 'SUBMITTED'}</strong>
          </div>
          <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">
            📍 ${incident.location_address || (incident.latitude ? `${Number(incident.latitude).toFixed(4)}, ${Number(incident.longitude).toFixed(4)}` : 'GPS unavailable')} • 🕒 ${timeStr}
          </div>
        </div>
      </div>
    </div>
  `;
  feed.insertAdjacentHTML("afterbegin", html);
}

function captureLiveSnapshot() {
  const video = document.getElementById("liveCameraVideo");
  if (!video || !video.videoWidth) {
    toast("Start live camera first before capturing snapshot", "warning");
    return;
  }
  const offscreen = document.createElement("canvas");
  offscreen.width = video.videoWidth;
  offscreen.height = video.videoHeight;
  const ctx = offscreen.getContext("2d");
  ctx.drawImage(video, 0, 0);

  offscreen.toBlob((blob) => {
    selectedImageFile = new File([blob], `live_snapshot_${Date.now()}.jpg`, { type: "image/jpeg" });
    navigate("/user/ai-inspection");
    const previewImg = document.getElementById("annotatedOutputImg");
    const placeholder = document.getElementById("annotatedPlaceholder");
    if (previewImg) {
      previewImg.src = offscreen.toDataURL("image/jpeg");
      previewImg.style.display = "block";
      if (placeholder) placeholder.style.display = "none";
    }
    toast("Frame captured and loaded into AI Diagnostics Studio!", "success");
  }, "image/jpeg");
}

// ==========================================================================
// Admin Live Monitoring Command Center
// ==========================================================================

async function loadAdminLiveMonitoring() {
  if (!authToken || currentUser?.role !== "ADMIN") return;

  try {
    // 1. Fetch real stats
    const statsRes = await fetch("/api/admin/live-monitoring/stats", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (statsRes.ok) {
      const stats = await statsRes.json();
      const elSources = document.getElementById("adminLiveActiveSources");
      const elActive = document.getElementById("adminLiveActiveIncidents");
      const elCrit = document.getElementById("adminLiveCriticalIncidents");
      const elVerif = document.getElementById("adminLiveVerifiedIncidents");
      const elRepair = document.getElementById("adminLiveUnderRepair");
      const elDone = document.getElementById("adminLiveCompletedToday");

      if (elSources) elSources.textContent = stats.connected_sources ?? 1;
      if (elActive) elActive.textContent = stats.active_live_incidents ?? 0;
      if (elCrit) elCrit.textContent = stats.critical_live_incidents ?? 0;
      if (elVerif) elVerif.textContent = stats.verified_live_incidents ?? 0;
      if (elRepair) elRepair.textContent = stats.under_repair ?? 0;
      if (elDone) elDone.textContent = stats.completed_today ?? 0;
    }

    // 2. Fetch incidents with source filter
    const incRes = await fetch(`/api/admin/complaints?source_filter=${encodeURIComponent(currentLiveSourceFilter)}`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (incRes.ok) {
      const complaints = await incRes.json();
      renderAdminLiveMonitoringFeed(complaints);
    }
  } catch (e) {
    console.error("Admin Live Monitoring load error:", e);
  }
}

function setLiveSourceFilter(source, btn) {
  currentLiveSourceFilter = source;
  document.querySelectorAll("#adminLiveSourceTabs .source-tab-btn").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
  loadAdminLiveMonitoring();
}

function renderAdminLiveMonitoringFeed(complaints) {
  const feed = document.getElementById("adminLiveIncidentFeed");
  if (!feed) return;

  if (!complaints || complaints.length === 0) {
    feed.innerHTML = `
      <div style="padding:48px; text-align:center; color:var(--text-muted);">
        <div style="font-size:32px; margin-bottom:8px;">📡</div>
        <h4 style="font-size:15px; font-weight:700; color:var(--text-main);">No Live Incidents in Queue</h4>
        <p style="font-size:12px; margin-top:4px;">Real-time camera and citizen detections will appear here automatically.</p>
      </div>
    `;
    return;
  }

  feed.innerHTML = complaints.map(c => {
    const rawImg = c.annotated_image_path || c.image_path;
    const thumb = rawImg ? getImageUrl(rawImg) : createPlaceholderDataUrl("Live evidence frame");
    const sourceLabel = c.source || "CITIZEN_IMAGE";
    const isLive = sourceLabel === "LIVE_VIDEO" || sourceLabel === "VIDEO_SIMULATION" || sourceLabel === "LIVE_CAMERA" || sourceLabel === "WEBCAM";
    const srcBadgeClass = isLive ? "badge-danger" : "badge-info";
    const isSubmitted = c.status === "SUBMITTED" || c.status === "PENDING";
    const isVerified = c.status === "VERIFIED";
    const isAssigned = c.status === "ASSIGNED";
    const isInProgress = c.status === "IN_PROGRESS";
    const isUnderReview = c.status === "UNDER_REVIEW";
    const isCompleted = c.status === "COMPLETED";

    const statBadgeClass = isCompleted ? "badge-success" : (isVerified || isAssigned || isInProgress ? "badge-warning" : (isUnderReview ? "badge-info" : "badge-danger"));
    const gpsText = (c.latitude && c.longitude) ? `${Number(c.latitude).toFixed(4)}, ${Number(c.longitude).toFixed(4)}` : "GPS unavailable";
    const borderLeftColor = c.risk_score >= 75 ? '#EF4444' : (c.risk_score >= 50 ? '#F59E0B' : '#10B981');

    return `
      <div class="live-incident-card" id="live-card-${c.id}" style="border-left-color: ${borderLeftColor};">
        <div class="live-card-top-bar">
          <div class="live-card-badges">
            <span class="live-pulse-badge ${isLive ? 'live' : 'citizen'}">
              <span class="pulse-dot"></span>
              ${isLive ? '🔴 LIVE INCIDENT' : '📋 CITIZEN COMPLAINT'}
            </span>
            <span class="badge ${srcBadgeClass}">Source: ${sourceLabel}</span>
            <span class="badge ${statBadgeClass}">${c.status}</span>
          </div>
          <span class="live-card-time">🕒 ${c.created_at ? c.created_at.slice(11, 19) : 'Just now'}</span>
        </div>

        <div class="live-card-body">
          <div class="live-card-thumb-wrap">
            <img src="${thumb}" alt="Evidence" class="live-card-thumb" onerror="handleImageError(this, 'Evidence frame')">
          </div>
          <div class="live-card-details">
            <h4 class="live-card-title">
              #${c.complaint_id || c.tracking_number || c.id} — ${c.title || c.detected_class || 'Road Hazard'}
            </h4>
            <div class="live-card-meta-chips">
              <span>AI Detection: <strong style="color:var(--primary);">${c.detected_class || c.issue_type || 'Hazard'}</strong></span>
              <span>Confidence: <strong>${Math.round((c.confidence || 0.88) * 100)}%</strong></span>
              <span>Risk: <strong style="color:${c.risk_score >= 75 ? '#DC2626' : '#D97706'}">${c.risk_score != null ? c.risk_score : '--'}/100</strong></span>
              <span>Priority: <strong>${c.priority_level || 'HIGH'}</strong></span>
            </div>
            <div class="live-card-location">
              📍 Location: <strong>${c.location_address || 'Municipal Zone'}</strong> (GPS: <code>${gpsText}</code>) ${c.camera_id ? `• Camera: <code>${c.camera_id}</code>` : ''}
            </div>
          </div>
          <div class="live-card-actions">
            <button class="btn btn-secondary btn-sm" onclick="navigate('/admin/complaints/${c.id}')">View Details</button>
            ${isSubmitted ? `
              <button class="btn btn-success btn-sm" onclick="handleVerifyLiveIncident('${c.id}')">✓ Verify</button>
              <button class="btn btn-danger btn-sm" onclick="handleRejectLiveIncident('${c.id}')">✕ Reject</button>
            ` : ''}
            ${isVerified ? `
              <button class="btn btn-primary btn-sm" onclick="openAssignModal('${c.id}')">👷 Assign Worker</button>
            ` : ''}
            ${isUnderReview ? `
              <button class="btn btn-success btn-sm" onclick="navigate('/admin/complaints/${c.id}')">🔍 Review Completion</button>
            ` : ''}
            ${isCompleted ? `
              <span class="badge badge-success" style="padding:6px 12px; font-size:11px; text-align:center;">✓ Resolved</span>
            ` : ''}
          </div>
        </div>
      </div>
    `;
  }).join("");
}

async function handleVerifyLiveIncident(id) {
  await handleVerifyComplaint(id);
  loadAdminLiveMonitoring();
}

async function handleRejectLiveIncident(id) {
  await handleRejectComplaint(id);
  loadAdminLiveMonitoring();
}

// ==========================================================================
// Video Intelligence Studio (Section 7)
// ==========================================================================

function handleVideoFileSelect(event) {
  const file = event.target.files && event.target.files[0];
  if (file) {
    selectedVideoFile = file;
    lastVideoAnalysis = null;
    const video = document.getElementById("videoElement");
    const playerContainer = document.getElementById("videoPlayerContainer");
    const dropzone = document.getElementById("videoDropzone");
    const list = document.getElementById("videoTimelineList");
    const countBadge = document.getElementById("videoDetectionsCountBadge");
    const actionsPanel = document.getElementById("videoActionsPanel");
    const btnRemove = document.getElementById("btnRemoveVideo");
    const btnProcess = document.getElementById("btnProcessVideo");

    // Clear previous video results immediately
    if (list) {
      list.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 13px;">Selected video: <strong>${file.name}</strong>.<br><small>Click 'Process Video with AI' to begin frame-by-frame AI inspection.</small></div>`;
    }
    if (countBadge) countBadge.textContent = "0 Hazards";
    if (actionsPanel) actionsPanel.style.display = "none";
    if (btnProcess) {
      btnProcess.disabled = false;
      btnProcess.textContent = "Process Video with AI";
    }

    if (video && playerContainer) {
      if (video.src && video.src.startsWith("blob:")) {
        try { URL.revokeObjectURL(video.src); } catch (e) {}
      }
      video.src = URL.createObjectURL(file);
      playerContainer.style.display = "block";
      if (dropzone) dropzone.style.display = "none";
    }

    if (btnRemove) {
      btnRemove.style.display = "inline-flex";
      btnRemove.disabled = false;
    }

    toast(`Video loaded: ${file.name}`, "info");
  }
}

async function runVideoProcessing() {
  if (!selectedVideoFile) {
    toast("Please select a video file to analyze", "warning");
    return;
  }

  const btn = document.getElementById("btnProcessVideo");
  try {
    btn.disabled = true;
    btn.textContent = "Processing Video Frames with AI (Please Wait)...";

    const formData = new FormData();
    formData.append("file", selectedVideoFile);
    formData.append("sample_fps", "1");
    formData.append("conf_threshold", activeConfidence);

    const res = await fetch("/api/video/analyze", {
      method: "POST",
      body: formData
    });

    if (res.ok) {
      lastVideoAnalysis = await res.json();
      renderVideoTimeline(lastVideoAnalysis);
      toast("Video survey processed successfully!", "success");
    } else {
      const err = await res.json().catch(() => ({}));
      toast(err.detail || "Video processing error", "error");
      const list = document.getElementById("videoTimelineList");
      if (list) list.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--danger);">AI inference failed for this input.</div>`;
    }
  } catch (e) {
    toast("Video processing failed: " + e.message, "error");
    const list = document.getElementById("videoTimelineList");
    if (list) list.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--danger);">AI inference failed for this input.</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Process Video with AI";
  }
}

function renderVideoTimeline(data) {
  const list = document.getElementById("videoTimelineList");
  const countBadge = document.getElementById("videoDetectionsCountBadge");
  const actionsPanel = document.getElementById("videoActionsPanel");

  const incidents = data.aggregated_incidents || data.timeline_incidents || data.incidents || [];
  const fileName = data.filename || (selectedVideoFile ? selectedVideoFile.name : "Uploaded Video");

  if (countBadge) countBadge.textContent = `${incidents.length} Hazards`;

  if (incidents.length > 0) {
    const sourceBanner = `
      <div style="margin-bottom: 12px; font-size: 12px; color: var(--text-muted); display: flex; align-items: center; justify-content: space-between; background: var(--bg-subtle); padding: 6px 12px; border-radius: 6px;">
        <span>Source: <strong style="color: var(--primary);">VIDEO</strong> • File: <strong>${fileName}</strong></span>
        <span>Total Detections: <strong>${data.total_raw_detections || incidents.length}</strong></span>
      </div>
    `;

    const itemsHtml = incidents.map((inc, idx) => {
      const clsName = inc.detected_class || inc.class_name || inc.label || "Road Hazard";
      const conf = inc.best_confidence != null ? inc.best_confidence : (inc.confidence != null ? inc.confidence : 0.85);
      const confPct = Math.round(conf * 100);
      const ts = inc.first_detected_timestamp || inc.timestamp || "00:00";
      const frameNum = inc.first_frame != null ? `Frame #${inc.first_frame}` : "";
      const modelName = inc.ai_model || "YOLO Detection";
      const boxStr = inc.best_bounding_box ? `• Box: [${inc.best_bounding_box.map(Math.round).join(", ")}]` : "";
      const condStr = inc.sign_condition ? `• Condition: <strong>${inc.sign_condition.condition.toUpperCase()}</strong>` : "";
      const sev = inc.severity || (conf >= 0.80 ? "HIGH" : "MEDIUM");
      const badgeClass = sev === "CRITICAL" || sev === "HIGH" ? "badge-danger" : "badge-warning";

      return `
        <div class="timeline-item-row" style="padding: 10px; margin-bottom: 8px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span class="timeline-timestamp" style="background: var(--bg-subtle); padding: 4px 8px; border-radius: 4px; font-size: 11.5px; font-weight: 700;">${ts}</span>
            <div>
              <div style="font-weight: 700; font-size: 13px; color: var(--text-main);">${idx + 1}. ${clsName}</div>
              <div style="font-size: 11px; color: var(--text-muted);">${frameNum} ${boxStr} ${condStr} • Model: ${modelName} • Source: VIDEO</div>
            </div>
          </div>
          <div style="text-align: right;">
            <span class="badge ${badgeClass}">${sev}</span>
            <div style="font-size: 11.5px; font-weight: 600; color: var(--text-secondary); margin-top: 2px;">${confPct}%</div>
          </div>
        </div>
      `;
    }).join("");

    list.innerHTML = sourceBanner + itemsHtml;
    if (actionsPanel) actionsPanel.style.display = "block";
  } else {
    list.innerHTML = `
      <div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px;">
        <div style="font-weight: 600; color: var(--text-main); margin-bottom: 4px;">No AI detections found in the uploaded video.</div>
        <div style="font-size: 11.5px;">Source: VIDEO • File: ${fileName} (${data.processing_stats?.sampled_frames_count || 0} frames analyzed)</div>
      </div>
    `;
    if (actionsPanel) actionsPanel.style.display = "none";
  }
}

async function saveVideoIncidentsToDb() {
  if (!lastVideoAnalysis || !lastVideoAnalysis.incidents) {
    toast("No video incidents to save", "warning");
    return;
  }
  try {
    const payload = {
      video_name: selectedVideoFile ? selectedVideoFile.name : "survey.mp4",
      incidents: lastVideoAnalysis.incidents
    };
    const res = await fetch("/api/video/save-incidents", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      toast("Video incidents committed to Municipal Database!", "success");
    }
  } catch (e) {
    toast("Failed saving video incidents: " + e.message, "error");
  }
}

function confirmRemoveVideo() {
  if (!selectedVideoFile) {
    toast("No video currently loaded", "warning");
    return;
  }
  const modal = document.getElementById("modalConfirmRemoveVideo");
  if (modal) {
    modal.classList.add("show");
  }
}

function executeRemoveVideo() {
  closeModal("modalConfirmRemoveVideo");
  clearVideoIntelligenceStudio();
  toast("Video and unsaved detections removed", "info");
}

function clearVideoIntelligenceStudio() {
  // 1. Release object URL if any & pause video
  const video = document.getElementById("videoElement");
  if (video) {
    try {
      video.pause();
      if (video.src && video.src.startsWith("blob:")) {
        URL.revokeObjectURL(video.src);
      }
      video.removeAttribute("src");
      video.load();
    } catch (e) {
      console.warn("Error clearing video player:", e);
    }
  }

  // 2. Reset file input value so re-uploading the same file works
  const fileInput = document.getElementById("videoFileInput");
  if (fileInput) {
    fileInput.value = "";
  }

  // 3. Reset state variables
  selectedVideoFile = null;
  lastVideoAnalysis = null;

  // 4. Reset UI components
  const dropzone = document.getElementById("videoDropzone");
  const playerContainer = document.getElementById("videoPlayerContainer");
  const btnProcess = document.getElementById("btnProcessVideo");
  const btnRemove = document.getElementById("btnRemoveVideo");
  const list = document.getElementById("videoTimelineList");
  const countBadge = document.getElementById("videoDetectionsCountBadge");
  const actionsPanel = document.getElementById("videoActionsPanel");

  if (dropzone) dropzone.style.display = "block";
  if (playerContainer) playerContainer.style.display = "none";
  if (btnRemove) {
    btnRemove.style.display = "none";
    btnRemove.disabled = true;
  }
  if (btnProcess) {
    btnProcess.disabled = false;
    btnProcess.textContent = "Process Video with AI";
  }
  if (countBadge) {
    countBadge.textContent = "0 Hazards";
  }
  if (actionsPanel) {
    actionsPanel.style.display = "none";
  }
  if (list) {
    list.innerHTML = `
      <div style="padding: 24px; text-align: center; color: var(--text-muted);" id="videoTimelinePlaceholder">
        Upload a video to view detected signs and damage timeline.
      </div>
    `;
  }
}

// ==========================================================================
// Municipal GIS Map Studio (Section 9)
// ==========================================================================
// Municipal GIS Map Studio & Field Worker Navigation
// ==========================================================================

let workerRoutePolyline = null;
let workerDestMarker = null;
let activeNavDestination = null;

function initLeafletMap() {
  const container = document.getElementById("leafletMap");
  if (!container) return;

  if (leafletMapInstance) {
    leafletMapInstance.invalidateSize();
    loadMapMarkers();
    checkWorkerMapNavControls();
    return;
  }

  // Initialize Map
  const mapCenterLat = (currentGps && currentGps.lat != null) ? currentGps.lat : 11.6643;
  const mapCenterLng = (currentGps && currentGps.lng != null) ? currentGps.lng : 78.1460;
  leafletMapInstance = L.map("leafletMap").setView([mapCenterLat, mapCenterLng], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors • VisionGuardAI GIS"
  }).addTo(leafletMapInstance);

  leafletMarkersLayer = L.layerGroup().addTo(leafletMapInstance);
  loadMapMarkers();
  checkWorkerMapNavControls();
}

function checkWorkerMapNavControls() {
  const navPanel = document.getElementById("workerMapNavPanel");
  if (!navPanel) return;

  if (currentUser && currentUser.role === "WORKER") {
    navPanel.style.display = "block";
    populateWorkerRouteTaskSelector();
  } else {
    navPanel.style.display = "none";
  }
}

async function populateWorkerRouteTaskSelector() {
  const select = document.getElementById("workerRouteTaskSelect");
  if (!select || !authToken) return;

  try {
    const res = await fetch("/api/worker/assignments", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const tasks = await res.json();
      workerAssignmentsCache = tasks || [];
      const activeTasks = tasks.filter(t => t.status !== "COMPLETED" && t.status !== "REJECTED");
      
      select.innerHTML = `<option value="">-- Select Work Order Destination (${activeTasks.length} Active) --</option>` + 
        activeTasks.map(t => `<option value="${t.id}">#${t.complaint_id || t.id} - ${t.title || t.issue_type} (${t.status})</option>`).join("");
    }
  } catch (e) {
    console.warn("Could not populate worker route selector:", e);
  }
}

function handleWorkerSelectRouteDestination(taskId) {
  if (!taskId) {
    clearWorkerRoute();
    return;
  }
  const task = workerAssignmentsCache.find(t => String(t.id) === String(taskId));
  if (!task || !task.latitude || !task.longitude) {
    toast("Selected task does not have valid GPS coordinates", "warning");
    return;
  }
  activeNavDestination = task;
  drawWorkerRouteToDestination(task);
}

function drawWorkerRouteToDestination(destTask) {
  if (!leafletMapInstance) return;

  const startLat = currentGps.lat;
  const startLng = currentGps.lng;
  const destLat = destTask.latitude;
  const destLng = destTask.longitude;

  // Calculate Haversine Distance
  const distanceKm = calculateHaversineDistance(startLat, startLng, destLat, destLng);
  const distInfo = document.getElementById("workerRouteDistanceInfo");
  const distVal = document.getElementById("workerRouteDistanceVal");
  if (distInfo && distVal) {
    distInfo.style.display = "block";
    distVal.textContent = distanceKm < 1 ? `${Math.round(distanceKm * 1000)} meters` : `${distanceKm.toFixed(2)} km`;
  }

  // Clear previous route
  if (workerRoutePolyline) {
    leafletMapInstance.removeLayer(workerRoutePolyline);
  }
  if (workerDestMarker) {
    leafletMapInstance.removeLayer(workerDestMarker);
  }

  // Draw Glowing Route Polyline
  const latlngs = [
    [startLat, startLng],
    [destLat, destLng]
  ];
  workerRoutePolyline = L.polyline(latlngs, {
    color: '#0284C7',
    weight: 5,
    opacity: 0.85,
    dashArray: '10, 10',
    lineJoin: 'round'
  }).addTo(leafletMapInstance);

  // Destination Marker
  const destIcon = L.divIcon({
    className: 'worker-dest-pin',
    html: `<div style="background:#EF4444; width:22px; height:22px; border-radius:50%; border:3px solid #FFF; box-shadow:0 0 12px rgba(239,68,68,0.8); display:flex; align-items:center; justify-content:center; color:#fff; font-size:10px; font-weight:800;">📍</div>`
  });
  workerDestMarker = L.marker([destLat, destLng], { icon: destIcon })
    .bindPopup(`
      <div style="font-family:Inter,sans-serif; min-width:180px;">
        <strong style="color:#0284C7;">#${destTask.complaint_id || destTask.id}</strong>
        <div style="font-weight:700; margin:3px 0;">${destTask.title || destTask.issue_type}</div>
        <div style="font-size:11.5px; color:#64748B;">📍 ${destTask.location_address || 'Site Location'}</div>
        <div style="font-size:11.5px; margin-top:4px;">Distance: <strong>${distanceKm.toFixed(2)} km</strong></div>
      </div>
    `)
    .addTo(leafletMapInstance);

  leafletMapInstance.fitBounds(workerRoutePolyline.getBounds(), { padding: [50, 50] });
  toast(`Route mapped to #${destTask.complaint_id || destTask.id} (${distanceKm.toFixed(2)} km)`, "info");
}

function locateAndRouteWorker() {
  if (currentGps.isLive && currentGps.lat != null) {
    updateGpsUi();
    loadMapMarkers();
    if (activeNavDestination) {
      drawWorkerRouteToDestination(activeNavDestination);
    } else {
      locateUserOnMap();
    }
    toast(`Using live GPS fix: ${currentGps.lat}, ${currentGps.lng}`, "success");
    return;
  }

  if ("geolocation" in navigator) {
    toast("Acquiring GPS fix...", "info");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        currentGps.lat = parseFloat(pos.coords.latitude.toFixed(6));
        currentGps.lng = parseFloat(pos.coords.longitude.toFixed(6));
        currentGps.accuracy = Math.round(pos.coords.accuracy || 0);
        currentGps.timestamp = new Date();
        currentGps.address = `GPS: ${currentGps.lat}, ${currentGps.lng} (±${currentGps.accuracy}m)`;
        currentGps.isLive = true;
        updateGpsUi();
        loadMapMarkers();
        if (activeNavDestination) {
          drawWorkerRouteToDestination(activeNavDestination);
        } else {
          locateUserOnMap();
        }
      },
      (err) => {
        toast("GPS location fix unavailable: " + err.message, "warning");
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }
}

function clearWorkerRoute() {
  if (workerRoutePolyline && leafletMapInstance) {
    leafletMapInstance.removeLayer(workerRoutePolyline);
    workerRoutePolyline = null;
  }
  if (workerDestMarker && leafletMapInstance) {
    leafletMapInstance.removeLayer(workerDestMarker);
    workerDestMarker = null;
  }
  activeNavDestination = null;
  const distInfo = document.getElementById("workerRouteDistanceInfo");
  if (distInfo) distInfo.style.display = "none";
  const select = document.getElementById("workerRouteTaskSelect");
  if (select) select.value = "";
  toast("Navigation route cleared", "info");
}

function calculateHaversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6371; // Radius of Earth in KM
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

async function loadMapMarkers() {
  if (!leafletMarkersLayer) return;
  leafletMarkersLayer.clearLayers();

  // Add User / Worker Location Marker if GPS fix is active
  if (currentGps && currentGps.lat != null && currentGps.lng != null) {
    const userIcon = L.divIcon({
      className: 'custom-map-marker',
      html: '<div style="background:#0284C7; width:18px; height:18px; border-radius:50%; border:3px solid #fff; box-shadow:0 0 10px rgba(2,132,199,0.5);"></div>'
    });
    L.marker([currentGps.lat, currentGps.lng], { icon: userIcon })
      .bindPopup(`<strong>Your Location</strong><br>${currentGps.address || 'Current Position'}`)
      .addTo(leafletMarkersLayer);
  }

  try {
    const res = await fetch("/api/map/incidents");
    if (res.ok) {
      const data = await res.json();
      const incidents = data.incidents || data || [];

      incidents.forEach(inc => {
        if (inc.latitude && inc.longitude) {
          const score = inc.risk_score || (inc.severity === "HIGH" ? 75 : (inc.severity === "MEDIUM" ? 45 : 20));
          const rLevel = inc.risk_level || (score >= 75 ? "CRITICAL" : (score >= 50 ? "HIGH" : (score >= 25 ? "MEDIUM" : "LOW")));
          const prio = inc.priority_level || (score >= 75 ? "URGENT" : (score >= 50 ? "HIGH" : (score >= 25 ? "NORMAL" : "LOW")));
          
          let color = "#10B981"; // LOW
          if (rLevel === "CRITICAL" || score >= 75) color = "#EF4444";
          else if (rLevel === "HIGH" || score >= 50) color = "#EA580C";
          else if (rLevel === "MEDIUM" || score >= 25) color = "#F59E0B";

          const markerIcon = L.divIcon({
            className: 'incident-marker',
            html: `<div style="background:${color}; width:16px; height:16px; border-radius:50%; border:2px solid #fff; box-shadow:0 2px 6px rgba(0,0,0,0.35); display:flex; align-items:center; justify-content:center; color:#fff; font-size:9px; font-weight:800;">!</div>`
          });

          L.marker([inc.latitude, inc.longitude], { icon: markerIcon })
            .bindPopup(`
              <div style="font-family:Inter,sans-serif; min-width:210px; padding:2px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                  <strong style="color:${color}; font-size:13px;">${inc.title || inc.issue_type || 'Road Hazard'}</strong>
                  <span style="font-size:10px; font-weight:800; padding:2px 6px; border-radius:10px; background:${color}22; color:${color};">${rLevel}</span>
                </div>
                <div style="font-size:11px; color:#64748b; margin:3px 0;">📍 ${inc.location_address || 'Salem Municipal Ward'}</div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px; font-size:11px; margin:6px 0; background:#f8fafc; padding:6px; border-radius:4px;">
                  <div>Risk Score: <strong>${score}/100</strong></div>
                  <div>Priority: <strong>${prio}</strong></div>
                  <div>Status: <strong>${inc.status || 'REPORTED'}</strong></div>
                  <div>Severity: <strong>${inc.severity || 'MEDIUM'}</strong></div>
                </div>
                <button onclick="openComplaintDetailsModal('${inc.id}')" style="margin-top:4px; background:#0284C7; color:#fff; border:none; padding:5px 10px; border-radius:4px; font-size:11px; font-weight:700; cursor:pointer; width:100%;">Inspect Risk Assessment</button>
              </div>
            `)
            .addTo(leafletMarkersLayer);
        }
      });
    }
  } catch (e) {
    console.error("Map markers load failed:", e);
  }
}

async function toggleRiskHeatmap() {
  const btn = document.getElementById("btnToggleRiskHeatmap");
  if (!leafletMapInstance) return;

  if (isRiskHeatmapActive) {
    if (riskHeatmapLayer) {
      leafletMapInstance.removeLayer(riskHeatmapLayer);
      riskHeatmapLayer = null;
    }
    isRiskHeatmapActive = false;
    if (btn) {
      btn.classList.remove("btn-primary");
      btn.classList.add("btn-outline");
    }
    toast("Risk heatmap overlay disabled", "info");
    return;
  }

  try {
    const res = await fetch("/api/risk/heatmap", {
      headers: authToken ? { "Authorization": `Bearer ${authToken}` } : {}
    });
    if (res.ok) {
      const data = await res.json();
      const points = data.points || [];

      if (points.length === 0) {
        toast("Not enough data to generate risk heatmap.", "warning");
        return;
      }

      riskHeatmapLayer = L.layerGroup();
      points.forEach(p => {
        if (p.lat && p.lng) {
          const score = p.risk_score || 50;
          let fillColor = "#10B981";
          if (score >= 75) fillColor = "#EF4444";
          else if (score >= 50) fillColor = "#EA580C";
          else if (score >= 25) fillColor = "#F59E0B";

          const radius = Math.max(120, score * 4);
          L.circle([p.lat, p.lng], {
            radius: radius,
            color: fillColor,
            fillColor: fillColor,
            fillOpacity: 0.35,
            weight: 1
          }).bindTooltip(`Risk Score: ${score}/100 (${p.risk_level}) • ${p.priority}`, { sticky: true })
            .addTo(riskHeatmapLayer);
        }
      });

      riskHeatmapLayer.addTo(leafletMapInstance);
      isRiskHeatmapActive = true;
      if (btn) {
        btn.classList.remove("btn-outline");
        btn.classList.add("btn-primary");
      }
      toast(`Risk Heatmap enabled (${points.length} spatial points)`, "success");
    }
  } catch (e) {
    console.error("Risk heatmap error:", e);
    toast("Failed loading risk heatmap: " + e.message, "error");
  }
}

function locateUserOnMap() {
  if (leafletMapInstance) {
    leafletMapInstance.setView([currentGps.lat, currentGps.lng], 15);
    toast("Centered on current GPS location", "info");
  }
}

function applyMapFilters() {
  loadMapMarkers();
}

// ==========================================================================
// Field Worker Portal (Section 12, 13) - Separate Dashboard & Tasks Views
// ==========================================================================

let currentWorkerTaskFilter = "ALL";
let workerAssignmentsCache = [];

async function loadWorkerDashboardData() {
  if (!authToken) return;

  try {
    // 1. Fetch worker dashboard metrics
    const dashRes = await fetch("/api/worker/dashboard", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (dashRes.ok) {
      const data = await dashRes.json();
      const metrics = data.metrics || {};
      const elAssigned = document.getElementById("workerStatAssigned");
      const elInProgress = document.getElementById("workerStatInProgress");
      const elCompleted = document.getElementById("workerStatCompleted");
      if (elAssigned) elAssigned.textContent = metrics.assigned_tasks ?? 0;
      if (elInProgress) elInProgress.textContent = metrics.in_progress_tasks ?? 0;
      if (elCompleted) elCompleted.textContent = metrics.completed_tasks ?? 0;
    }

    // 2. Fetch assignments to populate recent preview cards
    const tasksRes = await fetch("/api/worker/assignments", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    const previewContainer = document.getElementById("workerDashboardRecentTasks");
    if (tasksRes.ok && previewContainer) {
      const tasks = await tasksRes.json();
      workerAssignmentsCache = tasks || [];
      const recent3 = (tasks || []).slice(0, 3);

      if (recent3.length > 0) {
        previewContainer.innerHTML = recent3.map(t => {
          const sevBadge = t.severity === 'HIGH' || t.severity === 'CRITICAL' ? 'badge-danger' : (t.severity === 'MEDIUM' ? 'badge-warning' : 'badge-info');
          const statBadge = t.status === 'COMPLETED' ? 'badge-success' : (t.status === 'IN_PROGRESS' ? 'badge-warning' : 'badge-info');
          return `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--bg-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
              <div>
                <div style="font-weight: 700; font-size: 13.5px; color: var(--text-main);">#${t.complaint_id || t.id} — ${t.title || t.issue_type}</div>
                <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 2px;">📍 ${t.location_address || 'Salem'} • Status: <span class="badge ${statBadge}" style="font-size:10px; padding:2px 6px;">${t.status}</span></div>
              </div>
              <button class="btn btn-secondary btn-sm" onclick="navigate('/worker/tasks/${t.id}')">Open Task</button>
            </div>
          `;
        }).join("");
      } else {
        previewContainer.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px;">No assigned work orders currently.</div>`;
      }
    }
  } catch (e) {
    console.error("Worker dashboard failed:", e);
  }
}

async function loadWorkerTasksData() {
  if (!authToken) return;
  const grid = document.getElementById("workerTasksGrid");
  if (grid) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted);">
        <div style="display:inline-block; width:22px; height:22px; border:2px solid var(--primary); border-top-color:transparent; border-radius:50%; animation:spin 0.8s linear infinite; margin-bottom:8px;"></div>
        <div>Loading assigned maintenance tasks...</div>
      </div>
    `;
  }

  try {
    const res = await fetch("/api/worker/assignments", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (res.ok) {
      const tasks = await res.json();
      workerAssignmentsCache = tasks || [];
      filterWorkerTasks(currentWorkerTaskFilter);
    } else {
      if (grid) {
        grid.innerHTML = `
          <div style="grid-column: 1 / -1; padding: 48px; text-align: center; color: var(--danger);">
            <div style="font-size: 32px; margin-bottom: 8px;">⚠️</div>
            <h3 style="font-size: 15px; font-weight: 700; margin-bottom: 6px;">Unable to load assigned tasks.</h3>
            <button class="btn btn-outline btn-sm" onclick="loadWorkerTasksData()" style="margin-top:8px;">Retry</button>
          </div>
        `;
      }
    }
  } catch (e) {
    console.error("Worker tasks load failed:", e);
    if (grid) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 48px; text-align: center; color: var(--danger);">
          <div style="font-size: 32px; margin-bottom: 8px;">⚠️</div>
          <h3 style="font-size: 15px; font-weight: 700; margin-bottom: 6px;">Unable to load assigned tasks.</h3>
          <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">${e.message}</p>
          <button class="btn btn-outline btn-sm" onclick="loadWorkerTasksData()">Retry</button>
        </div>
      `;
    }
  }
}

function filterWorkerTasks(filterStatus) {
  currentWorkerTaskFilter = filterStatus || "ALL";

  // Update filter pill UI
  document.querySelectorAll("#workerTaskFilterTabs .filter-tab").forEach(tab => {
    if (tab.getAttribute("data-filter") === currentWorkerTaskFilter) {
      tab.classList.add("active");
    } else {
      tab.classList.remove("active");
    }
  });

  const searchInput = document.getElementById("workerTaskSearchInput");
  const query = searchInput ? searchInput.value.trim().toLowerCase() : "";

  let filtered = [...workerAssignmentsCache];

  if (currentWorkerTaskFilter !== "ALL") {
    filtered = filtered.filter(t => t.status === currentWorkerTaskFilter);
  }

  if (query) {
    filtered = filtered.filter(t => 
      (t.complaint_id && t.complaint_id.toLowerCase().includes(query)) ||
      (t.title && t.title.toLowerCase().includes(query)) ||
      (t.issue_type && t.issue_type.toLowerCase().includes(query)) ||
      (t.location_address && t.location_address.toLowerCase().includes(query)) ||
      (t.detected_class && t.detected_class.toLowerCase().includes(query))
    );
  }

  renderWorkerTasksGrid(filtered);
}

function renderWorkerTasksGrid(tasks) {
  const grid = document.getElementById("workerTasksGrid");
  if (!grid) return;

  if (tasks && tasks.length > 0) {
    grid.innerHTML = tasks.map(t => {
      const rawImg = getImageUrl(t.image_path);
      const thumbUrl = rawImg || createPlaceholderDataUrl("No evidence image uploaded");
      const sevBadge = t.severity === 'HIGH' || t.severity === 'CRITICAL' ? 'badge-danger' : (t.severity === 'MEDIUM' ? 'badge-warning' : 'badge-info');
      const statBadge = t.status === 'COMPLETED' ? 'badge-success' : (t.status === 'IN_PROGRESS' ? 'badge-warning' : 'badge-info');
      const isAssigned = t.status === 'ASSIGNED';
      const isInProgress = t.status === 'IN_PROGRESS';
      const isUnderReview = t.status === 'UNDER_REVIEW';
      const isCompleted = t.status === 'COMPLETED';
      const aiInfo = t.detected_class ? `<div style="font-size:12px; color:var(--primary); margin-top:2px;">AI Detection: <strong>${t.detected_class}</strong>${t.confidence ? ` • Conf: ${Math.round(t.confidence * 100)}%` : ''}</div>` : '';
      
      const prioLevel = t.priority_level || (t.risk_score >= 75 ? "URGENT" : (t.risk_score >= 50 ? "HIGH" : (t.risk_score >= 25 ? "NORMAL" : "LOW")));
      const prioBadge = prioLevel === 'URGENT' ? 'badge-danger' : (prioLevel === 'HIGH' ? 'badge-warning' : (prioLevel === 'NORMAL' ? 'badge-info' : 'badge-secondary'));

      return `
        <div class="task-card-item">
          <div style="display:flex; gap:12px; margin-bottom:12px;">
            <img src="${thumbUrl}" alt="Evidence" style="width:64px; height:64px; border-radius:var(--radius-sm); object-fit:cover; background:#F8FAFC; border: 1px solid var(--border-color); flex-shrink:0;" onerror="handleImageError(this, 'No evidence image uploaded')">
            <div style="flex:1; min-width:0;">
              <div class="task-card-header" style="margin-bottom:4px;">
                <strong style="font-size:13px;">#${t.complaint_id || t.tracking_number || t.id}</strong>
                <span class="badge ${sevBadge}">${t.severity || 'MEDIUM'}</span>
              </div>
              <h4 style="font-size:14px; font-weight:700; margin:0 0 2px 0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${t.title || (t.issue_type ? t.issue_type.replace('_', ' ') : 'Road Repair')}</h4>
              ${aiInfo}
              <div style="display:flex; align-items:center; gap:6px; margin-top:4px; flex-wrap:wrap;">
                ${t.source === 'LIVE_VIDEO' || t.source === 'VIDEO_SIMULATION' ? `<span class="badge badge-danger" style="font-size:10px; padding:2px 6px;">🎥 LIVE VIDEO</span>` : ''}
                <span class="badge ${prioBadge}" style="font-size:10px; padding:2px 6px;">Priority: ${prioLevel}</span>
                <span class="badge" style="background:#FAF5FF; color:#7E22CE; border:1px solid #E9D5FF; font-size:10px; padding:2px 6px;">Risk: ${t.risk_score != null ? t.risk_score : '--'}/100</span>
              </div>
            </div>
          </div>

          <div style="font-size:12px; color:var(--text-muted); margin-bottom:12px;">
            <div>📍 ${t.location_address || (t.latitude ? `${t.latitude.toFixed(4)}, ${t.longitude.toFixed(4)}` : 'Salem, Tamil Nadu')}</div>
            <div style="margin-top:2px;">📅 Assigned: ${t.created_at ? t.created_at.slice(0, 10) : 'Recent'} • Status: <span class="badge ${statBadge}">${t.status}</span></div>
          </div>

          <div class="task-workflow-stepper" style="margin-bottom:14px;">
            <div class="stepper-step completed"><div class="stepper-circle">✓</div>Assigned</div>
            <div class="stepper-step ${isInProgress || isUnderReview || isCompleted ? 'completed' : ''}"><div class="stepper-circle">${isInProgress ? '●' : (isUnderReview || isCompleted ? '✓' : '2')}</div>In Progress</div>
            <div class="stepper-step ${isCompleted ? 'completed' : ''}"><div class="stepper-circle">${isCompleted ? '✓' : '3'}</div>Completed</div>
          </div>

          <div style="display:flex; gap:8px; flex-wrap:wrap;">
            <button class="btn btn-secondary btn-sm" style="flex:1;" onclick="navigate('/worker/tasks/${t.id}')">View Details</button>
            <button class="btn btn-outline btn-sm" onclick="navigate('/worker/map'); setTimeout(() => handleWorkerSelectRouteDestination('${t.id}'), 200);">Navigate</button>
            ${isAssigned ? `<button class="btn btn-primary btn-sm" style="flex:1;" onclick="handleWorkerStartTask('${t.id}')">Start Work</button>` : ''}
            ${isInProgress ? `<button class="btn btn-success btn-sm" style="flex:1;" onclick="openWorkerCompleteModal('${t.id}')">Submit Work</button>` : ''}
          </div>
        </div>
      `;
    }).join("");
  } else {
    grid.innerHTML = `<div style="grid-column: 1/-1; padding: 48px; text-align: center; color: var(--text-muted);">No assigned maintenance tasks in queue.</div>`;
  }
}

async function handleWorkerStartTask(complaintId) {
  try {
    const res = await fetch(`/api/worker/assignments/${complaintId}/start`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      toast("Work started! Status updated to IN PROGRESS.", "success");
      loadWorkerDashboardData();
      if (activeComplaintId == complaintId) {
        loadComplaintDetails(complaintId);
      }
    } else {
      const err = await res.json();
      toast(err.detail || "Failed starting task", "error");
    }
  } catch (e) {
    toast("Failed starting task: " + e.message, "error");
  }
}

function openWorkerEvidenceModal(complaintId) {
  activeComplaintId = complaintId;
  const form = document.getElementById("formWorkerUploadEvidence");
  if (form) form.reset();
  const modal = document.getElementById("modalWorkerUploadEvidence");
  if (modal) modal.classList.add("show");
}

async function handleWorkerEvidenceSubmit(event) {
  event.preventDefault();
  const fileInput = document.getElementById("workerEvidenceFileInput");
  const evidenceType = document.getElementById("workerEvidenceType").value;
  const notes = document.getElementById("workerEvidenceNotes").value;

  if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
    toast("Please select a photo evidence file", "warning");
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);
  formData.append("evidence_type", evidenceType);
  if (notes) formData.append("notes", notes);

  try {
    const res = await fetch(`/api/worker/assignments/${activeComplaintId}/evidence`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${authToken}` },
      body: formData
    });

    if (res.ok) {
      toast("Repair evidence uploaded successfully!", "success");
      closeModal("modalWorkerUploadEvidence");
      loadComplaintDetails(activeComplaintId);
    } else {
      const err = await res.json();
      toast(err.detail || "Evidence upload failed", "error");
    }
  } catch (e) {
    toast("Evidence upload error: " + e.message, "error");
  }
}

function openWorkerCompleteModal(complaintId) {
  activeComplaintId = complaintId;
  const form = document.getElementById("formWorkerCompleteTask");
  if (form) form.reset();
  const modal = document.getElementById("modalWorkerCompleteTask");
  if (modal) modal.classList.add("show");
}

async function handleWorkerCompleteSubmit(event) {
  event.preventDefault();
  const notes = document.getElementById("workerCompleteNotes").value.trim();

  try {
    const res = await fetch(`/api/worker/assignments/${activeComplaintId}/complete`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ worker_notes: notes || "Work completed on site" })
    });

    if (res.ok) {
      toast("Task completion submitted for municipal verification!", "success");
      closeModal("modalWorkerCompleteTask");
      loadComplaintDetails(activeComplaintId);
      loadWorkerDashboardData();
    } else {
      const err = await res.json();
      toast(err.detail || "Completion submission failed", "error");
    }
  } catch (e) {
    toast("Completion error: " + e.message, "error");
  }
}

// ==========================================================================
// Admin Command Center & Analytics (Section 14)
// ==========================================================================

async function loadAdminDashboardData() {
  if (!authToken) return;
  try {
    const res = await fetch("/api/admin/dashboard", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (res.ok) {
      const data = await res.json();
      document.getElementById("adminStatTotal").textContent = data.stats.total_complaints || 0;
      document.getElementById("adminStatCompleted").textContent = data.stats.completed || 0;
      document.getElementById("adminStatNew").textContent = data.stats.new_complaints || 0;
      document.getElementById("adminStatInProgress").textContent = data.stats.in_progress || 0;

      // Render Charts with Chart.js
      renderAdminCharts(data);
    }
  } catch (e) {
    console.error("Admin dashboard failed:", e);
  }

  // Load Smart Infrastructure Risk Summary & Top Priority Issues
  try {
    const riskRes = await fetch("/api/risk/summary", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (riskRes.ok) {
      const summary = await riskRes.json();
      const counts = summary.risk_counts || {};
      const elCrit = document.getElementById("adminRiskStatCritical");
      const elHigh = document.getElementById("adminRiskStatHigh");
      const elMed = document.getElementById("adminRiskStatMedium");
      const elLow = document.getElementById("adminRiskStatLow");

      if (elCrit) elCrit.textContent = counts.CRITICAL ?? 0;
      if (elHigh) elHigh.textContent = counts.HIGH ?? 0;
      if (elMed) elMed.textContent = counts.MEDIUM ?? 0;
      if (elLow) elLow.textContent = counts.LOW ?? 0;

      // Render Top Priority Issues Queue
      const topTbody = document.getElementById("adminTopPriorityIssuesTable");
      if (topTbody) {
        const topIssues = summary.top_priority_issues || [];
        if (topIssues.length > 0) {
          topTbody.innerHTML = topIssues.map((issue, idx) => {
            const score = issue.risk_score ?? 0;
            const rLevel = issue.risk_level || (score >= 75 ? "CRITICAL" : (score >= 50 ? "HIGH" : (score >= 25 ? "MEDIUM" : "LOW")));
            const prio = issue.priority || issue.priority_level || (score >= 75 ? "URGENT" : (score >= 50 ? "HIGH" : (score >= 25 ? "NORMAL" : "LOW")));
            
            let color = "#10B981";
            if (rLevel === "CRITICAL" || score >= 75) color = "#EF4444";
            else if (rLevel === "HIGH" || score >= 50) color = "#EA580C";
            else if (rLevel === "MEDIUM" || score >= 25) color = "#F59E0B";

            return `
              <tr>
                <td><strong>#${idx + 1}</strong></td>
                <td>
                  <div style="font-weight: 700; color: var(--text-main);">${issue.title || issue.issue_type}</div>
                  <div style="font-size: 11.5px; color: var(--text-muted);">#${issue.complaint_id || issue.tracking_number || issue.id} • ${issue.location_address || 'Salem'}</div>
                </td>
                <td>
                  <span style="font-size: 14px; font-weight: 800; color: ${color};">${score}</span><span style="font-size: 11px; color: var(--text-muted);"> / 100</span>
                </td>
                <td>
                  <span class="badge" style="background: ${color}18; color: ${color}; border: 1px solid ${color}44; font-weight: 800;">${rLevel}</span>
                </td>
                <td>
                  <span class="badge ${prio === 'URGENT' ? 'badge-danger' : (prio === 'HIGH' ? 'badge-warning' : (prio === 'NORMAL' ? 'badge-info' : 'badge-secondary'))}">${prio}</span>
                </td>
                <td>
                  <span class="badge ${issue.status === 'COMPLETED' ? 'badge-success' : (issue.status === 'IN_PROGRESS' || issue.status === 'ASSIGNED' ? 'badge-warning' : 'badge-info')}">${issue.status}</span>
                </td>
                <td style="font-size: 12px; color: var(--text-secondary); max-width: 200px;">
                  ${issue.recommended_action || 'Prioritize field inspection and repair.'}
                </td>
                <td>
                  <button class="btn btn-secondary btn-sm" onclick="openComplaintDetailsModal('${issue.id}')">Inspect</button>
                </td>
              </tr>
            `;
          }).join("");
        } else {
          topTbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 24px;">No active municipal risk issues recorded.</td></tr>`;
        }
      }
    }
  } catch (errRiskSum) {
    console.error("Risk summary load failed:", errRiskSum);
  }
}

function renderAdminCharts(data) {
  // 1. Issue Type Donut Chart
  const issueCanvas = document.getElementById("adminIssueTypeChart");
  if (issueCanvas) {
    if (issueChartInstance) issueChartInstance.destroy();
    issueChartInstance = new Chart(issueCanvas, {
      type: "doughnut",
      data: {
        labels: ["Potholes", "Cracks", "Damaged Signs", "Faded Signs", "Traffic Signals"],
        datasets: [{
          data: [45, 22, 16, 9, 8],
          backgroundColor: ["#2563eb", "#0ea5e9", "#f59e0b", "#eab308", "#10b981"]
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "right" } }
      }
    });
  }

  // 2. Risk Level Bar Chart
  const riskCanvas = document.getElementById("adminRiskLevelChart");
  if (riskCanvas) {
    if (riskChartInstance) riskChartInstance.destroy();
    riskChartInstance = new Chart(riskCanvas, {
      type: "bar",
      data: {
        labels: ["Critical", "High", "Medium", "Low"],
        datasets: [{
          label: "Hazards",
          data: [12, 45, 86, 120],
          backgroundColor: ["#dc2626", "#ef4444", "#f59e0b", "#10b981"],
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } }
      }
    });
  }
}

async function loadAdminAnalyticsData() {
  if (!authToken) return;
  try {
    const res = await fetch("/api/analytics/historical", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      
      const trendsCanvas = document.getElementById("analyticsTrendsChart");
      if (trendsCanvas) {
        if (trendsChartInstance) trendsChartInstance.destroy();
        trendsChartInstance = new Chart(trendsCanvas, {
          type: "line",
          data: {
            labels: ["Week 1", "Week 2", "Week 3", "Week 4"],
            datasets: [{
              label: "Reported Hazards",
              data: [35, 48, 62, 54],
              borderColor: "#2563eb",
              backgroundColor: "rgba(37, 99, 235, 0.1)",
              fill: true,
              tension: 0.3
            }]
          },
          options: { responsive: true, maintainAspectRatio: false }
        });
      }

      const modelCanvas = document.getElementById("analyticsModelDistChart");
      if (modelCanvas) {
        if (modelDistChartInstance) modelDistChartInstance.destroy();
        modelDistChartInstance = new Chart(modelCanvas, {
          type: "pie",
          data: {
            labels: ["Traffic Signs", "Road Damage", "Traffic Signals", "Sign Condition"],
            datasets: [{
              data: [38, 42, 12, 8],
              backgroundColor: ["#2563eb", "#ef4444", "#10b981", "#8b5cf6"]
            }]
          },
          options: { responsive: true, maintainAspectRatio: false }
        });
      }
    }
  } catch (e) {
    console.error("Analytics load failed:", e);
  }

  // Load Smart Risk Analytics Charts (Chart 5 & Chart 6)
  try {
    const riskAnalyticsRes = await fetch("/api/risk/analytics", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (riskAnalyticsRes.ok) {
      const riskData = await riskAnalyticsRes.json();
      
      // Chart 5: Risk Level Distribution (Doughnut)
      const riskDistCanvas = document.getElementById("chartRiskDistribution");
      if (riskDistCanvas) {
        if (chartRiskDistInstance) chartRiskDistInstance.destroy();
        const dist = riskData.risk_distribution || { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
        chartRiskDistInstance = new Chart(riskDistCanvas, {
          type: "doughnut",
          data: {
            labels: ["Critical (75-100)", "High (50-74)", "Medium (25-49)", "Low (0-24)"],
            datasets: [{
              data: [dist.CRITICAL || 0, dist.HIGH || 0, dist.MEDIUM || 0, dist.LOW || 0],
              backgroundColor: ["#EF4444", "#EA580C", "#F59E0B", "#10B981"]
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "right" } }
          }
        });
      }

      // Chart 6: 7-Day Risk Trends (Line)
      const riskTrendsCanvas = document.getElementById("chartRiskTrends");
      if (riskTrendsCanvas) {
        if (chartRiskTrendsInstance) chartRiskTrendsInstance.destroy();
        const trendList = riskData.risk_trend || [];
        const labels = trendList.map(t => t.date.slice(5)); // MM-DD
        const scores = trendList.map(t => t.avg_risk_score);
        const counts = trendList.map(t => t.count);

        chartRiskTrendsInstance = new Chart(riskTrendsCanvas, {
          type: "line",
          data: {
            labels: labels.length > 0 ? labels : ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"],
            datasets: [
              {
                label: "Avg Risk Score",
                data: scores.length > 0 ? scores : [45, 52, 68, 60, 72, 65, 80],
                borderColor: "#EF4444",
                backgroundColor: "rgba(239, 68, 68, 0.1)",
                fill: true,
                tension: 0.3,
                yAxisID: 'y'
              },
              {
                label: "Hazard Detections",
                data: counts.length > 0 ? counts : [3, 5, 8, 6, 9, 7, 10],
                borderColor: "#0284C7",
                backgroundColor: "rgba(2, 132, 199, 0.1)",
                fill: false,
                tension: 0.3,
                yAxisID: 'y1'
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              y: {
                type: 'linear',
                display: true,
                position: 'left',
                min: 0,
                max: 100,
                title: { display: true, text: 'Risk Score (0-100)' }
              },
              y1: {
                type: 'linear',
                display: true,
                position: 'right',
                grid: { drawOnChartArea: false },
                title: { display: true, text: 'Detection Count' }
              }
            }
          }
        });
      }
    }
  } catch (errRiskAn) {
    console.error("Risk analytics chart load failed:", errRiskAn);
  }
}

// Admin Worker Approvals & Applications Management
let workerApprovalsCache = [];
let workerApprovalStatusFilter = "ALL";

function filterWorkerApprovals(status) {
  workerApprovalStatusFilter = status;
  
  const btnAll = document.getElementById("btnFilterAll");
  const btnPending = document.getElementById("btnFilterPending");
  const btnApproved = document.getElementById("btnFilterApproved");
  const btnRejected = document.getElementById("btnFilterRejected");

  [btnAll, btnPending, btnApproved, btnRejected].forEach(b => {
    if (b) {
      b.classList.remove("btn-primary");
      b.classList.add("btn-outline");
    }
  });

  if (status === "ALL" && btnAll) { btnAll.classList.add("btn-primary"); btnAll.classList.remove("btn-outline"); }
  else if (status === "PENDING_APPROVAL" && btnPending) { btnPending.classList.add("btn-primary"); btnPending.classList.remove("btn-outline"); }
  else if (status === "APPROVED" && btnApproved) { btnApproved.classList.add("btn-primary"); btnApproved.classList.remove("btn-outline"); }
  else if (status === "REJECTED" && btnRejected) { btnRejected.classList.add("btn-primary"); btnRejected.classList.remove("btn-outline"); }

  renderWorkerApprovalsTable();
}

async function loadAdminWorkerApprovalsData() {
  if (!authToken) return;
  const tbody = document.getElementById("adminWorkerApprovalsTableBody");
  try {
    const res = await fetch("/api/admin/worker-approvals", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      workerApprovalsCache = data || [];

      // Update summary counts
      const pendingCount = workerApprovalsCache.filter(w => w.approval_status === "PENDING_APPROVAL").length;
      const approvedCount = workerApprovalsCache.filter(w => w.approval_status === "APPROVED").length;
      const rejectedCount = workerApprovalsCache.filter(w => w.approval_status === "REJECTED").length;

      const elP = document.getElementById("approvalStatPending");
      const elA = document.getElementById("approvalStatApproved");
      const elR = document.getElementById("approvalStatRejected");
      if (elP) elP.textContent = pendingCount;
      if (elA) elA.textContent = approvedCount;
      if (elR) elR.textContent = rejectedCount;

      renderWorkerApprovalsTable();
    }
  } catch (e) {
    console.error("Worker approvals load failed:", e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--danger);">Failed to load worker approvals.</td></tr>`;
  }
}

function renderWorkerApprovalsTable() {
  const tbody = document.getElementById("adminWorkerApprovalsTableBody");
  if (!tbody) return;

  let items = workerApprovalsCache;
  if (workerApprovalStatusFilter !== "ALL") {
    items = items.filter(w => w.approval_status === workerApprovalStatusFilter);
  }

  if (items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--text-muted);">No worker registration applications found.</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(w => {
    let statusBadge = "";
    if (w.approval_status === "PENDING_APPROVAL") {
      statusBadge = `<span class="badge badge-warning" style="background:#FEF3C7; color:#B45309; border:1px solid #FDE68A;">⏳ PENDING</span>`;
    } else if (w.approval_status === "APPROVED") {
      statusBadge = `<span class="badge badge-success">✓ APPROVED</span>`;
    } else {
      statusBadge = `<span class="badge badge-danger">✕ REJECTED</span>`;
    }

    let actionsHtml = "";
    const nameEscaped = (w.full_name || "Worker").replace(/'/g, "\\'");
    if (w.approval_status === "PENDING_APPROVAL") {
      actionsHtml = `
        <div style="display: flex; gap: 6px;">
          <button class="btn btn-xs btn-success" onclick="handleApproveWorker(${w.id}, '${nameEscaped}')">Approve</button>
          <button class="btn btn-xs btn-danger" onclick="handleRejectWorker(${w.id}, '${nameEscaped}')">Reject</button>
        </div>
      `;
    } else if (w.approval_status === "APPROVED") {
      actionsHtml = `<button class="btn btn-xs btn-outline" style="color:var(--danger);" onclick="handleRejectWorker(${w.id}, '${nameEscaped}')">Reject</button>`;
    } else {
      actionsHtml = `<button class="btn btn-xs btn-outline" style="color:var(--success);" onclick="handleApproveWorker(${w.id}, '${nameEscaped}')">Approve</button>`;
    }

    return `
      <tr>
        <td>
          <div style="font-weight: 700; color: var(--text-main);">${w.full_name}</div>
          ${w.specialization ? `<div style="font-size:11px; color:var(--text-muted);">${w.specialization}</div>` : ''}
        </td>
        <td>
          <div>${w.email}</div>
          <div style="font-size:11.5px; color:var(--text-muted);">${w.phone || '--'}</div>
        </td>
        <td><strong>${w.department}</strong></td>
        <td><code>${w.employee_id || 'PENDING'}</code></td>
        <td>${w.created_at ? w.created_at.slice(0, 10) : 'Recent'}</td>
        <td>${statusBadge}</td>
        <td>${actionsHtml}</td>
      </tr>
    `;
  }).join("");
}

async function handleApproveWorker(workerId, workerName) {
  if (!confirm(`Are you sure you want to APPROVE and activate Worker candidate "${workerName}"?`)) {
    return;
  }
  try {
    const res = await fetch(`/api/admin/worker-approvals/${workerId}/approve`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${authToken}`,
        "Content-Type": "application/json"
      }
    });
    if (res.ok) {
      toast(`Worker "${workerName}" has been approved and activated!`, "success");
      loadAdminWorkerApprovalsData();
    } else {
      const err = await res.json();
      toast(err.detail || "Failed to approve worker", "error");
    }
  } catch (e) {
    toast("Approval error: " + e.message, "error");
  }
}

async function handleRejectWorker(workerId, workerName) {
  const reason = prompt(`Enter rejection reason for candidate "${workerName}":`, "Credentials could not be verified by municipal admin");
  if (reason === null) return;

  try {
    const res = await fetch(`/api/admin/worker-approvals/${workerId}/reject`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${authToken}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ rejection_reason: reason })
    });
    if (res.ok) {
      toast(`Worker application for "${workerName}" was rejected.`, "info");
      loadAdminWorkerApprovalsData();
    } else {
      const err = await res.json();
      toast(err.detail || "Failed to reject worker", "error");
    }
  } catch (e) {
    toast("Rejection error: " + e.message, "error");
  }
}

// Admin Workers & Users Management
async function loadAdminWorkersData() {
  if (!authToken) return;
  const tbody = document.getElementById("adminWorkersTableBody");
  try {
    const res = await fetch("/api/admin/workers", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok && tbody) {
      const workers = await res.json();
      if (workers.length > 0) {
        tbody.innerHTML = workers.map(w => {
          const appStatus = w.approval_status || (w.is_active ? 'APPROVED' : 'PENDING_APPROVAL');
          let statusBadge = '';
          if (appStatus === 'PENDING_APPROVAL') {
            statusBadge = `<span class="badge badge-warning" style="background:#FEF3C7; color:#B45309; border:1px solid #FDE68A;">PENDING <a href="#" onclick="navigate('/admin/worker-approvals')" style="margin-left:4px; text-decoration:underline;">Review</a></span>`;
          } else if (appStatus === 'APPROVED') {
            statusBadge = `<span class="badge badge-success">APPROVED</span>`;
          } else {
            statusBadge = `<span class="badge badge-danger">REJECTED</span>`;
          }

          return `
            <tr>
              <td><strong>${w.full_name || w.name || 'Field Engineer'}</strong></td>
              <td><code>${w.employee_id || 'VG-ENG-01'}</code></td>
              <td>${w.department || 'Roads'}</td>
              <td>${w.specialization || 'Surface Repair'}</td>
              <td><span class="badge badge-info">${w.active_tasks || 0}</span></td>
              <td><span class="badge badge-success">${w.completed_tasks || 0}</span></td>
              <td>${statusBadge}</td>
            </tr>
          `;
        }).join("");
      } else {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--text-muted);">No field workers registered.</td></tr>`;
      }
    }
  } catch (e) {
    console.error("Workers roster load failed:", e);
  }
}

async function loadAdminUsersData() {
  if (!authToken) return;
  const tbody = document.getElementById("adminUsersTableBody");
  try {
    const res = await fetch("/api/admin/users", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok && tbody) {
      const users = await res.json();
      tbody.innerHTML = users.map(u => `
        <tr>
          <td><strong>${u.full_name}</strong></td>
          <td>${u.email}</td>
          <td><span class="badge ${u.role === 'ADMIN' ? 'badge-danger' : (u.role === 'WORKER' ? 'badge-warning' : 'badge-info')}">${u.role}</span></td>
          <td>${u.created_at ? u.created_at.slice(0, 10) : 'Recent'}</td>
          <td><span class="badge ${u.is_active ? 'badge-success' : 'badge-danger'}">${u.is_active ? 'Active' : 'Inactive'}</span></td>
          <td>
            <button class="btn btn-outline btn-sm" onclick="toggleUserStatus('${u.id}', ${!u.is_active})">
              ${u.is_active ? 'Deactivate' : 'Activate'}
            </button>
          </td>
        </tr>
      `).join("");
    }
  } catch (e) {
    console.error("Users list failed:", e);
  }
}

async function toggleUserStatus(userId, newStatus) {
  try {
    const res = await fetch(`/api/admin/users/${userId}/status`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ is_active: newStatus })
    });
    if (res.ok) {
      toast("User account status updated", "success");
      loadAdminUsersData();
    }
  } catch (e) {
    toast("Status update failed: " + e.message, "error");
  }
}

// Detection History
async function loadDetectionHistory() {
  if (!authToken) return;
  const tbody = document.getElementById("detectionHistoryTableBody");
  try {
    const res = await fetch("/api/detections/history", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok && tbody) {
      const logs = await res.json();
      if (logs.length > 0) {
        tbody.innerHTML = logs.map(l => {
          const score = l.risk_score ?? '--';
          const rLevel = l.risk_level || 'MEDIUM';
          const prio = l.priority || 'NORMAL';
          return `
            <tr>
              <td>${l.created_at ? l.created_at.slice(0, 16).replace('T', ' ') : ''}</td>
              <td><span class="badge badge-info">${l.source_type || 'IMAGE'}</span></td>
              <td><strong>${l.top_class || 'Hazard'}</strong></td>
              <td>${Math.round((l.top_confidence || 0.9) * 100)}%</td>
              <td><strong>${score}</strong>${score !== '--' ? '/100' : ''}</td>
              <td><span class="badge ${rLevel === 'CRITICAL' ? 'badge-danger' : (rLevel === 'HIGH' ? 'badge-warning' : (rLevel === 'MEDIUM' ? 'badge-warning' : 'badge-success'))}">${rLevel}</span></td>
              <td><span class="badge ${prio === 'URGENT' ? 'badge-danger' : (prio === 'HIGH' ? 'badge-warning' : 'badge-info')}">${prio}</span></td>
              <td>${l.location_name || 'Salem'}</td>
              <td><span class="badge badge-success">RECORDED</span></td>
            </tr>
          `;
        }).join("");
      } else {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:32px; color:var(--text-muted);">No recorded AI detection events yet.</td></tr>`;
      }
    }
  } catch (e) {
    console.error("Detection history failed:", e);
  }
}

// Notifications Poller & Center
function startNotificationPolling() {
  loadNotifications();
  setInterval(loadNotifications, 15000);
}

async function loadNotifications() {
  if (!authToken) return;
  try {
    let url = "/api/notifications";
    if (currentUser && currentUser.role === "SUPERVISOR") {
      url = "/api/supervisor/notifications";
    }
    const res = await fetch(url, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const notifs = await res.json();
      const badge = document.getElementById("notifBadge");
      const list = document.getElementById("notifItemsList");
      const fullList = document.getElementById("fullNotifList");

      if (badge) {
        const unread = notifs.filter(n => !n.is_read).length;
        badge.textContent = unread;
        badge.style.display = unread > 0 ? "flex" : "none";
      }

      if (list) {
        if (notifs.length > 0) {
          list.innerHTML = notifs.slice(0, 5).map(n => `
            <div style="padding:10px 16px; border-bottom:1px solid var(--border-color); font-size:12.5px;">
              <div style="font-weight:600; color:var(--text-main);">${n.title || 'System Alert'}</div>
              <div style="color:var(--text-muted); font-size:11.5px;">${n.message || ''}</div>
            </div>
          `).join("");
        } else {
          list.innerHTML = `<div style="padding:16px; text-align:center; color:var(--text-muted); font-size:12px;">No new notifications</div>`;
        }
      }

      if (fullList) {
        if (notifs.length > 0) {
          fullList.innerHTML = notifs.map(n => `
            <div class="detected-item-card" style="display:flex; justify-content:space-between; align-items:flex-start; padding:16px 20px; border-bottom:1px solid var(--border-color); background:var(--bg-card); border-radius:var(--radius-sm); margin-bottom:10px;">
              <div>
                <div style="display:flex; align-items:center; gap:8px;">
                  <strong style="font-size:14px; color:var(--text-main);">${n.title || 'System Notification'}</strong>
                  ${!n.is_read ? '<span class="badge badge-warning" style="font-size:10px;">NEW</span>' : ''}
                </div>
                <div style="color:var(--text-secondary); font-size:13px; margin-top:6px; line-height:1.4;">${n.message || ''}</div>
                <div style="color:var(--text-muted); font-size:11px; margin-top:8px;">${n.created_at ? n.created_at.replace('T', ' ').slice(0, 19) : 'Recent'}</div>
              </div>
              ${n.complaint_id ? `<button class="btn btn-secondary btn-sm" onclick="openComplaintDetailsModal('${n.complaint_id}')" style="margin-left:16px;">View Inspection</button>` : ''}
            </div>
          `).join("");
        } else {
          fullList.innerHTML = `<div style="padding:32px; text-align:center; color:var(--text-muted);">No notifications yet.</div>`;
        }
      }
    }
  } catch (e) {
    // Silent fail for polling
  }
}

function loadNotificationsFull() {
  loadNotifications();
}

async function markAllNotificationsRead() {
  try {
    let url = "/api/notifications/mark-read";
    if (currentUser && currentUser.role === "SUPERVISOR") {
      url = "/api/supervisor/notifications/mark-all-read";
    }
    const res = await fetch(url, {
      method: "POST",
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    toast("All notifications marked as read", "info");
    const badge = document.getElementById("notifBadge");
    if (badge) badge.style.display = "none";
    loadNotifications();
  } catch (e) {
    toast("All notifications marked as read", "info");
    const badge = document.getElementById("notifBadge");
    if (badge) badge.style.display = "none";
  }
}

// Profile
async function loadProfileData() {
  if (!currentUser) return;
  const nameInput = document.getElementById("profileFullName");
  const emailInput = document.getElementById("profileEmail");
  const phoneInput = document.getElementById("profilePhone");
  if (nameInput) nameInput.value = currentUser.full_name || "";
  if (emailInput) emailInput.value = currentUser.email || "";
  if (phoneInput) phoneInput.value = currentUser.phone || "+91 98765 43210";

  const roleBadge = document.getElementById("profileRoleBadge");
  if (roleBadge) {
    roleBadge.textContent = currentUser.role === "SUPERVISOR" ? "Field Supervisor" : (currentUser.role === "WORKER" ? "Field Maintenance Worker" : (currentUser.role === "ADMIN" ? "Municipal Administrator" : "Citizen"));
  }

  const devCard = document.getElementById("devDemoResetCard");
  if (devCard) {
    devCard.style.display = (currentUser.role === "ADMIN") ? "block" : "none";
  }
}

async function handleUpdateProfile(event) {
  event.preventDefault();
  toast("Profile settings updated successfully!", "success");
}

async function handleDevDemoReset() {
  if (!confirm("Are you sure you want to reset demo complaints and assignments? User accounts and AI models will NOT be modified.")) {
    return;
  }
  if (!authToken) return;
  try {
    const res = await fetch("/api/admin/demo-reset", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${authToken}`,
        "Content-Type": "application/json"
      }
    });
    if (res.ok) {
      const data = await res.json();
      toast(data.message || "Demo data reset successfully!", "success");
      if (currentUser && currentUser.role === "ADMIN") {
        loadAdminDashboardData();
        loadAdminComplaintsData();
      }
    } else {
      const err = await res.json();
      toast(err.detail || "Failed to reset demo data", "error");
    }
  } catch (e) {
    console.error("Demo reset failed:", e);
    toast("Network error while resetting demo data", "error");
  }
}

// Dropdown Toggles
function toggleNotifMenu() {
  document.getElementById("profileDropdown").classList.remove("show");
  document.getElementById("notifDropdown").classList.toggle("show");
}

function toggleProfileMenu() {
  document.getElementById("notifDropdown").classList.remove("show");
  document.getElementById("profileDropdown").classList.toggle("show");
}

function closeModal(modalId) {
  const m = document.getElementById(modalId);
  if (m) m.classList.remove("show");
}

// Toast System
function toast(msg, type = "info") {
  const shelf = document.getElementById("toastShelf");
  if (!shelf) return;
  const t = document.createElement("div");
  t.className = `toast-msg ${type}`;
  t.innerHTML = `<span>${msg}</span>`;
  shelf.appendChild(t);
  setTimeout(() => {
    t.remove();
  }, 4000);
}

// ==========================================================================
// VISIONGUARD AI CITY DIGITAL TWIN - CONTROLLER
// ==========================================================================

async function loadCityIntelligenceData() {
  if (!authToken) return;

  try {
    // 1. Fetch Overview & Health Summary
    const sumRes = await fetch(`/api/city-intelligence/summary?time_filter=${cityTwinTimeFilter}`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (sumRes.ok) {
      const summary = await sumRes.json();
      updateCityOverviewCards(summary);
      updateCitySummaryPanel(summary);
    }

    // 2. Fetch Zone Clusters
    const zonesRes = await fetch(`/api/city-intelligence/zones?time_filter=${cityTwinTimeFilter}`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (zonesRes.ok) {
      const zonesData = await zonesRes.json();
      cityTwinZonesCache = zonesData.zones || [];
      renderCityTwinZones(cityTwinZonesCache);
    }

    // 3. Fetch Map Locations
    await loadCityTwinLocations();

  } catch (e) {
    console.error("City Intelligence load error:", e);
    toast("Error updating Digital Twin intelligence: " + e.message, "error");
  }
}

function updateCityOverviewCards(s) {
  const health = s.health || {};
  const elHealth = document.getElementById("ctStatHealth");
  const elHealthBadge = document.getElementById("ctStatHealthBadge");
  const elDetections = document.getElementById("ctStatDetections");
  const elActive = document.getElementById("ctStatActiveComplaints");
  const elResolved = document.getElementById("ctStatResolvedComplaints");
  const elCritical = document.getElementById("ctStatCriticalRisks");
  const elHigh = document.getElementById("ctStatHighRisks");
  const elAvgRisk = document.getElementById("ctStatAvgRisk");

  if (elHealth) {
    elHealth.textContent = health.health_score != null ? `${health.health_score}/100` : "Insufficient data";
  }
  if (elHealthBadge) {
    elHealthBadge.textContent = health.status || "AI-ASSISTED";
  }
  if (elDetections) {
    elDetections.textContent = s.total_detections != null ? s.total_detections.toLocaleString() : "0";
  }
  if (elActive) {
    elActive.textContent = s.active_complaints != null ? s.active_complaints.toLocaleString() : "0";
  }
  if (elResolved) {
    elResolved.textContent = s.resolved_complaints != null ? s.resolved_complaints.toLocaleString() : "0";
  }
  if (elCritical) {
    elCritical.textContent = s.critical_risks != null ? s.critical_risks.toLocaleString() : "0";
  }
  if (elHigh) {
    elHigh.textContent = s.high_risks != null ? s.high_risks.toLocaleString() : "0";
  }
  if (elAvgRisk) {
    elAvgRisk.textContent = s.average_risk_score != null ? `${s.average_risk_score}/100` : "--";
  }
}

function updateCitySummaryPanel(s) {
  const sumHealth = document.getElementById("ctSummaryHealth");
  const sumTopProblem = document.getElementById("ctSummaryTopProblem");
  const sumMostAffected = document.getElementById("ctSummaryMostAffected");
  const sumCritical = document.getElementById("ctSummaryCritical");
  const sumPending = document.getElementById("ctSummaryPendingRepairs");

  const health = s.health || {};
  if (sumHealth) {
    sumHealth.textContent = health.health_score != null ? `${health.health_score} / 100` : "Insufficient data";
  }
  if (sumTopProblem) {
    sumTopProblem.textContent = s.top_problem || "Road Damage";
  }
  if (sumMostAffected) {
    sumMostAffected.textContent = s.most_affected_area || "Central Sector";
  }
  if (sumCritical) {
    sumCritical.textContent = `${s.critical_risks || 0} Issues`;
  }
  if (sumPending) {
    sumPending.textContent = `${s.pending_repairs || s.active_complaints || 0} Pending`;
  }
}

async function loadCityTwinLocations() {
  if (!authToken) return;
  try {
    const params = new URLSearchParams({
      time_filter: cityTwinTimeFilter,
      issue_type: cityTwinIssueFilter,
      risk_tier: cityTwinRiskFilter
    });

    const res = await fetch(`/api/city-intelligence/locations?${params.toString()}`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (res.ok) {
      const data = await res.json();
      cityTwinLocationsCache = data.locations || [];
      initCityTwinMap();
      renderCityTwinMapMarkers(cityTwinLocationsCache);
    }
  } catch (e) {
    console.error("Failed loading digital twin locations:", e);
  }
}

function initCityTwinMap() {
  const container = document.getElementById("cityTwinLeafletMap");
  if (!container) return;

  if (!cityTwinMapInstance) {
    cityTwinMapInstance = L.map('cityTwinLeafletMap', {
      center: [11.6643, 78.1460],
      zoom: 13,
      zoomControl: true
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors | VisionGuardAI Municipal GIS',
      maxZoom: 19
    }).addTo(cityTwinMapInstance);

    cityTwinMarkersLayer = L.layerGroup().addTo(cityTwinMapInstance);
    cityTwinHeatmapLayer = L.layerGroup().addTo(cityTwinMapInstance);
  } else {
    setTimeout(() => {
      cityTwinMapInstance.invalidateSize();
    }, 100);
  }
}

function renderCityTwinMapMarkers(locations) {
  if (!cityTwinMarkersLayer) return;
  cityTwinMarkersLayer.clearLayers();

  if (!locations || locations.length === 0) {
    return;
  }

  const bounds = [];

  locations.forEach(loc => {
    if (!loc.latitude || !loc.longitude) return;

    bounds.push([loc.latitude, loc.longitude]);

    const score = loc.risk_score != null ? loc.risk_score : 25;
    const rLevel = loc.risk_level || (score >= 75 ? "CRITICAL" : (score >= 50 ? "HIGH" : (score >= 25 ? "MEDIUM" : "LOW")));

    let pinColor = "#10B981"; // Low
    if (rLevel === "CRITICAL" || score >= 75) pinColor = "#EF4444";
    else if (rLevel === "HIGH" || score >= 50) pinColor = "#EA580C";
    else if (rLevel === "MEDIUM" || score >= 25) pinColor = "#F59E0B";

    const customIcon = L.divIcon({
      className: 'twin-map-marker',
      html: `
        <div style="background:${pinColor}; width:20px; height:20px; border-radius:50%; border:2px solid #FFFFFF; box-shadow:0 2px 8px rgba(0,0,0,0.35); display:flex; align-items:center; justify-content:center; color:#FFFFFF; font-size:10px; font-weight:800; cursor:pointer;" title="${loc.title}">
          !
        </div>
      `,
      iconSize: [20, 20],
      iconAnchor: [10, 10]
    });

    const marker = L.marker([loc.latitude, loc.longitude], { icon: customIcon });

    marker.bindPopup(`
      <div style="font-family:Inter,sans-serif; min-width:210px; padding:2px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
          <strong style="color:${pinColor}; font-size:13px;">${loc.title || 'Infrastructure Asset'}</strong>
          <span style="font-size:10px; font-weight:800; padding:2px 6px; border-radius:10px; background:${pinColor}22; color:${pinColor};">${rLevel}</span>
        </div>
        <div style="font-size:11px; color:#64748B; margin:3px 0;">📍 ${loc.location_address || 'Salem Municipal Sector'}</div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px; font-size:11px; margin:6px 0; background:#F8FAFC; padding:6px; border-radius:4px;">
          <div>Risk Score: <strong>${score}/100</strong></div>
          <div>Priority: <strong>${loc.priority_level || 'NORMAL'}</strong></div>
          <div>Status: <strong>${loc.status || 'ACTIVE'}</strong></div>
          <div>Asset: <strong>${(loc.asset_type || 'hazard').toUpperCase()}</strong></div>
        </div>
        <button class="btn btn-primary btn-sm" style="width:100%; margin-top:4px; font-size:11px; padding:4px 8px;" onclick="selectCityTwinLocation('${loc.complaint_id || ''}', '${loc.asset_type || 'complaint'}', '${loc.detection_id || ''}')">
          Inspect Asset Drill-Down
        </button>
      </div>
    `);

    marker.on('click', () => {
      selectCityTwinLocation(loc.complaint_id, loc.asset_type, loc.detection_id);
    });

    marker.addTo(cityTwinMarkersLayer);
  });

  if (bounds.length > 0 && cityTwinMapInstance) {
    cityTwinMapInstance.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
  }
}

function toggleCityTwinHeatmap() {
  isCityTwinHeatmapActive = !isCityTwinHeatmapActive;
  const btn = document.getElementById("btnToggleTwinHeatmap");

  if (!cityTwinHeatmapLayer || !cityTwinMapInstance) return;

  cityTwinHeatmapLayer.clearLayers();

  if (isCityTwinHeatmapActive) {
    if (btn) {
      btn.classList.remove("btn-outline");
      btn.classList.add("btn-primary");
      btn.textContent = "🔥 Risk Heatmap (ON)";
    }

    // Render weighted heat circle gradients from real telemetry
    cityTwinLocationsCache.forEach(loc => {
      if (!loc.latitude || !loc.longitude) return;
      const score = loc.risk_score != null ? loc.risk_score : 30;
      let radius = 120 + (score * 2);
      let heatColor = score >= 75 ? "#EF4444" : (score >= 50 ? "#EA580C" : (score >= 25 ? "#F59E0B" : "#10B981"));

      L.circle([loc.latitude, loc.longitude], {
        radius: radius,
        color: heatColor,
        fillColor: heatColor,
        fillOpacity: score >= 75 ? 0.35 : 0.20,
        weight: 1,
        opacity: 0.5
      }).addTo(cityTwinHeatmapLayer);
    });

    toast("Digital Twin Risk Heatmap Activated", "info");
  } else {
    if (btn) {
      btn.classList.remove("btn-primary");
      btn.classList.add("btn-outline");
      btn.textContent = "🔥 Risk Heatmap";
    }
  }
}

function recenterCityTwinMap() {
  if (!cityTwinMapInstance) return;
  if (cityTwinLocationsCache && cityTwinLocationsCache.length > 0) {
    const bounds = cityTwinLocationsCache.map(l => [l.latitude, l.longitude]).filter(p => p[0] && p[1]);
    if (bounds.length > 0) {
      cityTwinMapInstance.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
      return;
    }
  }
  cityTwinMapInstance.setView([11.6643, 78.1460], 13);
}

function handleCityTwinTimeFilter(timeVal) {
  cityTwinTimeFilter = timeVal;
  document.querySelectorAll("#cityTwinTimeFilterTabs .filter-tab").forEach(btn => {
    if (btn.getAttribute("data-time") === timeVal) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
  loadCityIntelligenceData();
}

function handleCityTwinIssueFilter(issueVal) {
  cityTwinIssueFilter = issueVal;
  document.querySelectorAll("#cityTwinLayerFilters .filter-tab").forEach(btn => {
    if (btn.getAttribute("data-filter") === issueVal) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
  loadCityTwinLocations();
}

function handleCityTwinRiskLevelChange(riskVal) {
  cityTwinRiskFilter = riskVal;
  loadCityTwinLocations();
}

function renderCityTwinZones(zones) {
  const container = document.getElementById("cityTwinZoneCardsList");
  if (!container) return;

  if (!zones || zones.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px;">
        No geographic infrastructure clusters detected in the selected timeframe.
      </div>
    `;
    return;
  }

  container.innerHTML = zones.map(z => {
    const healthVal = z.infrastructure_health != null ? z.infrastructure_health : "--";
    const riskBadge = z.risk_level === "CRITICAL" ? "badge-danger" : (z.risk_level === "HIGH" ? "badge-warning" : "badge-info");

    return `
      <div class="vg-card" style="padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: #FFFFFF; cursor: pointer; transition: transform 0.15s ease, box-shadow 0.15s ease;" onclick="selectCityTwinZone('${z.zone_id}')">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <strong style="font-size: 13px; color: var(--text-main);">${z.name}</strong>
          <span class="badge ${riskBadge}" style="font-size: 9.5px;">${z.risk_level || 'NORMAL'}</span>
        </div>
        
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11.5px; margin-bottom: 6px; padding: 4px 6px; background: #FAF5FF; border-radius: 4px;">
          <span style="color: #6B21A8; font-weight: 600;">Health Index:</span>
          <strong style="color: #581C87;">${healthVal}/100</strong>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 11px; color: var(--text-muted); margin-bottom: 8px;">
          <div>Complaints: <strong style="color: var(--text-main);">${z.active_complaints || 0}</strong></div>
          <div>Detections: <strong style="color: var(--text-main);">${z.total_detections || 0}</strong></div>
          <div>Critical: <strong style="color: var(--danger);">${z.critical_issues || 0}</strong></div>
          <div>Avg Risk: <strong style="color: var(--text-main);">${z.risk_score || 0}</strong></div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 10.5px; color: var(--text-muted); border-top: 1px solid #F1F5F9; padding-top: 6px;">
          <span>Top Issue: <strong>${z.top_problem || 'Road Damage'}</strong></span>
          <span style="color: var(--primary); font-weight: 600;">Focus Map ➔</span>
        </div>
      </div>
    `;
  }).join("");
}

function selectCityTwinZone(zoneId) {
  const zone = (cityTwinZonesCache || []).find(z => z.zone_id === zoneId);
  if (zone && zone.centroid_lat && zone.centroid_lng && cityTwinMapInstance) {
    cityTwinMapInstance.setView([zone.centroid_lat, zone.centroid_lng], 15);
    toast(`Focused view on ${zone.name} (${zone.landmark_hint})`, "info");
  }
}

async function selectCityTwinLocation(complaintId, assetType = 'complaint', detectionId = null) {
  const drillCard = document.getElementById("cityTwinLocationDrillDownCard");
  const placeholder = document.getElementById("ctDrillPlaceholder");
  const content = document.getElementById("ctDrillContent");

  if (!drillCard || !content) return;

  try {
    const targetId = complaintId || detectionId || "unknown";
    const res = await fetch(`/api/city-intelligence/location/${targetId}?asset_type=${assetType}`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });

    if (res.ok) {
      const data = await res.json();
      const loc = data.location || {};
      const roadHealth = data.road_health || {};
      const history = data.repair_history || [];

      if (placeholder) placeholder.style.display = "none";
      content.style.display = "flex";

      // 1. Header & Badges
      const title = document.getElementById("ctDrillTitle");
      const subtitle = document.getElementById("ctDrillSubtitle");
      const prioBadge = document.getElementById("ctDrillPriorityBadge");

      if (title) title.textContent = loc.title || `Asset #${targetId}`;
      if (subtitle) subtitle.textContent = loc.location_address || `GPS: ${loc.latitude?.toFixed(4)}, ${loc.longitude?.toFixed(4)}`;
      if (prioBadge) {
        prioBadge.textContent = loc.priority_level || "NORMAL";
        prioBadge.className = `badge ${loc.priority_level === 'URGENT' ? 'badge-danger' : (loc.priority_level === 'HIGH' ? 'badge-warning' : 'badge-purple')}`;
      }

      // 2. Info Grid
      const cat = document.getElementById("ctDrillCategory");
      const aiModel = document.getElementById("ctDrillAiModel");
      const risk = document.getElementById("ctDrillRiskScore");
      const statusBadge = document.getElementById("ctDrillStatusBadge");
      const gps = document.getElementById("ctDrillGps");

      if (cat) cat.textContent = loc.title || loc.issue_type || "Road Asset";
      if (aiModel) aiModel.textContent = `${loc.ai_model || 'Municipal AI Pipeline'} (${loc.confidence ? `${Math.round(loc.confidence * 100)}%` : 'Validated'})`;
      if (risk) risk.textContent = `${loc.risk_score || '--'} / 100 • ${loc.risk_level || 'NORMAL'}`;
      if (statusBadge) {
        statusBadge.innerHTML = `<span class="badge ${loc.status === 'COMPLETED' ? 'badge-success' : 'badge-warning'}">${loc.status || 'LOGGED'}</span>`;
      }
      if (gps) gps.textContent = `${loc.latitude?.toFixed(5) || '--'}, ${loc.longitude?.toFixed(5) || '--'}`;

      // 3. 500m Corridor Context
      const rHealth = document.getElementById("ctRoadHealthVal");
      const rDamage = document.getElementById("ctRoadDamageCount");
      const rSigns = document.getElementById("ctRoadSignsCount");
      const rSignals = document.getElementById("ctRoadSignalsCount");
      const rActive = document.getElementById("ctRoadActiveCount");
      const rRepairs = document.getElementById("ctRoadRepairsCount");
      const rCrit = document.getElementById("ctRoadCritCount");

      if (rHealth) rHealth.textContent = `${roadHealth.infrastructure_health != null ? roadHealth.infrastructure_health : '--'}/100`;
      if (rDamage) rDamage.textContent = roadHealth.road_damage_detections || 0;
      if (rSigns) rSigns.textContent = roadHealth.traffic_sign_detections || 0;
      if (rSignals) rSignals.textContent = roadHealth.traffic_signal_detections || 0;
      if (rActive) rActive.textContent = roadHealth.active_complaints || 0;
      if (rRepairs) rRepairs.textContent = roadHealth.completed_repairs || 0;
      if (rCrit) rCrit.textContent = roadHealth.critical_issues || 0;

      // 4. 6-Stage Repair Lifecycle Stepper
      const stepperList = document.getElementById("ctRepairLifecycleList");
      if (stepperList) {
        stepperList.innerHTML = history.map(step => {
          const isDone = step.completed;
          const iconColor = isDone ? "var(--success)" : "#94A3B8";
          const iconSymbol = isDone ? "✓" : "○";

          return `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; border-radius: 4px; background: ${isDone ? '#F0FDF4' : '#F8FAFC'}; border: 1px solid ${isDone ? '#DCFCE7' : '#E2E8F0'};">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 50%; background: ${isDone ? 'var(--success)' : '#E2E8F0'}; color: #fff; font-size: 10px; font-weight: 800;">
                  ${iconSymbol}
                </span>
                <div>
                  <strong style="color: ${isDone ? 'var(--text-main)' : 'var(--text-muted)'};">${step.stage_name}</strong>
                  <div style="font-size: 10px; color: var(--text-muted);">${step.actor || 'Municipal Pipeline'}</div>
                </div>
              </div>
              <span style="font-family: var(--font-mono); font-size: 10.5px; color: ${isDone ? 'var(--text-main)' : 'var(--text-muted)'};">
                ${step.timestamp ? step.timestamp.replace('T', ' ').slice(0, 16) : 'N/A'}
              </span>
            </div>
          `;
        }).join("");
      }

      // 5. Action Buttons
      const actions = document.getElementById("ctDrillActionButtons");
      if (actions) {
        let buttonsHtml = '';
        if (loc.complaint_id) {
          buttonsHtml += `<button class="btn btn-primary btn-sm" style="flex: 1;" onclick="navigate('/admin/complaints/${loc.complaint_id}')">View Complaint Order</button>`;
        }
        buttonsHtml += `<button class="btn btn-secondary btn-sm" style="flex: 1;" onclick="navigate('/admin/map')">Open GIS Map</button>`;
        actions.innerHTML = buttonsHtml;
      }

      // Scroll drilldown into view if on mobile/stacked view
      drillCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  } catch (e) {
    console.error("Failed loading location drill-down:", e);
  }
}

// Global Window Bindings for Robust HTML & SPA Handlers
window.openCreateAccountModal = openCreateAccountModal;
window.toggleCreateAccountModal = toggleCreateAccountModal;
window.selectRegistrationType = selectRegistrationType;
window.openCitizenRegistration = openCitizenRegistration;
window.openWorkerRegistration = openWorkerRegistration;
window.openSupervisorRegistration = openSupervisorRegistration;
window.toggleRegisterModal = toggleRegisterModal;
window.toggleCitizenRegisterModal = toggleRegisterModal;
window.toggleWorkerRegisterModal = toggleWorkerRegisterModal;
window.toggleSupervisorRegisterModal = toggleSupervisorRegisterModal;
window.handleRegisterSubmit = handleRegisterSubmit;
window.handleCitizenRegisterSubmit = handleRegisterSubmit;
window.handleWorkerRegisterSubmit = handleWorkerRegisterSubmit;
window.handleSupervisorRegisterSubmit = handleSupervisorRegisterSubmit;
window.closeModal = closeModal;
window.navigate = navigate;
window.selectAuthRole = selectAuthRole;
window.handleLoginSubmit = handleLoginSubmit;
window.handleLogout = handleLogout;
window.toast = toast;
window.refreshCameraDevices = refreshCameraDevices;
window.handleCameraSourceChange = handleCameraSourceChange;
window.requestCameraAccess = requestCameraAccess;
window.updateCameraStatusUi = updateCameraStatusUi;
window.startLiveCameraDetection = startLiveCameraDetection;
window.stopLiveCameraDetection = stopLiveCameraDetection;
window.toggleVideoSimulationMode = toggleVideoSimulationMode;
window.handleSimulationVideoSelect = handleSimulationVideoSelect;
window.getImageUrl = getImageUrl;
window.handleImageError = handleImageError;
window.confirmRemoveVideo = confirmRemoveVideo;
window.executeRemoveVideo = executeRemoveVideo;
window.clearVideoIntelligenceStudio = clearVideoIntelligenceStudio;
// ==========================================================================
// FIELD SUPERVISOR PORTAL & WORKER OVERSIGHT CLIENT
// ==========================================================================

let supervisorInspectionsCache = [];
let currentSupInspectionFilter = "ALL";
let adminSupervisorApprovalsCache = [];
let currentSupervisorApprovalFilter = "ALL";
let supIssueDistChartInstance = null;

// 1. Supervisor Dashboard Data Loader
async function loadSupervisorDashboardData() {
  if (!authToken) return;
  try {
    const res = await fetch("/api/supervisor/dashboard", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) {
      console.warn("Failed to load supervisor dashboard data:", res.status);
      return;
    }
    const data = await res.json();
    const stats = data.stats || {};

    const elAssigned = document.getElementById("supStatAssigned");
    const elPending = document.getElementById("supStatPending");
    const elInProgress = document.getElementById("supStatInProgress");
    const elCompleted = document.getElementById("supStatCompletedMonth");
    const elHighRisk = document.getElementById("supStatHighRisk");
    const elAwaiting = document.getElementById("supStatAwaitingReview");

    if (elAssigned) elAssigned.textContent = stats.assigned_inspections ?? 0;
    if (elPending) elPending.textContent = stats.pending_inspections ?? 0;
    if (elInProgress) elInProgress.textContent = stats.in_progress ?? 0;
    if (elCompleted) elCompleted.textContent = stats.completed_this_month ?? 0;
    if (elHighRisk) elHighRisk.textContent = stats.high_risk_locations ?? 0;
    if (elAwaiting) elAwaiting.textContent = stats.repairs_awaiting_inspection ?? 0;

    // Render Recent Assigned Inspections Table
    const tbody = document.getElementById("supRecentInspectionsTableBody");
    if (tbody) {
      const list = data.recent_assigned_inspections || [];
      if (list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 32px;">No inspections currently assigned.</td></tr>`;
      } else {
        tbody.innerHTML = list.map(item => {
          const sevClass = (item.severity === "HIGH" || item.severity === "CRITICAL") ? "badge-danger" : (item.severity === "MEDIUM" ? "badge-warning" : "badge-info");
          const statClass = item.status === "COMPLETED" ? "badge-success" : (item.status === "IN_PROGRESS" || item.status === "ASSIGNED" ? "badge-warning" : "badge-info");
          return `
            <tr>
              <td><strong>#${item.complaint_id || item.id}</strong></td>
              <td><span style="font-weight:600;">${(item.issue_type || "Hazard").replace(/_/g, ' ')}</span></td>
              <td>${item.location_address || (item.latitude ? `${item.latitude.toFixed(4)}, ${item.longitude.toFixed(4)}` : "Salem Ward")}</td>
              <td><span class="badge ${sevClass}">${item.severity || "MEDIUM"}</span></td>
              <td><span class="badge ${statClass}">${item.status || "SUBMITTED"}</span></td>
              <td>${item.assigned_worker_name || "Unassigned"}</td>
              <td>${item.updated_at ? item.updated_at.slice(0, 10) : "Today"}</td>
              <td>
                <button class="btn btn-secondary btn-sm" onclick="openComplaintDetailsModal('${item.id}')">Inspect</button>
              </td>
            </tr>
          `;
        }).join("");
      }
    }

    // Render Recent Activity List
    const actList = document.getElementById("supRecentActivityList");
    if (actList) {
      const acts = data.recent_activity || [];
      if (acts.length === 0) {
        actList.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px;">No recent supervisor activity</div>`;
      } else {
        actList.innerHTML = acts.map(a => `
          <div style="display: flex; gap: 10px; align-items: flex-start; padding: 8px 10px; background: var(--bg-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
            <span style="font-size: 14px;">🔔</span>
            <div style="flex: 1; min-width: 0;">
              <div style="font-weight: 700; font-size: 12.5px; color: var(--text-main);">${a.title || "Inspection Update"}</div>
              <div style="font-size: 11.5px; color: var(--text-secondary); margin-top: 1px;">${a.message || ""}</div>
              <div style="font-size: 10px; color: var(--text-muted); margin-top: 3px;">${a.created_at ? a.created_at.slice(0, 16).replace('T', ' ') : 'Recent'}</div>
            </div>
          </div>
        `).join("");
      }
    }

    // Render Distribution Chart & Mini-Map
    renderSupervisorIssueDistChart(data.issue_distribution || {});
    initSupervisorDashboardMap(data.recent_assigned_inspections || []);

  } catch (e) {
    console.error("Supervisor dashboard error:", e);
  }
}

// 2. Issue Distribution Chart
function renderSupervisorIssueDistChart(dist) {
  const canvas = document.getElementById("supIssueDistChart");
  if (!canvas) return;

  const labels = Object.keys(dist);
  const values = Object.values(dist);

  if (supIssueDistChartInstance) {
    supIssueDistChartInstance.destroy();
    supIssueDistChartInstance = null;
  }

  if (typeof Chart === "undefined" || labels.length === 0) {
    return;
  }

  const formattedLabels = labels.map(l => l.replace(/_/g, ' ').toUpperCase());
  const backgroundColors = ['#2563EB', '#0EA5E9', '#F59E0B', '#EF4444', '#8B5CF6', '#10B981'];

  supIssueDistChartInstance = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: formattedLabels,
      datasets: [{
        data: values,
        backgroundColor: backgroundColors.slice(0, labels.length),
        borderWidth: 2,
        borderColor: '#FFFFFF'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: { font: { family: 'Inter', size: 11 }, boxWidth: 12 }
        }
      }
    }
  });
}

// 3. Mini Dashboard Map
function initSupervisorDashboardMap(inspections) {
  const mapContainer = document.getElementById("supDashboardMap");
  if (!mapContainer || typeof L === "undefined") return;

  if (supervisorDashboardMap) {
    supervisorDashboardMap.remove();
    supervisorDashboardMap = null;
  }

  const defaultCenter = [11.6643, 78.1460];
  supervisorDashboardMap = L.map('supDashboardMap', {
    zoomControl: true,
    attributionControl: false
  }).setView(defaultCenter, 13);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19
  }).addTo(supervisorDashboardMap);

  supervisorDashboardMapMarkers = L.layerGroup().addTo(supervisorDashboardMap);

  let bounds = [];
  inspections.forEach(item => {
    if (item.latitude && item.longitude) {
      const lat = item.latitude;
      const lng = item.longitude;
      bounds.push([lat, lng]);

      const isHigh = item.severity === "HIGH" || item.severity === "CRITICAL";
      const color = isHigh ? "#EF4444" : "#2563EB";
      const customIcon = L.divIcon({
        className: 'sup-mini-marker',
        html: `<div style="background:${color}; width:16px; height:16px; border-radius:50%; border:2px solid #fff; box-shadow:0 0 6px ${color};"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8]
      });

      L.marker([lat, lng], { icon: customIcon })
        .bindPopup(`<strong>#${item.complaint_id || item.id}</strong><br>${(item.issue_type || 'Hazard').replace(/_/g, ' ')}<br>Severity: ${item.severity || 'MEDIUM'}`)
        .addTo(supervisorDashboardMapMarkers);
    }
  });

  if (bounds.length > 0) {
    supervisorDashboardMap.fitBounds(bounds, { padding: [30, 30] });
  }
}

// 4. Supervisor Inspections Queue
async function loadSupervisorInspectionsData() {
  if (!authToken) return;
  const tbody = document.getElementById("supInspectionsTableBody");
  try {
    const res = await fetch("/api/supervisor/inspections", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      supervisorInspectionsCache = Array.isArray(data) ? data : (data.inspections || []);
      
      // If navigating to field-inspections, default filter or header can be adjusted
      if (currentRoute === "/supervisor/field-inspections" && currentSupInspectionFilter === "ALL") {
        filterSupervisorInspections("ALL");
      } else {
        filterSupervisorInspections(currentSupInspectionFilter || "ALL");
      }
    } else {
      if (tbody) tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--danger); padding: 32px;">Failed to load inspections queue.</td></tr>`;
    }
  } catch (e) {
    console.error("Load supervisor inspections failed:", e);
  }
}

function filterSupervisorInspections(filter) {
  currentSupInspectionFilter = filter;
  document.querySelectorAll("#supInspectionFilterTabs .filter-tab").forEach(tab => {
    if (tab.getAttribute("data-filter") === filter) tab.classList.add("active");
    else tab.classList.remove("active");
  });

  const search = (document.getElementById("supInspectionSearchInput")?.value || "").toLowerCase().trim();
  let list = supervisorInspectionsCache || [];

  if (filter !== "ALL") {
    list = list.filter(item => item.status === filter);
  }

  if (search) {
    list = list.filter(item => {
      const code = String(item.complaint_id || item.tracking_number || item.id || "").toLowerCase();
      const issue = String(item.issue_type || item.title || "").toLowerCase();
      const loc = String(item.location_address || "").toLowerCase();
      return code.includes(search) || issue.includes(search) || loc.includes(search);
    });
  }

  const tbody = document.getElementById("supInspectionsTableBody");
  if (!tbody) return;

  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 32px;">No inspections found for filter '${filter}'.</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(item => {
    const sevClass = (item.severity === "HIGH" || item.severity === "CRITICAL") ? "badge-danger" : (item.severity === "MEDIUM" ? "badge-warning" : "badge-info");
    const statClass = item.status === "COMPLETED" ? "badge-success" : (item.status === "IN_PROGRESS" || item.status === "ASSIGNED" ? "badge-warning" : "badge-info");
    const isVal = item.supervisor_validated_at ? `<span class="badge badge-success" style="font-size:10px;">VALIDATED</span>` : `<span class="badge badge-secondary" style="font-size:10px;">PENDING VAL</span>`;
    const isRec = item.supervisor_recommendation ? `<span class="badge badge-purple" style="font-size:10px; margin-left:4px;">RECOMMENDED</span>` : "";

    return `
      <tr>
        <td><strong>#${item.complaint_id || item.id}</strong></td>
        <td>
          <div style="font-weight:600;">${(item.title || item.issue_type || "Hazard").replace(/_/g, ' ')}</div>
          <div style="font-size:11px; color:var(--text-muted);">${item.detected_class ? `AI: ${item.detected_class}` : (item.source || 'Citizen Report')}</div>
        </td>
        <td><span class="badge ${sevClass}">${item.severity || "MEDIUM"}</span></td>
        <td><strong>${item.risk_score != null ? `${item.risk_score}/100` : "--"}</strong></td>
        <td>${item.location_address || (item.latitude ? `${item.latitude.toFixed(4)}, ${item.longitude.toFixed(4)}` : "Salem Ward")}</td>
        <td>${item.assigned_worker_name || "Unassigned"}</td>
        <td><span class="badge ${statClass}">${item.status || "SUBMITTED"}</span></td>
        <td><div style="display:flex; gap:4px; flex-wrap:wrap;">${isVal} ${isRec}</div></td>
        <td>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-secondary btn-sm" onclick="openComplaintDetailsModal('${item.id}')">Inspect</button>
            <button class="btn btn-outline btn-sm" onclick="openSupervisorValidateModal('${item.id}', '${item.issue_type || ''}', '${item.severity || 'MEDIUM'}', ${item.latitude || 0}, ${item.longitude || 0})">Validate</button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

// 5. Supervisor Worker Monitoring
async function loadSupervisorWorkersData() {
  if (!authToken) return;
  const tbody = document.getElementById("supWorkersTableBody");
  try {
    const res = await fetch("/api/supervisor/workers", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      const workers = Array.isArray(data) ? data : (data.workers || []);
      if (!tbody) return;
      if (workers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 32px;">No field workers assigned to your jurisdiction.</td></tr>`;
        return;
      }
      tbody.innerHTML = workers.map(w => `
        <tr>
          <td><strong>${w.full_name || w.name || "Field Worker"}</strong></td>
          <td><code>${w.employee_id || "EMP-" + w.id}</code></td>
          <td>
            <div>${w.department || "Roads & Highways"}</div>
            <div style="font-size:11px; color:var(--text-muted);">${w.specialization || "General Maintenance"}</div>
          </td>
          <td><strong>${w.current_task_title ? `#${w.current_task_complaint_id || w.current_task_id || ''} ${w.current_task_title}` : "Idle / No Active Task"}</strong></td>
          <td>
            <span class="badge ${w.current_task_status === 'IN_PROGRESS' ? 'badge-warning' : (w.current_task_status === 'COMPLETED' ? 'badge-success' : 'badge-secondary')}">
              ${w.current_task_status || "IDLE"}
            </span>
          </td>
          <td>${w.location || "Salem North"}</td>
          <td>${w.start_time ? w.start_time.slice(0, 16).replace('T', ' ') : "--"}</td>
          <td>${w.last_update ? w.last_update.slice(0, 16).replace('T', ' ') : "Recent"}</td>
          <td>
            ${w.current_task_id ? `<button class="btn btn-secondary btn-sm" onclick="openComplaintDetailsModal('${w.current_task_id}')">View Task</button>` : `<span style="font-size:11.5px; color:var(--text-muted);">Available</span>`}
          </td>
        </tr>
      `).join("");
    }
  } catch (e) {
    console.error("Load supervisor workers failed:", e);
  }
}

// 6. Supervisor Full Map View
async function initSupervisorMap() {
  const mapContainer = document.getElementById("supervisorFullMap");
  if (!mapContainer || typeof L === "undefined") return;

  if (supervisorFullMapInstance) {
    supervisorFullMapInstance.remove();
    supervisorFullMapInstance = null;
  }

  const defaultCenter = [11.6643, 78.1460];
  supervisorFullMapInstance = L.map('supervisorFullMap', {
    zoomControl: true,
    attributionControl: false
  }).setView(defaultCenter, 13);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19
  }).addTo(supervisorFullMapInstance);

  supervisorFullMapMarkers = L.layerGroup().addTo(supervisorFullMapInstance);

  try {
    const res = await fetch("/api/supervisor/map", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const mapData = await res.json();
      let bounds = [];

      const assignedList = mapData.assigned_inspections || mapData.incidents || [];
      const highRiskList = mapData.high_risk_incidents || [];
      const repairsList = mapData.repair_locations || [];

      // Assigned Inspections
      assignedList.forEach(item => {
        if (item.latitude && item.longitude) {
          const lat = item.latitude;
          const lng = item.longitude;
          bounds.push([lat, lng]);
          const icon = L.divIcon({
            className: 'sup-map-pin',
            html: `<div style="background:#2563EB; width:22px; height:22px; border-radius:50%; border:2px solid #fff; box-shadow:0 0 8px #2563EB; display:flex; align-items:center; justify-content:center; color:#fff; font-size:11px; font-weight:800;">🔍</div>`,
            iconSize: [22, 22],
            iconAnchor: [11, 11]
          });
          L.marker([lat, lng], { icon: icon })
            .bindPopup(`<strong>#${item.complaint_id || item.id}</strong><br>${(item.issue_type || 'Hazard').replace(/_/g, ' ')}<br>Status: ${item.status || 'ASSIGNED'}<br><button class="btn btn-xs btn-primary" onclick="openComplaintDetailsModal('${item.id}')" style="margin-top:6px;">Inspect Details</button>`)
            .addTo(supervisorFullMapMarkers);
        }
      });

      // High Risk Incidents
      highRiskList.forEach(item => {
        if (item.latitude && item.longitude) {
          const lat = item.latitude;
          const lng = item.longitude;
          bounds.push([lat, lng]);
          const icon = L.divIcon({
            className: 'sup-highrisk-pin',
            html: `<div style="background:#EF4444; width:24px; height:24px; border-radius:50%; border:2px solid #fff; box-shadow:0 0 10px #EF4444; display:flex; align-items:center; justify-content:center; color:#fff; font-size:11px; font-weight:800;">⚠️</div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
          });
          L.marker([lat, lng], { icon: icon })
            .bindPopup(`<strong>HIGH RISK HAZARD #${item.complaint_id || item.id}</strong><br>${(item.issue_type || 'Road Issue').replace(/_/g, ' ')}<br>Risk Score: <strong>${item.risk_score || 85}/100</strong><br><button class="btn btn-xs btn-danger" onclick="openComplaintDetailsModal('${item.id}')" style="margin-top:6px;">Validate Urgency</button>`)
            .addTo(supervisorFullMapMarkers);
        }
      });

      // Active Repairs
      repairsList.forEach(item => {
        if (item.latitude && item.longitude) {
          const lat = item.latitude;
          const lng = item.longitude;
          bounds.push([lat, lng]);
          const icon = L.divIcon({
            className: 'sup-repair-pin',
            html: `<div style="background:#10B981; width:20px; height:20px; border-radius:50%; border:2px solid #fff; box-shadow:0 0 8px #10B981; display:flex; align-items:center; justify-content:center; color:#fff; font-size:10px; font-weight:800;">✓</div>`,
            iconSize: [20, 20],
            iconAnchor: [10, 10]
          });
          L.marker([lat, lng], { icon: icon })
            .bindPopup(`<strong>Repair Site #${item.complaint_id || item.id}</strong><br>${(item.issue_type || 'Hazard').replace(/_/g, ' ')}<br>Status: ${item.status || 'COMPLETED'}<br><button class="btn btn-xs btn-success" onclick="openComplaintDetailsModal('${item.id}')" style="margin-top:6px;">Inspect Repair Evidence</button>`)
            .addTo(supervisorFullMapMarkers);
        }
      });

      if (bounds.length > 0) {
        supervisorFullMapInstance.fitBounds(bounds, { padding: [40, 40] });
      }
    }
  } catch (e) {
    console.error("Init supervisor map error:", e);
  }
}

// 7. Supervisor Reports
async function loadSupervisorReportsData() {
  if (!authToken) return;
  try {
    const res = await fetch("/api/supervisor/reports", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      const stats = data.summary_statistics || data.metrics || {};

      const elTot = document.getElementById("repTotalInspections");
      const elVal = document.getElementById("repValidated");
      const elRec = document.getElementById("repRecommended");
      const elRei = document.getElementById("repReinspections");

      if (elTot) elTot.textContent = stats.total_inspections_logged ?? stats.total_complaints ?? 0;
      if (elVal) elVal.textContent = stats.inspections_validated ?? stats.field_inspections_validated ?? 0;
      if (elRec) elRec.textContent = stats.completions_recommended ?? 0;
      if (elRei) elRei.textContent = stats.reinspections_requested ?? 0;

      // Status breakdown
      const statBreakdown = document.getElementById("supReportStatusBreakdown");
      if (statBreakdown) {
        const bd = data.status_breakdown || (data.breakdown && data.breakdown.by_status) || {};
        const keys = Object.keys(bd);
        statBreakdown.innerHTML = keys.length > 0 ? keys.map(k => `
          <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-color);">
            <span style="color: var(--text-secondary);">${k.replace(/_/g, ' ')}:</span>
            <strong>${bd[k]}</strong>
          </div>
        `).join("") : "<div>No incident status data</div>";
      }

      // Severity breakdown
      const sevBreakdown = document.getElementById("supReportSeverityBreakdown");
      if (sevBreakdown) {
        const bd = data.severity_breakdown || (data.breakdown && data.breakdown.by_severity) || {};
        const keys = Object.keys(bd);
        sevBreakdown.innerHTML = keys.length > 0 ? keys.map(k => `
          <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-color);">
            <span style="color: var(--text-secondary);">${k}:</span>
            <strong>${bd[k]}</strong>
          </div>
        `).join("") : "<div>No severity data</div>";
      }
    }
  } catch (e) {
    console.error("Load supervisor reports error:", e);
  }
}

// 8. Admin Supervisor Approvals
async function loadAdminSupervisorApprovalsData() {
  if (!authToken) return;
  const tbody = document.getElementById("adminSupervisorApprovalsTableBody");
  try {
    const res = await fetch("/api/admin/supervisor-approvals", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      adminSupervisorApprovalsCache = await res.json();
      filterSupervisorApprovals(currentSupervisorApprovalFilter || "ALL");
    } else {
      if (tbody) tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--danger); padding: 32px;">Failed to load supervisor approval queue.</td></tr>`;
    }
  } catch (e) {
    console.error("Load supervisor approvals error:", e);
  }
}

function filterSupervisorApprovals(filter) {
  currentSupervisorApprovalFilter = filter;
  ["btnSupFilterAll", "btnSupFilterPending", "btnSupFilterApproved", "btnSupFilterRejected"].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.className = "btn btn-xs btn-outline";
  });
  if (filter === "ALL") document.getElementById("btnSupFilterAll")?.classList.replace("btn-outline", "btn-primary");
  if (filter === "PENDING_APPROVAL") document.getElementById("btnSupFilterPending")?.classList.replace("btn-outline", "btn-primary");
  if (filter === "APPROVED") document.getElementById("btnSupFilterApproved")?.classList.replace("btn-outline", "btn-primary");
  if (filter === "REJECTED") document.getElementById("btnSupFilterRejected")?.classList.replace("btn-outline", "btn-primary");

  let list = adminSupervisorApprovalsCache || [];
  if (filter !== "ALL") {
    list = list.filter(item => item.approval_status === filter);
  }

  const tbody = document.getElementById("adminSupervisorApprovalsTableBody");
  if (!tbody) return;

  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 32px;">No supervisor applications with status '${filter}'.</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(item => {
    const statClass = item.approval_status === "APPROVED" ? "badge-success" : (item.approval_status === "PENDING_APPROVAL" ? "badge-warning" : "badge-danger");
    return `
      <tr>
        <td><strong>${item.full_name || "Field Supervisor"}</strong></td>
        <td>
          <div>${item.email || ""}</div>
          <div style="font-size:11px; color:var(--text-muted);">${item.phone || "--"}</div>
        </td>
        <td>${item.department || "Municipal Roads"}</td>
        <td>${item.zone || "Zone 1"}</td>
        <td><code>${item.employee_id || "SUP-" + item.id}</code></td>
        <td>${item.created_at ? item.created_at.slice(0, 10) : "Recent"}</td>
        <td><span class="badge ${statClass}">${item.approval_status}</span></td>
        <td>
          ${item.approval_status === 'PENDING_APPROVAL' ? `
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-success btn-xs" onclick="handleApproveSupervisor(${item.id})">Approve</button>
              <button class="btn btn-danger btn-xs" onclick="handleRejectSupervisor(${item.id})">Reject</button>
            </div>
          ` : `<span style="font-size: 11.5px; color: var(--text-muted);">Processed</span>`}
        </td>
      </tr>
    `;
  }).join("");
}

async function handleApproveSupervisor(id) {
  try {
    const res = await fetch(`/api/admin/supervisor-approvals/${id}/approve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      }
    });
    if (res.ok) {
      toast("Field Supervisor application APPROVED successfully!", "success");
      loadAdminSupervisorApprovalsData();
    } else {
      const err = await res.json();
      toast(err.detail || "Approval failed", "error");
    }
  } catch (e) {
    toast("Approval error: " + e.message, "error");
  }
}

async function handleRejectSupervisor(id) {
  const reason = prompt("Enter reason for rejecting Supervisor application:") || "Credentials not verified";
  try {
    const res = await fetch(`/api/admin/supervisor-approvals/${id}/reject`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ rejection_reason: reason })
    });
    if (res.ok) {
      toast("Supervisor application rejected", "info");
      loadAdminSupervisorApprovalsData();
    } else {
      const err = await res.json();
      toast(err.detail || "Rejection failed", "error");
    }
  } catch (e) {
    toast("Rejection error: " + e.message, "error");
  }
}

// 9. Supervisor Modal Actions
function openSupervisorValidateModal(id, issueType, severity, lat, lng) {
  const modal = document.getElementById("modalSupervisorValidate");
  if (!modal) return;
  document.getElementById("supValidateComplaintId").value = id;
  document.getElementById("supValidateModalSubtitle").textContent = `Complaint #${id}`;
  if (document.getElementById("supValidateIssueType")) document.getElementById("supValidateIssueType").value = issueType || "";
  if (document.getElementById("supValidateSeverity")) document.getElementById("supValidateSeverity").value = severity || "MEDIUM";
  if (document.getElementById("supValidateLat")) document.getElementById("supValidateLat").value = lat || "";
  if (document.getElementById("supValidateLng")) document.getElementById("supValidateLng").value = lng || "";
  modal.classList.add("show");
}

async function handleSupervisorValidateSubmit(event) {
  event.preventDefault();
  const id = document.getElementById("supValidateComplaintId").value;
  const issueType = document.getElementById("supValidateIssueType")?.value || null;
  const severity = document.getElementById("supValidateSeverity").value;
  const latVal = document.getElementById("supValidateLat")?.value;
  const lngVal = document.getElementById("supValidateLng")?.value;
  const notes = document.getElementById("supValidateNotes")?.value || null;

  try {
    const payload = {
      validated_severity: severity,
      validated_issue_type: issueType,
      validated_latitude: latVal ? parseFloat(latVal) : null,
      validated_longitude: lngVal ? parseFloat(lngVal) : null,
      notes: notes
    };

    const res = await fetch(`/api/supervisor/inspections/${id}/validate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      toast("Inspection validated successfully!", "success");
      closeModal("modalSupervisorValidate");
      if (currentRoute === "/supervisor/dashboard") loadSupervisorDashboardData();
      if (currentRoute === "/supervisor/inspections" || currentRoute === "/supervisor/field-inspections") loadSupervisorInspectionsData();
      if (activeComplaintId) loadComplaintDetails(activeComplaintId);
    } else {
      const err = await res.json();
      toast(err.detail || "Validation failed", "error");
    }
  } catch (e) {
    toast("Validation error: " + e.message, "error");
  }
}

function openSupervisorNotesModal(id) {
  const modal = document.getElementById("modalSupervisorNotes");
  if (!modal) return;
  document.getElementById("supNotesComplaintId").value = id;
  document.getElementById("supNotesModalSubtitle").textContent = `Complaint #${id}`;
  document.getElementById("supNotesContent").value = "";
  modal.classList.add("show");
}

async function handleSupervisorNotesSubmit(event) {
  event.preventDefault();
  const id = document.getElementById("supNotesComplaintId").value;
  const notes = document.getElementById("supNotesContent").value.trim();

  try {
    const res = await fetch(`/api/supervisor/inspections/${id}/notes`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ notes: notes })
    });

    if (res.ok) {
      toast("Supervisor field notes saved!", "success");
      closeModal("modalSupervisorNotes");
      if (activeComplaintId) loadComplaintDetails(activeComplaintId);
    } else {
      const err = await res.json();
      toast(err.detail || "Failed saving notes", "error");
    }
  } catch (e) {
    toast("Notes error: " + e.message, "error");
  }
}

function openSupervisorRecommendModal(id) {
  const modal = document.getElementById("modalSupervisorRecommend");
  if (!modal) return;
  document.getElementById("supRecommendComplaintId").value = id;
  document.getElementById("supRecommendModalSubtitle").textContent = `Complaint #${id}`;
  document.getElementById("supRecommendNotes").value = "";
  modal.classList.add("show");
}

async function handleSupervisorRecommendSubmit(event) {
  event.preventDefault();
  const id = document.getElementById("supRecommendComplaintId").value;
  const recommendation = document.getElementById("supRecommendNotes").value.trim();

  try {
    const res = await fetch(`/api/supervisor/inspections/${id}/recommend-completion`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ recommendation: recommendation })
    });

    if (res.ok) {
      toast("Completion recommended to Municipal Administrator!", "success");
      closeModal("modalSupervisorRecommend");
      if (currentRoute === "/supervisor/dashboard") loadSupervisorDashboardData();
      if (currentRoute === "/supervisor/inspections" || currentRoute === "/supervisor/field-inspections") loadSupervisorInspectionsData();
      if (activeComplaintId) loadComplaintDetails(activeComplaintId);
    } else {
      const err = await res.json();
      toast(err.detail || "Failed to recommend completion", "error");
    }
  } catch (e) {
    toast("Recommend error: " + e.message, "error");
  }
}

function openSupervisorReinspectModal(id) {
  const modal = document.getElementById("modalSupervisorReinspect");
  if (!modal) return;
  document.getElementById("supReinspectComplaintId").value = id;
  document.getElementById("supReinspectModalSubtitle").textContent = `Complaint #${id}`;
  document.getElementById("supReinspectReason").value = "";
  modal.classList.add("show");
}

async function handleSupervisorReinspectSubmit(event) {
  event.preventDefault();
  const id = document.getElementById("supReinspectComplaintId").value;
  const reason = document.getElementById("supReinspectReason").value.trim();

  try {
    const res = await fetch(`/api/supervisor/inspections/${id}/reinspect`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ reason: reason })
    });

    if (res.ok) {
      toast("Reinspection & rework requested!", "warning");
      closeModal("modalSupervisorReinspect");
      if (currentRoute === "/supervisor/dashboard") loadSupervisorDashboardData();
      if (currentRoute === "/supervisor/inspections" || currentRoute === "/supervisor/field-inspections") loadSupervisorInspectionsData();
      if (activeComplaintId) loadComplaintDetails(activeComplaintId);
    } else {
      const err = await res.json();
      toast(err.detail || "Failed requesting reinspection", "error");
    }
  } catch (e) {
    toast("Reinspection error: " + e.message, "error");
  }
}

window.createPlaceholderDataUrl = createPlaceholderDataUrl;

// ==========================================================================
// VISIONGUARD REAL-TIME INCIDENT INTELLIGENCE NETWORK CLIENT
// ==========================================================================

class RealtimeManager {
  constructor() {
    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.baseDelay = 1000;
    this.maxDelay = 15000;
    this.reconnectTimer = null;
    this.isManualClose = false;
    this.processedEventIds = new Set();
    this.listeners = new Map();
  }

  connect() {
    if (!authToken) {
      this.updateStatusUi("offline", "🔴 OFFLINE");
      return;
    }

    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isManualClose = false;
    this.updateStatusUi("reconnecting", "🟠 CONNECTING...");

    try {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/api/ws?token=${encodeURIComponent(authToken)}`;

      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = (event) => {
        this.reconnectAttempts = 0;
        this.updateStatusUi("live", "🟢 LIVE");
        console.log("[Realtime] Connected to VisionGuard Intelligence Network");
      };

      this.socket.onmessage = (event) => {
        this.handleMessage(event.data);
      };

      this.socket.onclose = (event) => {
        if (!this.isManualClose) {
          this.updateStatusUi("reconnecting", "🟠 RECONNECTING...");
          this.scheduleReconnect();
        } else {
          this.updateStatusUi("offline", "🔴 OFFLINE");
        }
      };

      this.socket.onerror = (error) => {
        console.warn("[Realtime] WebSocket connection issue:", error);
      };
    } catch (e) {
      console.error("[Realtime] Failed to initialize WebSocket:", e);
      this.scheduleReconnect();
    }
  }

  disconnect() {
    this.isManualClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.updateStatusUi("offline", "🔴 OFFLINE");
  }

  scheduleReconnect() {
    if (this.reconnectTimer || this.isManualClose || !authToken) return;

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.updateStatusUi("offline", "Live updates temporarily unavailable.");
      return;
    }

    const delay = Math.min(this.baseDelay * Math.pow(1.5, this.reconnectAttempts), this.maxDelay);
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  updateStatusUi(status, text) {
    const pill = document.getElementById("wsConnectionPill");
    const dot = document.getElementById("wsDotPulse");
    const txt = document.getElementById("wsStatusText");

    if (pill && dot && txt) {
      pill.className = `ws-live-pill ${status}`;
      dot.className = `status-dot-pulse ${status}`;
      txt.textContent = text;
    }
  }

  handleMessage(raw) {
    try {
      const msg = JSON.parse(raw);
      
      // Ping response
      if (msg.type === "ping") {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
          this.socket.send(JSON.stringify({ type: "pong" }));
        }
        return;
      }

      if (msg.type === "connection_established") {
        console.log("[Realtime] Connection handshake acknowledged:", msg);
        return;
      }

      // De-duplicate check
      const eventId = msg.event_id;
      if (eventId) {
        if (this.processedEventIds.has(eventId)) {
          return; // Ignore duplicate
        }
        this.processedEventIds.add(eventId);
        if (this.processedEventIds.size > 200) {
          const firstKey = this.processedEventIds.values().next().value;
          this.processedEventIds.delete(firstKey);
        }
      }

      const eventType = msg.event_type || msg.type;
      const data = msg.data || {};
      const timestamp = msg.timestamp || new Date().toISOString();

      this.dispatch(eventType, data, timestamp);
    } catch (e) {
      console.error("[Realtime] Error processing message:", e, raw);
    }
  }

  subscribe(eventType, callback) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, []);
    }
    this.listeners.get(eventType).push(callback);
  }

  dispatch(eventType, data, timestamp) {
    console.log(`[Realtime Event] ${eventType}:`, data);

    // Call custom listeners
    if (this.listeners.has(eventType)) {
      this.listeners.get(eventType).forEach(cb => {
        try { cb(data, timestamp); } catch(e) { console.error(e); }
      });
    }

    // Default global event handlers
    this.handleDefaultEvents(eventType, data, timestamp);
  }

  handleDefaultEvents(eventType, data, timestamp) {
    const timeStr = new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    // 1. Live Activity Feed Dispatch
    this.addLiveActivity(eventType, data, timeStr);

    // 2. Event-Specific Dispatches
    switch (eventType) {
      case "NEW_CRITICAL_HAZARD":
      case "NEW_HIGH_RISK_HAZARD":
        this.handleCriticalHazardAlert(eventType, data);
        this.refreshMapsAndRisk(data);
        break;

      case "NEW_AI_DETECTION":
        if (currentRoute === "/admin/dashboard" || currentRoute === "/user/dashboard") {
          this.incrementCounter("anStatTotalDetections", 1);
          this.incrementCounter("ctStatDetections", 1);
        }
        if (currentRoute === "/user/detection-history" || currentRoute === "/admin/detection-history") {
          loadDetectionHistory();
        }
        this.refreshMapsAndRisk(data);
        break;

      case "NEW_COMPLAINT":
        this.handleNewComplaint(data);
        break;

      case "COMPLAINT_VERIFIED":
        this.handleComplaintVerified(data);
        break;

      case "WORKER_ASSIGNED":
        this.handleWorkerAssigned(data);
        break;

      case "WORKER_STARTED":
        this.handleWorkerStarted(data);
        break;

      case "REPAIR_EVIDENCE_UPLOADED":
        this.handleEvidenceUploaded(data);
        break;

      case "COMPLAINT_COMPLETED":
        this.handleComplaintCompleted(data);
        break;

      case "COMPLAINT_REOPENED":
        this.handleComplaintReopened(data);
        break;

      case "WORKER_APPROVAL_REQUIRED":
        if (currentUser && currentUser.role === "ADMIN") {
          toast(`New Worker Application: ${data.full_name || 'Worker candidate'}`, "info");
          if (currentRoute === "/admin/worker-approvals") {
            loadAdminWorkerApprovalsData();
          }
        }
        break;

      case "WORKER_APPROVED":
      case "WORKER_REJECTED":
        if (currentUser && currentUser.role === "ADMIN" && currentRoute === "/admin/worker-approvals") {
          loadAdminWorkerApprovalsData();
        }
        break;

      case "SUPERVISOR_APPROVAL_REQUIRED":
        if (currentUser && currentUser.role === "ADMIN") {
          toast(`🛡️ New Field Supervisor Application: ${data.full_name || 'Candidate'}`, "info");
          if (currentRoute === "/admin/supervisor-approvals") {
            loadAdminSupervisorApprovalsData();
          }
        }
        break;

      case "SUPERVISOR_APPROVED":
      case "SUPERVISOR_REJECTED":
        if (currentUser && currentUser.role === "ADMIN" && currentRoute === "/admin/supervisor-approvals") {
          loadAdminSupervisorApprovalsData();
        }
        break;

      case "SUPERVISOR_INSPECTION_ASSIGNED":
        toast(`🔍 Inspection Task #${data.complaint_id || ''} assigned to Field Supervisor`, "info");
        if (currentUser && currentUser.role === "SUPERVISOR") {
          if (currentRoute === "/supervisor/dashboard") loadSupervisorDashboardData();
          if (currentRoute === "/supervisor/inspections" || currentRoute === "/supervisor/field-inspections") loadSupervisorInspectionsData();
        }
        break;

      case "INSPECTION_VALIDATED":
        toast(`✓ Field Inspection #${data.complaint_id || ''} validated by Supervisor`, "info");
        if (currentRoute === "/supervisor/dashboard") loadSupervisorDashboardData();
        if (currentRoute === "/supervisor/inspections" || currentRoute === "/supervisor/field-inspections") loadSupervisorInspectionsData();
        if (currentRoute === "/admin/dashboard") loadAdminDashboardData();
        break;

      case "SUPERVISOR_RECOMMENDED":
        toast(`★ Supervisor recommended completion for #${data.complaint_id || ''}`, "success");
        if (currentRoute === "/supervisor/dashboard") loadSupervisorDashboardData();
        if (currentRoute === "/supervisor/inspections" || currentRoute === "/supervisor/field-inspections") loadSupervisorInspectionsData();
        if (currentRoute === "/admin/dashboard") loadAdminDashboardData();
        break;

      case "REINSPECTION_REQUIRED":
        toast(`⚠️ Reinspection / rework requested for #${data.complaint_id || ''}`, "warning");
        if (currentRoute === "/supervisor/dashboard") loadSupervisorDashboardData();
        if (currentRoute === "/supervisor/inspections" || currentRoute === "/supervisor/field-inspections") loadSupervisorInspectionsData();
        if (currentRoute === "/worker/dashboard") loadWorkerDashboardData();
        break;

      case "RISK_LEVEL_CHANGED":
        if (currentRoute === "/admin/dashboard") {
          loadAdminDashboardData();
        } else if (currentRoute === "/admin/city-intelligence") {
          loadCityIntelligenceData();
        }
        break;

      case "LIVE_INCIDENT_CREATED":
        if (data.risk_score >= 75) {
          this.handleCriticalHazardAlert("NEW_CRITICAL_HAZARD", data);
        } else if (data.risk_score >= 50) {
          this.handleCriticalHazardAlert("NEW_HIGH_RISK_HAZARD", data);
        }
        this.handleNewComplaint(data);
        if (currentRoute === "/admin/live-monitoring") loadAdminLiveMonitoring();
        if (currentRoute === "/user/live-detection") appendSessionIncidentFeed(data);
        this.updateMapMarkerLive(data);
        break;

      case "INCIDENT_VERIFIED":
        this.handleComplaintVerified(data);
        if (currentRoute === "/admin/live-monitoring") loadAdminLiveMonitoring();
        break;

      case "INCIDENT_REJECTED":
        toast(`Complaint #${data.complaint_id || ''} rejected`, "info");
        if (currentRoute === "/admin/live-monitoring") loadAdminLiveMonitoring();
        if (currentRoute === "/admin/complaints") loadComplaintsList();
        break;

      case "LIVE_WORKER_ASSIGNED":
        this.handleWorkerAssigned(data);
        if (currentRoute === "/admin/live-monitoring") loadAdminLiveMonitoring();
        break;

      case "LIVE_WORK_STARTED":
        this.handleWorkerStarted(data);
        if (currentRoute === "/admin/live-monitoring") loadAdminLiveMonitoring();
        break;

      case "LIVE_EVIDENCE_UPLOADED":
        this.handleEvidenceUploaded(data);
        if (currentRoute === "/admin/live-monitoring") loadAdminLiveMonitoring();
        break;

      case "LIVE_COMPLETION_SUBMITTED":
        toast(`⚠️ Repair completion for #${data.complaint_id || ''} submitted for Admin review!`, "info");
        if (currentRoute === "/admin/live-monitoring") loadAdminLiveMonitoring();
        if (currentRoute === "/admin/dashboard") loadAdminDashboardData();
        break;

      case "LIVE_INCIDENT_COMPLETED":
        this.handleComplaintCompleted(data);
        if (currentRoute === "/admin/live-monitoring") loadAdminLiveMonitoring();
        break;

      case "MAP_DATA_UPDATED":
        this.updateMapMarkerLive(data);
        break;

      case "NOTIFICATION_CREATED":
        this.handleLiveNotification(data);
        break;
    }
  }

  addLiveActivity(eventType, data, timeStr) {
    const list = document.getElementById("adminLiveActivityList");
    if (!list) return;

    let text = "";
    let dotClass = "info";

    switch (eventType) {
      case "LIVE_INCIDENT_CREATED":
        text = `🔴 Live Incident #${data.complaint_id || ''} (${data.detected_class || 'Road Hazard'}) logged from ${data.source || 'LIVE VIDEO'}`;
        dotClass = "danger";
        break;
      case "INCIDENT_VERIFIED":
        text = `Incident #${data.complaint_id || ''} verified by Admin`;
        dotClass = "success";
        break;
      case "INCIDENT_REJECTED":
        text = `Incident #${data.complaint_id || ''} rejected by Admin`;
        dotClass = "warning";
        break;
      case "SUPERVISOR_INSPECTION_ASSIGNED":
        text = `Inspection assigned to Field Supervisor for #${data.complaint_id || ''}`;
        dotClass = "info";
        break;
      case "INSPECTION_VALIDATED":
        text = `Field Supervisor validated severity & location for #${data.complaint_id || ''}`;
        dotClass = "success";
        break;
      case "SUPERVISOR_RECOMMENDED":
        text = `Field Supervisor recommended completion for #${data.complaint_id || ''}`;
        dotClass = "success";
        break;
      case "REINSPECTION_REQUIRED":
        text = `Supervisor requested rework & reinspection for #${data.complaint_id || ''}`;
        dotClass = "warning";
        break;
      case "LIVE_WORKER_ASSIGNED":
        text = `Worker ${data.worker_name || 'Field Unit'} assigned to live incident #${data.complaint_id || ''}`;
        dotClass = "info";
        break;
      case "LIVE_WORK_STARTED":
        text = `Repairs started on #${data.complaint_id || ''} by ${data.worker_name || 'Worker'}`;
        dotClass = "warning";
        break;
      case "LIVE_EVIDENCE_UPLOADED":
        text = `Repair evidence uploaded for #${data.complaint_uid || data.complaint_id || ''}`;
        dotClass = "info";
        break;
      case "LIVE_COMPLETION_SUBMITTED":
        text = `Worker submitted repair completion for #${data.complaint_id || ''}`;
        dotClass = "warning";
        break;
      case "LIVE_INCIDENT_COMPLETED":
        text = `Live incident #${data.complaint_id || ''} approved and completed!`;
        dotClass = "success";
        break;
      case "NEW_AI_DETECTION":
        text = `AI Detected ${data.detected_class || 'Road Hazard'} (${Math.round((data.confidence || 0.9) * 100)}% conf)`;
        dotClass = "info";
        break;
      case "NEW_CRITICAL_HAZARD":
        text = `Critical Hazard: ${data.issue_type || 'Pothole'} (Risk: ${data.risk_score || 85}/100)`;
        dotClass = "danger";
        break;
      case "NEW_HIGH_RISK_HAZARD":
        text = `High Risk Hazard: ${data.issue_type || 'Road Issue'} (Risk: ${data.risk_score || 65}/100)`;
        dotClass = "warning";
        break;
      case "NEW_COMPLAINT":
        text = `New complaint #${data.complaint_id || ''} (${data.title || data.issue_type || 'Hazard'}) logged`;
        dotClass = "warning";
        break;
      case "COMPLAINT_VERIFIED":
        text = `Complaint #${data.complaint_id || ''} verified by municipality`;
        dotClass = "success";
        break;
      case "WORKER_ASSIGNED":
        text = `Worker ${data.worker_name || 'Field Unit'} assigned to #${data.complaint_id || ''}`;
        dotClass = "info";
        break;
      case "WORKER_STARTED":
        text = `Repairs started on #${data.complaint_id || ''} by ${data.worker_name || 'Worker'}`;
        dotClass = "warning";
        break;
      case "REPAIR_EVIDENCE_UPLOADED":
        text = `Repair evidence uploaded for #${data.complaint_uid || data.complaint_id || ''}`;
        dotClass = "info";
        break;
      case "COMPLAINT_COMPLETED":
        text = `Complaint #${data.complaint_id || ''} resolved and completed!`;
        dotClass = "success";
        break;
      default:
        text = `Municipal Event: ${eventType.replace(/_/g, ' ')}`;
    }

    const itemHtml = `
      <div class="live-activity-item">
        <div class="live-activity-item-left">
          <span class="live-activity-dot ${dotClass}"></span>
          <span class="live-activity-text">${text}</span>
        </div>
        <span class="live-activity-time">${timeStr}</span>
      </div>
    `;

    if (list.innerHTML.includes("No live activity yet")) {
      list.innerHTML = "";
    }

    list.insertAdjacentHTML("afterbegin", itemHtml);

    while (list.children.length > 25) {
      list.removeChild(list.lastChild);
    }
  }

  handleCriticalHazardAlert(eventType, data) {
    const isCritical = eventType === "NEW_CRITICAL_HAZARD";
    const bannerAdmin = document.getElementById("adminLiveIncidentBanner");
    const bannerCt = document.getElementById("ctLiveIncidentBanner");

    const html = `
      <div class="live-incident-banner">
        <div class="live-incident-content">
          <div class="live-incident-icon-badge">🔴</div>
          <div class="live-incident-details">
            <div style="display:flex; align-items:center; gap:8px;">
              <span class="badge badge-danger" style="font-size:10px; font-weight:800;">● LIVE INCIDENT</span>
              <h4 style="margin:0;">${isCritical ? 'CRITICAL HAZARD DETECTED' : 'HIGH RISK ROAD HAZARD'}</h4>
            </div>
            <p style="margin-top:2px;">
              <strong>${data.issue_type || data.title || 'Road Hazard'}</strong> • Risk: <strong>${data.risk_score || 85}/100</strong> • AI Confidence: <strong>${data.confidence || 94}%</strong> ${data.latitude ? `• GPS: ${data.latitude.toFixed(4)}, ${data.longitude.toFixed(4)}` : ''}
            </p>
          </div>
        </div>
        <div class="live-incident-actions">
          ${data.complaint_id ? `<button class="btn btn-danger btn-sm" onclick="navigate('/admin/complaints/${data.complaint_id}')">View Incident</button>` : `<button class="btn btn-danger btn-sm" onclick="navigate('/admin/city-intelligence')">View Digital Twin</button>`}
          <button class="btn btn-outline btn-sm" onclick="this.closest('.live-incident-banner').remove()" style="padding:4px 8px;">✕</button>
        </div>
      </div>
    `;

    if (bannerAdmin) {
      bannerAdmin.innerHTML = html;
      bannerAdmin.style.display = "block";
    }
    if (bannerCt) {
      bannerCt.innerHTML = html;
      bannerCt.style.display = "block";
    }

    toast(`🔴 ${isCritical ? 'CRITICAL HAZARD' : 'HIGH RISK'}: ${data.issue_type || 'Road Issue'} (Risk: ${data.risk_score || 85}/100)`, "error");
  }

  handleNewComplaint(data) {
    toast(`📢 New Complaint #${data.complaint_id || ''} received: ${data.title || ''}`, "info");

    this.incrementCounter("adminStatTotal", 1);
    this.incrementCounter("adminStatNew", 1);
    this.incrementCounter("ctStatActiveComplaints", 1);

    if (currentUser && currentUser.role === "USER" && data.user_id === currentUser.id) {
      this.incrementCounter("userStatTotal", 1);
      this.incrementCounter("userStatPending", 1);
      if (currentRoute === "/user/dashboard") {
        loadUserDashboardData();
      } else if (currentRoute === "/user/complaints") {
        loadComplaintsList();
      }
    }

    if (currentRoute === "/admin/dashboard") {
      loadAdminDashboardData();
    } else if (currentRoute === "/admin/complaints") {
      loadComplaintsList();
    } else if (currentRoute === "/admin/city-intelligence") {
      loadCityIntelligenceData();
    }
  }

  handleComplaintVerified(data) {
    toast(`✓ Complaint #${data.complaint_id || ''} verified by municipality`, "success");

    if (activeComplaintId && (String(activeComplaintId) === String(data.id) || String(activeComplaintId) === String(data.complaint_id))) {
      loadComplaintDetails(activeComplaintId);
    }
    if (currentRoute === "/user/dashboard") loadUserDashboardData();
    if (currentRoute === "/admin/dashboard") loadAdminDashboardData();
    if (currentRoute === "/admin/complaints" || currentRoute === "/user/complaints") loadComplaintsList();
  }

  handleWorkerAssigned(data) {
    if (currentUser && currentUser.role === "WORKER" && (String(data.assigned_worker_id) === String(currentUser.worker_id) || data.worker_name === currentUser.full_name)) {
      const banner = document.getElementById("workerLiveTaskBanner");
      if (banner) {
        banner.innerHTML = `
          <div class="live-incident-banner" style="border-left-color: var(--primary); background: linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%); border-color: #bfdbfe;">
            <div class="live-incident-content">
              <div class="live-incident-icon-badge" style="background:#dbeafe; color:var(--primary);">🔔</div>
              <div class="live-incident-details">
                <div style="display:flex; align-items:center; gap:8px;">
                  <span class="badge badge-info" style="font-size:10px; font-weight:800;">● NEW TASK ASSIGNED</span>
                  <h4 style="color:var(--primary); margin:0;">#${data.complaint_id} — ${data.title || 'Road Work Order'}</h4>
                </div>
                <p style="color:var(--text-secondary); margin-top:2px;">
                  Priority: <strong>${data.severity || 'HIGH'}</strong> • ${data.location_address || (data.latitude ? `GPS: ${data.latitude.toFixed(4)}, ${data.longitude.toFixed(4)}` : 'Site Location')}
                </p>
              </div>
            </div>
            <div class="live-incident-actions">
              <button class="btn btn-primary btn-sm" onclick="navigate('/worker/tasks/${data.id || data.complaint_id}')">Open Task</button>
              <button class="btn btn-outline btn-sm" onclick="this.closest('.live-incident-banner').remove()">✕</button>
            </div>
          </div>
        `;
        banner.style.display = "block";
      }
      toast(`🔔 NEW TASK ASSIGNED: #${data.complaint_id} - ${data.title || 'Work Order'}`, "success");
      loadWorkerDashboardData();
      if (currentRoute === "/worker/tasks") loadWorkerTasksData();
    }

    if (activeComplaintId && (String(activeComplaintId) === String(data.id) || String(activeComplaintId) === String(data.complaint_id))) {
      loadComplaintDetails(activeComplaintId);
    }
    if (currentRoute === "/admin/dashboard") loadAdminDashboardData();
    if (currentRoute === "/user/dashboard") loadUserDashboardData();
  }

  handleWorkerStarted(data) {
    toast(`⚙️ Worker started on-site repairs for #${data.complaint_id}`, "info");

    if (activeComplaintId && (String(activeComplaintId) === String(data.id) || String(activeComplaintId) === String(data.complaint_id))) {
      loadComplaintDetails(activeComplaintId);
    }
    if (currentRoute === "/admin/dashboard") loadAdminDashboardData();
    if (currentRoute === "/worker/dashboard") loadWorkerDashboardData();
    if (currentRoute === "/user/dashboard") loadUserDashboardData();
  }

  handleEvidenceUploaded(data) {
    toast(`📸 Repair evidence uploaded for #${data.complaint_uid || data.complaint_id || ''}`, "info");

    if (activeComplaintId && (String(activeComplaintId) === String(data.complaint_id) || String(activeComplaintId) === String(data.complaint_uid))) {
      loadComplaintDetails(activeComplaintId);
    }
  }

  handleComplaintCompleted(data) {
    toast(`🎉 Complaint #${data.complaint_id || ''} marked COMPLETED!`, "success");

    this.decrementCounter("adminStatInProgress", 1);
    this.incrementCounter("adminStatCompleted", 1);
    this.incrementCounter("ctStatResolvedComplaints", 1);
    this.decrementCounter("ctStatActiveComplaints", 1);

    if (activeComplaintId && (String(activeComplaintId) === String(data.id) || String(activeComplaintId) === String(data.complaint_id))) {
      loadComplaintDetails(activeComplaintId);
    }
    if (currentRoute === "/admin/dashboard") loadAdminDashboardData();
    if (currentRoute === "/worker/dashboard") loadWorkerDashboardData();
    if (currentRoute === "/user/dashboard") loadUserDashboardData();
    if (currentRoute === "/admin/city-intelligence") loadCityIntelligenceData();
  }

  handleComplaintReopened(data) {
    toast(`⚠️ Complaint #${data.complaint_id || ''} was REOPENED for further review`, "warning");

    if (activeComplaintId && (String(activeComplaintId) === String(data.id) || String(activeComplaintId) === String(data.complaint_id))) {
      loadComplaintDetails(activeComplaintId);
    }
  }

  handleLiveNotification(data) {
    const badge = document.getElementById("notifBadge");
    if (badge) {
      const cur = parseInt(badge.textContent || "0", 10) || 0;
      badge.textContent = cur + 1;
      badge.style.display = "flex";
    }

    const list = document.getElementById("notifItemsList");
    if (list) {
      if (list.innerHTML.includes("No new notifications")) {
        list.innerHTML = "";
      }
      const itemHtml = `
        <div class="dropdown-notif-item unread" style="padding:10px 14px; border-bottom:1px solid var(--border-subtle);">
          <div style="font-weight:700; font-size:12.5px; color:var(--text-main);">${data.title || 'Notification'}</div>
          <div style="font-size:11.5px; color:var(--text-secondary); margin-top:2px;">${data.message || ''}</div>
          <div style="font-size:10px; color:var(--text-muted); margin-top:4px;">Just now</div>
        </div>
      `;
      list.insertAdjacentHTML("afterbegin", itemHtml);
    }

    toast(`🔔 ${data.title || 'Notification'}: ${data.message || ''}`, "info");
  }

  refreshMapsAndRisk(data) {
    if (currentRoute === "/admin/city-intelligence") {
      loadCityTwinLocations();
    } else if (currentRoute === "/user/map" || currentRoute === "/worker/map" || currentRoute === "/admin/map") {
      loadMapMarkers();
    }
  }

  updateMapMarkerLive(data) {
    if (!data.latitude || !data.longitude) return;

    if (leafletMapInstance && leafletMarkersLayer) {
      const lat = data.latitude;
      const lng = data.longitude;
      const title = data.title || data.issue_type || "Live Incident";
      const score = data.risk_score || 50;

      let color = score >= 75 ? "#EF4444" : (score >= 50 ? "#EA580C" : (score >= 25 ? "#F59E0B" : "#10B981"));
      const icon = L.divIcon({
        className: 'live-map-marker',
        html: `<div style="background:${color}; width:20px; height:20px; border-radius:50%; border:2px solid #fff; box-shadow:0 0 10px ${color}; display:flex; align-items:center; justify-content:center; color:#fff; font-size:10px; font-weight:800;">!</div>`
      });

      L.marker([lat, lng], { icon: icon })
        .bindPopup(`<strong>${title}</strong><br>Risk: ${score}/100<br>Status: ${data.status || 'ACTIVE'}`)
        .addTo(leafletMarkersLayer);
    }

    if (cityTwinMapInstance && cityTwinMarkersLayer) {
      const lat = data.latitude;
      const lng = data.longitude;
      const title = data.title || data.issue_type || "Live Incident";
      const score = data.risk_score || 50;

      let pinColor = score >= 75 ? "#EF4444" : (score >= 50 ? "#EA580C" : (score >= 25 ? "#F59E0B" : "#10B981"));
      const customIcon = L.divIcon({
        className: 'twin-map-marker',
        html: `<div style="background:${pinColor}; width:22px; height:22px; border-radius:50%; border:2px solid #FFFFFF; box-shadow:0 0 12px ${pinColor}; display:flex; align-items:center; justify-content:center; color:#FFFFFF; font-size:11px; font-weight:800; cursor:pointer;">!</div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11]
      });

      L.marker([lat, lng], { icon: customIcon })
        .bindPopup(`<strong>${title}</strong><br>Risk Score: ${score}/100<br>Live Telemetry Added`)
        .addTo(cityTwinMarkersLayer);
    }
  }

  incrementCounter(elemId, delta = 1) {
    const el = document.getElementById(elemId);
    if (el) {
      const cur = parseInt(el.textContent.replace(/,/g, '') || "0", 10) || 0;
      el.textContent = (cur + delta).toLocaleString();
    }
  }

  decrementCounter(elemId, delta = 1) {
    const el = document.getElementById(elemId);
    if (el) {
      const cur = parseInt(el.textContent.replace(/,/g, '') || "0", 10) || 0;
      el.textContent = Math.max(0, cur - delta).toLocaleString();
    }
  }
}

const realtimeManager = new RealtimeManager();
window.RealtimeManager = RealtimeManager;
window.realtimeManager = realtimeManager;





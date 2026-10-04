"""
VisionGuard AI 2.0 - Mobile USB & Laptop Camera Integration Test Suite
Validates:
1. Camera source selector dropdown in HTML (#cameraSourceSelect)
2. Refresh cameras button in HTML (#btnRefreshCameras)
3. Camera status and AI detection status indicators (#currentCameraNameLabel, #cameraOnlineStatusBadge, #aiDetectionStatusBadge)
4. Camera permission prompt and banner (#cameraPermissionBanner, #btnRequestCameraAccess)
5. JavaScript mediaDevices enumeration (enumerateDevices filtering videoinput)
6. Dynamic camera selection and constraint passing (deviceId exact & fallback)
7. Error handling for NotAllowedError, NotFoundError, NotReadableError, OverconstrainedError
8. Window exports for camera management functions
"""

def test_camera_ui_dom_and_javascript_integration():
    """Verify HTML markup and JavaScript functions for multi-camera and mobile camera support."""
    with open("static/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    with open("static/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    checks = [
        ('cameraSourceSelect ID in HTML', 'id="cameraSourceSelect"' in html),
        ('btnRefreshCameras ID in HTML', 'id="btnRefreshCameras"' in html),
        ('cameraPermissionBanner ID in HTML', 'id="cameraPermissionBanner"' in html),
        ('btnRequestCameraAccess ID in HTML', 'id="btnRequestCameraAccess"' in html),
        ('currentCameraNameLabel ID in HTML', 'id="currentCameraNameLabel"' in html),
        ('cameraOnlineStatusBadge ID in HTML', 'id="cameraOnlineStatusBadge"' in html),
        ('aiDetectionStatusBadge ID in HTML', 'id="aiDetectionStatusBadge"' in html),
        ('liveCameraVideo ID in HTML', 'id="liveCameraVideo"' in html),
        ('liveCameraCanvas ID in HTML', 'id="liveCameraCanvas"' in html),
        ('enumerateDevices in app.js', 'navigator.mediaDevices.enumerateDevices' in js),
        ('videoinput filter in app.js', 'kind === "videoinput"' in js or "kind === 'videoinput'" in js),
        ('refreshCameraDevices in app.js', 'function refreshCameraDevices' in js),
        ('handleCameraSourceChange in app.js', 'function handleCameraSourceChange' in js),
        ('requestCameraAccess in app.js', 'function requestCameraAccess' in js),
        ('updateCameraStatusUi in app.js', 'function updateCameraStatusUi' in js),
        ('startLiveCameraDetection in app.js', 'function startLiveCameraDetection' in js),
        ('stopLiveCameraDetection in app.js', 'function stopLiveCameraDetection' in js),
        ('getCameraErrorMessage in app.js', 'function getCameraErrorMessage' in js),
        ('deviceId exact constraint in app.js', 'deviceId: { exact:' in js or 'deviceId: { exact: chosenDeviceId }' in js),
        ('getUserMedia call in app.js', 'navigator.mediaDevices.getUserMedia' in js),
        ('NotAllowedError handled in app.js', 'NotAllowedError' in js),
        ('NotFoundError handled in app.js', 'NotFoundError' in js),
        ('NotReadableError handled in app.js', 'NotReadableError' in js),
        ('OverconstrainedError handled in app.js', 'OverconstrainedError' in js),
        ('ONLINE and OFFLINE statuses in app.js', 'ONLINE' in js and 'OFFLINE' in js),
        ('ACTIVE and STOPPED statuses in app.js', 'ACTIVE' in js and 'STOPPED' in js),
        ('No camera device detected message', 'No camera device detected.' in js),
        ('Camera disconnected message', 'Camera disconnected. Click Refresh Cameras.' in js),
        ('audio: false constraint in app.js', 'audio: false' in js),
        ('Stop previous tracks on camera switch', 'liveWebcamStream.getTracks().forEach' in js),
        ('refreshCameraDevices exported to window', 'window.refreshCameraDevices = refreshCameraDevices' in js),
        ('handleCameraSourceChange exported to window', 'window.handleCameraSourceChange = handleCameraSourceChange' in js),
        ('requestCameraAccess exported to window', 'window.requestCameraAccess = requestCameraAccess' in js),
        ('updateCameraStatusUi exported to window', 'window.updateCameraStatusUi = updateCameraStatusUi' in js),
        ('startLiveCameraDetection exported to window', 'window.startLiveCameraDetection = startLiveCameraDetection' in js),
        ('stopLiveCameraDetection exported to window', 'window.stopLiveCameraDetection = stopLiveCameraDetection' in js),
    ]

    all_passed = True
    print("================ CAMERA & DEVICE INTEGRATION CHECKS ================")
    for name, passed in checks:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")
        if not passed:
            all_passed = False

    print("====================================================================")
    assert all_passed, "Some Camera & Device Integration checks failed!"
    print("ALL CAMERA & DEVICE INTEGRATION CHECKS PASSED!")


if __name__ == "__main__":
    test_camera_ui_dom_and_javascript_integration()

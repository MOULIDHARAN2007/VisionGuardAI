"""
Test suite for VISIONGUARD AI Video Intelligence Studio - Remove / Clear Video Feature.
Verifies all 6 test cases and UI / State requirements using built-in standard libraries.
"""

import os
import re
import pytest

def test_html_structure_remove_video_button():
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    assert os.path.exists(html_path), "index.html must exist"
    
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Verify btnRemoveVideo button exists
    assert 'id="btnRemoveVideo"' in content, "btnRemoveVideo id must exist in index.html"
    assert 'btn-danger' in content, "btn-danger class must be present"
    assert 'onclick="confirmRemoveVideo()"' in content, "btnRemoveVideo must have onclick='confirmRemoveVideo()'"
    assert 'Remove Video' in content, "Remove Video text must be present"
    
    # 2. Verify button container layout has both buttons
    video_btn_pattern = re.search(r'id="btnProcessVideo"[\s\S]*?id="btnRemoveVideo"', content)
    assert video_btn_pattern is not None, "btnProcessVideo and btnRemoveVideo should be structured together"

def test_html_structure_confirm_modal():
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify modalConfirmRemoveVideo backdrop and dialog
    assert 'id="modalConfirmRemoveVideo"' in content, "modalConfirmRemoveVideo must exist"
    assert 'modal-backdrop-overlay' in content, "modal-backdrop-overlay class must exist"
    
    # Verify exact confirmation texts
    assert "Remove this video?" in content, "Modal title must include 'Remove this video?'"
    assert "This will clear the currently loaded video and its unsaved detection results." in content, "Modal explanation must be present"
    
    # Verify Cancel button
    assert 'id="btnCancelRemoveVideo"' in content, "btnCancelRemoveVideo must exist"
    assert "closeModal('modalConfirmRemoveVideo')" in content, "Cancel button must close modal"
    
    # Verify Confirm button
    assert 'id="btnConfirmRemoveVideo"' in content, "btnConfirmRemoveVideo must exist"
    assert 'onclick="executeRemoveVideo()"' in content, "Confirm button must call executeRemoveVideo()"

def test_js_video_intelligence_functions():
    js_path = os.path.join(os.path.dirname(__file__), "static", "app.js")
    assert os.path.exists(js_path), "app.js must exist"
    
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Verify confirmRemoveVideo function definition
    assert "function confirmRemoveVideo()" in content, "confirmRemoveVideo must be defined"
    
    # 2. Verify executeRemoveVideo function definition
    assert "function executeRemoveVideo()" in content, "executeRemoveVideo must be defined"
    
    # 3. Verify clearVideoIntelligenceStudio function definition
    assert "function clearVideoIntelligenceStudio()" in content, "clearVideoIntelligenceStudio must be defined"
    
    # 4. Check that clearVideoIntelligenceStudio resets all key UI elements and state variables
    assert "selectedVideoFile = null" in content, "selectedVideoFile must be set to null"
    assert "lastVideoAnalysis = null" in content, "lastVideoAnalysis must be set to null"
    assert 'video.removeAttribute("src")' in content or "video.src =" in content, "video source must be cleared"
    assert "fileInput.value = \"\"" in content, "fileInput value must be cleared"
    assert 'countBadge.textContent = "0 Hazards"' in content, "Hazards count badge must be reset"
    assert 'btnRemove.style.display = "none"' in content, "btnRemove must be hidden on clear"
    assert 'playerContainer.style.display = "none"' in content, "playerContainer must be hidden on clear"
    assert 'dropzone.style.display = "block"' in content, "dropzone must be restored on clear"
    
    # 5. Check handleVideoFileSelect shows the remove button
    assert 'btnRemove.style.display = "inline-flex"' in content or 'btnRemove.style.display = "block"' in content, "handleVideoFileSelect must show Remove Video button"

    # 6. Check window bindings
    assert "window.confirmRemoveVideo = confirmRemoveVideo;" in content, "window.confirmRemoveVideo must be bound"
    assert "window.executeRemoveVideo = executeRemoveVideo;" in content, "window.executeRemoveVideo must be bound"
    assert "window.clearVideoIntelligenceStudio = clearVideoIntelligenceStudio;" in content, "window.clearVideoIntelligenceStudio must be bound"

def test_database_records_not_deleted():
    js_path = os.path.join(os.path.dirname(__file__), "static", "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract clearVideoIntelligenceStudio function body
    match = re.search(r"function clearVideoIntelligenceStudio\(\)\s*\{([\s\S]*?)\n\}", content)
    assert match is not None, "clearVideoIntelligenceStudio function body should be extractable"
    func_body = match.group(1)
    
    # Ensure no DELETE requests or DB wipe operations are done in clearVideoIntelligenceStudio
    assert "DELETE" not in func_body, "clearVideoIntelligenceStudio must not make DELETE API calls"
    assert "/api/complaints/delete" not in func_body, "clearVideoIntelligenceStudio must not delete complaints"
    assert "/api/detections/delete" not in func_body, "clearVideoIntelligenceStudio must not delete detections"

if __name__ == "__main__":
    pytest.main(["-v", __file__])

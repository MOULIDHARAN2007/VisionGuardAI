from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def create_sample_images():
    complaints_dir = Path("uploads/complaints")
    evidence_dir = Path("uploads/evidence")
    static_dir = Path("static")
    complaints_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    static_dir.mkdir(parents=True, exist_ok=True)

    # 1. Pothole Demo Image
    pothole_img = Image.new("RGB", (640, 480), color=(80, 85, 90))
    draw = ImageDraw.Draw(pothole_img)
    # Draw asphalt road texture and lines
    draw.rectangle([0, 0, 640, 480], fill=(70, 75, 80))
    # Lane line
    draw.line([320, 0, 320, 480], fill=(230, 200, 50), width=8)
    # Pothole cavity
    draw.ellipse([200, 180, 440, 320], fill=(30, 32, 35), outline=(50, 52, 55), width=4)
    draw.ellipse([230, 200, 410, 300], fill=(15, 18, 20))
    # Cracks radiating out
    draw.line([200, 250, 140, 220], fill=(20, 20, 20), width=2)
    draw.line([440, 250, 500, 280], fill=(20, 20, 20), width=2)
    draw.line([300, 180, 290, 120], fill=(20, 20, 20), width=2)
    draw.line([350, 320, 380, 390], fill=(20, 20, 20), width=2)
    # Water/depth shading
    draw.ellipse([270, 230, 370, 280], fill=(10, 12, 15))
    
    # Text overlay
    draw.rectangle([10, 10, 280, 40], fill=(0, 0, 0, 180))
    draw.text((18, 16), "VISIONGUARD AI - POTHOLE TELEMETRY", fill=(255, 255, 255))
    
    pothole_path = complaints_dir / "sample_pothole_demo.jpg"
    pothole_img.save(pothole_path, "JPEG", quality=90)
    print("Created:", pothole_path)

    # 2. Completed Repair Demo Image
    repair_img = Image.new("RGB", (640, 480), color=(80, 85, 90))
    draw_rep = ImageDraw.Draw(repair_img)
    draw_rep.rectangle([0, 0, 640, 480], fill=(70, 75, 80))
    draw_rep.line([320, 0, 320, 480], fill=(230, 200, 50), width=8)
    # Fresh asphalt patch (darker, smooth rectangle with sealed edges)
    draw_rep.rectangle([180, 160, 460, 340], fill=(35, 38, 42), outline=(25, 28, 30), width=3)
    # Fresh seal lines
    draw_rep.line([180, 160, 460, 160], fill=(20, 20, 20), width=3)
    draw_rep.line([180, 340, 460, 340], fill=(20, 20, 20), width=3)
    draw_rep.line([180, 160, 180, 340], fill=(20, 20, 20), width=3)
    draw_rep.line([460, 160, 460, 340], fill=(20, 20, 20), width=3)
    
    # Text overlay
    draw_rep.rectangle([10, 10, 310, 40], fill=(0, 100, 0, 180))
    draw_rep.text((18, 16), "MUNICIPAL REPAIR COMPLETED & SEALED", fill=(255, 255, 255))
    
    repair_path = evidence_dir / "sample_repair_demo.jpg"
    repair_img.save(repair_path, "JPEG", quality=90)
    print("Created:", repair_path)

    # 3. High quality placeholder image
    placeholder_img = Image.new("RGB", (400, 300), color=(241, 245, 249))
    draw_ph = ImageDraw.Draw(placeholder_img)
    draw_ph.rectangle([4, 4, 396, 296], fill=(248, 250, 252), outline=(203, 213, 225), width=2)
    draw_ph.rectangle([160, 100, 240, 160], fill=(226, 232, 240), outline=(148, 163, 184), width=2)
    draw_ph.ellipse([185, 120, 215, 150], fill=(148, 163, 184))
    draw_ph.text((130, 185), "VisionGuard AI Evidence", fill=(100, 116, 139))
    draw_ph.text((140, 205), "No Image Available", fill=(148, 163, 184))
    
    ph_path = static_dir / "placeholder.jpg"
    placeholder_img.save(ph_path, "JPEG", quality=90)
    print("Created:", ph_path)

if __name__ == "__main__":
    create_sample_images()

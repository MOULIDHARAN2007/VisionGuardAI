import sqlite3

conn = sqlite3.connect('visionguard.db')
c = conn.cursor()
c.execute("UPDATE complaints SET image_path='/uploads/complaints/sample_pothole_demo.jpg' WHERE complaint_id='VG-CMP-202609-001-DEMO'")
conn.commit()
print("Updated demo complaint image path in DB!")

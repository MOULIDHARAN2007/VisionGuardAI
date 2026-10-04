"""
VisionGuard AI 2.0 - Database Complaint Reset Script
Safely cleans all existing complaint, assignment, evidence, detection, and notification transactional records.
Preserves Users, Workers, Supervisors, Admins, System Configuration, and AI Models.
"""

import os
import shutil
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "visionguard.db"
BACKUP_PATH = BASE_DIR / "visionguard_before_complaint_reset_backup.db"

def reset_database():
    # 1. Ensure backup exists
    if not BACKUP_PATH.exists():
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"[Backup] Created backup at {BACKUP_PATH}")
    else:
        print(f"[Backup] Verified existing backup at {BACKUP_PATH} ({BACKUP_PATH.stat().st_size} bytes)")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 2. Count before deletion
    counts_before = {}
    for table in ["complaints", "assignments", "evidence", "notifications", "detections", "users", "workers", "supervisors", "admins"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        counts_before[table] = cursor.fetchone()[0]

    print("\n--- Record Counts Before Reset ---")
    for t, cnt in counts_before.items():
        print(f"  {t}: {cnt}")

    # 3. Clean transactional records respecting FK hierarchy
    # evidence -> assignments -> detections -> complaints -> notifications
    cursor.execute("DELETE FROM evidence")
    evidence_deleted = cursor.rowcount

    cursor.execute("DELETE FROM assignments")
    assignments_deleted = cursor.rowcount

    cursor.execute("DELETE FROM detections")
    detections_deleted = cursor.rowcount

    cursor.execute("DELETE FROM complaints")
    complaints_deleted = cursor.rowcount

    cursor.execute("DELETE FROM notifications")
    notifications_deleted = cursor.rowcount

    conn.commit()

    # Verify FK integrity
    fk_errors = cursor.execute("PRAGMA foreign_key_check;").fetchall()
    if fk_errors:
        print(f"[ERROR] Foreign key violations found: {fk_errors}")
        conn.rollback()
        conn.close()
        return False

    # 4. Count after deletion
    counts_after = {}
    for table in ["complaints", "assignments", "evidence", "notifications", "detections", "users", "workers", "supervisors", "admins"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        counts_after[table] = cursor.fetchone()[0]

    print("\n--- Record Counts After Reset ---")
    for t, cnt in counts_after.items():
        print(f"  {t}: {cnt}")

    conn.close()

    # 5. Clean up old uploads files
    upload_dirs = [
        BASE_DIR / "uploads" / "complaints",
        BASE_DIR / "uploads" / "evidence",
        BASE_DIR / "uploads" / "detections",
        BASE_DIR / "uploads" / "videos"
    ]
    files_removed = 0
    for udir in upload_dirs:
        if udir.exists():
            for f in udir.iterdir():
                if f.is_file() and not f.name.startswith("."):
                    try:
                        f.unlink()
                        files_removed += 1
                    except Exception as e:
                        print(f"  Could not delete {f}: {e}")

    print(f"\n[Uploads Cleanup] Removed {files_removed} old transactional files from uploads directory.")
    print("[Success] Complaint transactional data reset complete! Complaint count = 0.")
    return True

if __name__ == "__main__":
    reset_database()

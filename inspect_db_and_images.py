import sqlite3
import os
from pathlib import Path

conn = sqlite3.connect('visionguard.db')
c = conn.cursor()

tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('Tables:', tables)

for t in tables:
    c.execute(f"PRAGMA table_info({t})")
    cols = [col[1] for col in c.fetchall()]
    print(f"\n--- TABLE: {t} ---")
    print(f"Columns: {cols}")
    c.execute(f"SELECT * FROM {t} LIMIT 3")
    for r in c.fetchall():
        print("  Row:", r)

print("\n--- FILES IN UPLOADS ---")
for root, dirs, files in os.walk('uploads'):
    print(root, files)

print("\n--- FILES IN STATIC ---")
for root, dirs, files in os.walk('static'):
    print(root, files)

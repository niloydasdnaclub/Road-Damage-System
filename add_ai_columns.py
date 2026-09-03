import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

existing = [row[1] for row in cursor.execute("PRAGMA table_info(complaints)")]

if "ai_problem" not in existing:
    cursor.execute("ALTER TABLE complaints ADD COLUMN ai_problem TEXT DEFAULT 'Not Analyzed'")
    print("Added ai_problem")

if "severity_score" not in existing:
    cursor.execute("ALTER TABLE complaints ADD COLUMN severity_score INTEGER DEFAULT 0")
    print("Added severity_score")

if "priority" not in existing:
    cursor.execute("ALTER TABLE complaints ADD COLUMN priority TEXT DEFAULT 'Low'")
    print("Added priority")

conn.commit()
conn.close()

print("Database update complete!")
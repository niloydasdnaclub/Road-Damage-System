import sqlite3
from app import analyze_complaint, DATABASE

conn = sqlite3.connect(DATABASE)
conn.row_factory = sqlite3.Row

complaints = conn.execute("""
    SELECT id, problem_type, description
    FROM complaints
""").fetchall()

print(f"Found {len(complaints)} complaints")

for complaint in complaints:

    ai_problem, severity_score, priority = analyze_complaint(
        complaint["problem_type"],
        complaint["description"]
    )

    conn.execute("""
        UPDATE complaints
        SET
            ai_problem = ?,
            severity_score = ?,
            priority = ?
        WHERE id = ?
    """, (
        ai_problem,
        severity_score,
        priority,
        complaint["id"]
    ))

    print(
        complaint["id"],
        "→",
        ai_problem,
        "| Score:",
        severity_score,
        "| Priority:",
        priority
    )

conn.commit()
conn.close()

print()
print("AI UPDATE COMPLETE!")
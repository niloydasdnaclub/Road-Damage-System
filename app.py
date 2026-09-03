
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory
)

import sqlite3
import os
import uuid
from datetime import datetime


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__, template_folder=".")
app.secret_key = "CHANGE_THIS_TO_A_STRONG_SECRET_KEY"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def add_column_if_missing(conn, table, column, definition):

    columns = [
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    ]

    if column not in columns:

        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_db():

    conn = get_db()

    # =====================================================
    # COMPLAINTS TABLE
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT UNIQUE,
            name TEXT,
            mobile TEXT,
            email TEXT,
            address TEXT,
            latitude TEXT,
            longitude TEXT,
            problem_type TEXT,
            description TEXT,
            photo TEXT,
            video TEXT,
            status TEXT DEFAULT 'Submitted',
            department TEXT DEFAULT 'Not Assigned',
            branch TEXT DEFAULT 'Not Assigned',
            officer TEXT DEFAULT 'Not Assigned',
            created_at TEXT
        )
    """)

    # =====================================================
    # OFFICERS TABLE
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS officers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            department TEXT,
            branch TEXT,
            mobile TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT
        )
    """)

    # =====================================================
    # AI COLUMNS
    # =====================================================

    add_column_if_missing(
        conn,
        "complaints",
        "ai_problem",
        "TEXT DEFAULT 'Not Analyzed'"
    )

    add_column_if_missing(
        conn,
        "complaints",
        "severity_score",
        "INTEGER DEFAULT 0"
    )

    add_column_if_missing(
        conn,
        "complaints",
        "priority",
        "TEXT DEFAULT 'Low'"
    )

    # =====================================================
    # OFFICER CREATED_AT
    # =====================================================

    add_column_if_missing(
        conn,
        "officers",
        "created_at",
        "TEXT"
    )

    conn.commit()
    conn.close()


# IMPORTANT FOR RENDER/GUNICORN
init_db()


# =========================================================
# AI ANALYSIS
# DESCRIPTION + PHOTO
# =========================================================

def analyze_complaint(
    problem_type="",
    description="",
    photo=""
):

    problem = str(
        problem_type or ""
    ).lower().strip()

    desc = str(
        description or ""
    ).lower().strip()

    photo_name = str(
        photo or ""
    ).lower().strip()

    text = problem + " " + desc

    score = 0


    # =====================================================
    # EMERGENCY WORDS
    # =====================================================

    emergency_words = [

        "electric shock",
        "electric shock risk",
        "electrocution",
        "electrocuted",

        "live wire",
        "live electric wire",

        "wire have current",
        "wire has current",

        "current",
        "high voltage",

        "danger to life",
        "dangerous",

        "life threatening",
        "life-threatening",

        "immediate danger",
        "emergency",

        "fatal",
        "killed",
        "death",

        "people dead",
        "person dead",
        "many people dead",
        "someone died",
        "people are dead"
    ]

    emergency_found = any(
        word in text
        for word in emergency_words
    )

    if emergency_found:
        score += 40


    # =====================================================
    # ELECTRICAL
    # =====================================================

    electrical_words = [

        "electric wire",
        "electrical wire",
        "electricity wire",

        "power wire",
        "power line",
        "electric line",

        "fallen wire",
        "fallen electric wire",
        "fallen power line",

        "wire fallen",
        "wire down",

        "electric pole",
        "electricity pole",
        "power pole",

        "electric cable",
        "electrical cable",
        "power cable",

        "live wire",

        "electric current",
        "current wire",

        "high voltage",

        "transformer",

        "electricity line"
    ]

    electrical_found = any(
        word in text
        for word in electrical_words
    )

    # Additional electrical detection
    if (
        "wire" in text
        and (
            "electric" in text
            or "current" in text
            or "power" in text
            or "voltage" in text
        )
    ):
        electrical_found = True

    if electrical_found:
        score += 35


    # =====================================================
    # CRITICAL INFRASTRUCTURE
    # =====================================================

    critical_words = [

        "bridge collapse",
        "bridge collapsed",

        "road collapse",
        "road collapsed",

        "building collapse",
        "building collapsed",

        "wall collapse",
        "wall collapsed",

        "major accident",

        "landslide",

        "flooded road",

        "road completely broken",

        "completely destroyed"
    ]

    critical_found = any(
        word in text
        for word in critical_words
    )

    if critical_found:
        score += 30


    # =====================================================
    # HIGH SEVERITY
    # =====================================================

    high_words = [

        "large pothole",
        "big pothole",
        "deep pothole",
        "huge pothole",

        "large crack",
        "deep crack",

        "broken road",
        "damaged road",
        "road damage",

        "danger",
        "unsafe",

        "traffic problem",

        "waterlogging",

        "blocked road",
        "road blocked",

        "severe damage",
        "major damage"
    ]

    for word in high_words:

        if word in text:
            score += 20


    # =====================================================
    # MEDIUM SEVERITY
    # =====================================================

    medium_words = [

        "pothole",
        "crack",
        "broken",
        "damaged",

        "street light",
        "streetlight",

        "drain",
        "drainage",

        "garbage",

        "water leak",
        "water leakage",
        "leakage",

        "footpath",
        "sidewalk"
    ]

    for word in medium_words:

        if word in text:
            score += 12


    # =====================================================
    # LOW SEVERITY
    # =====================================================

    low_words = [

        "small crack",
        "minor",
        "light damage",
        "slight damage",

        "dirty",
        "cleaning",
        "maintenance"
    ]

    for word in low_words:

        if word in text:
            score += 5


    # =====================================================
    # PROBLEM TYPE BASE SCORE
    # =====================================================

    if "pothole" in problem:

        score += 25

    elif "road" in problem:

        score += 20

    elif "bridge" in problem:

        score += 30

    elif "accident" in problem:

        score += 35

    elif (
        "electric" in problem
        or "electrical" in problem
        or "wire" in problem
        or "power" in problem
    ):

        score += 25

    elif (
        "street" in problem
        and "light" in problem
    ):

        score += 10

    elif "drain" in problem:

        score += 15


    # =====================================================
    # FALLEN WIRE
    # =====================================================

    if (
        ("wire" in text or "cable" in text)
        and (
            "fallen" in text
            or "fall" in text
            or "down" in text
            or "broken" in text
        )
    ):

        score += 25


    # =====================================================
    # PUBLIC DANGER
    # =====================================================

    public_danger_words = [

        "many people",
        "people are",

        "public",

        "children",

        "crowd",

        "house",
        "houses",

        "road",

        "people walking",
        "people passing",

        "near school",
        "near hospital",
        "near market"
    ]

    public_danger_found = any(
        word in text
        for word in public_danger_words
    )

    if (
        electrical_found
        and public_danger_found
    ):

        score += 15


    # =====================================================
    # DESCRIPTION LENGTH
    # =====================================================

    if len(desc) > 100:
        score += 5

    if len(desc) > 250:
        score += 5


    # =====================================================
    # PHOTO PRESENT
    # =====================================================

    photo_found = bool(photo_name)

    if photo_found:

        score += 5


    # =====================================================
    # PHOTO FILENAME SIGNAL
    # =====================================================

    photo_signal_words = {

        "fire": 20,

        "accident": 25,

        "collapse": 25,

        "collapsed": 25,

        "pothole": 15,

        "road_damage": 15,

        "roaddamage": 15,

        "broken_road": 20,

        "bridge": 25,

        "electric": 20,

        "electrical": 20,

        "wire": 20,

        "livewire": 30,

        "powerline": 25,

        "flood": 20,

        "waterlogging": 15,

        "garbage": 10,

        "drain": 10,

        "streetlight": 10,

        "street_light": 10
    }

    for word, points in photo_signal_words.items():

        if word in photo_name:

            score += points


    # =====================================================
    # LIMIT SCORE
    # =====================================================

    score = min(score, 100)


    # =====================================================
    # AI CLASSIFICATION
    # =====================================================

    # Electrical MUST come before road.

    if electrical_found:

        ai_problem = "Electrical Infrastructure"

    elif critical_found:

        ai_problem = "Critical Infrastructure Damage"

    elif (
        "pothole" in text
        or "road damage" in text
        or "damaged road" in text
        or "broken road" in text
        or "crack" in text
    ):

        ai_problem = "Road Damage"

    elif (
        "drain" in text
        or "drainage" in text
        or "waterlogging" in text
        or "water leak" in text
    ):

        ai_problem = "Drainage / Water Issue"

    elif (
        "garbage" in text
        or "waste" in text
        or "dirty" in text
    ):

        ai_problem = "Waste Management Issue"

    elif (
        "footpath" in text
        or "sidewalk" in text
    ):

        ai_problem = "Footpath / Sidewalk Damage"

    elif (
        "street light" in text
        or "streetlight" in text
    ):

        ai_problem = "Street Light Issue"

    elif problem:

        ai_problem = problem_type

    else:

        ai_problem = "General Infrastructure Issue"


    # =====================================================
    # CRITICAL OVERRIDE
    # =====================================================

    if (
        electrical_found
        and emergency_found
    ):

        score = max(score, 95)

    elif (
        critical_found
        and emergency_found
    ):

        score = max(score, 95)


    # =====================================================
    # PRIORITY
    # =====================================================

    if score >= 80:

        priority = "Critical"

    elif score >= 60:

        priority = "High"

    elif score >= 30:

        priority = "Medium"

    else:

        priority = "Low"


    # Emergency protection

    if (
        electrical_found
        and emergency_found
    ):

        priority = "Critical"

    elif (
        critical_found
        and emergency_found
    ):

        priority = "Critical"


    return (
        ai_problem,
        score,
        priority
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# REPORT
# =========================================================

@app.route(
    "/report",
    methods=["GET", "POST"]
)
def report():

    if request.method == "GET":

        return render_template(
            "report.html"
        )


    # =====================================================
    # FORM DATA
    # =====================================================

    name = request.form.get(
        "name",
        ""
    )

    mobile = request.form.get(
        "mobile",
        ""
    )

    email = request.form.get(
        "email",
        ""
    )

    address = request.form.get(
        "address",
        ""
    )

    latitude = request.form.get(
        "latitude",
        ""
    )

    longitude = request.form.get(
        "longitude",
        ""
    )

    problem_type = request.form.get(
        "problem_type",
        ""
    )

    description = request.form.get(
        "description",
        ""
    )


    # =====================================================
    # COMPLAINT ID
    # =====================================================

    complaint_id = (
        "CIVIC-"
        + datetime.now().strftime("%Y")
        + "-"
        + uuid.uuid4().hex[:6].upper()
    )


    # =====================================================
    # PHOTO
    # =====================================================

    photo_file = request.files.get(
        "photo"
    )

    photo_filename = ""


    if (
        photo_file
        and photo_file.filename
    ):

        extension = os.path.splitext(
            photo_file.filename
        )[1].lower()

        photo_filename = (
            complaint_id
            + "_photo"
            + extension
        )

        photo_file.save(
            os.path.join(
                app.config["UPLOAD_FOLDER"],
                photo_filename
            )
        )


    # =====================================================
    # VIDEO
    # =====================================================

    video_file = request.files.get(
        "video"
    )

    video_filename = ""


    if (
        video_file
        and video_file.filename
    ):

        extension = os.path.splitext(
            video_file.filename
        )[1].lower()

        video_filename = (
            complaint_id
            + "_video"
            + extension
        )

        video_file.save(
            os.path.join(
                app.config["UPLOAD_FOLDER"],
                video_filename
            )
        )


    # =====================================================
    # AI
    # =====================================================

    (
        ai_problem,
        severity_score,
        priority
    ) = analyze_complaint(
        problem_type,
        description,
        photo_filename
    )


    # =====================================================
    # DEPARTMENT ROUTING
    # =====================================================

    lower_problem = (
        problem_type
        + " "
        + description
    ).lower()


    department = "Not Assigned"


    if (
        "electric" in lower_problem
        or "electrical" in lower_problem
        or "wire" in lower_problem
        or "power" in lower_problem
        or "street light" in lower_problem
        or "streetlight" in lower_problem
    ):

        department = "Electrical"

    elif (
        "road" in lower_problem
        or "pothole" in lower_problem
        or "bridge" in lower_problem
    ):

        department = "PWD / Roads"

    elif (
        "drain" in lower_problem
        or "drainage" in lower_problem
        or "water" in lower_problem
    ):

        department = "Water / Drainage"

    elif (
        "garbage" in lower_problem
        or "waste" in lower_problem
    ):

        department = "Municipality"


    # =====================================================
    # DATABASE INSERT
    # =====================================================

    conn = get_db()


    conn.execute("""
        INSERT INTO complaints (
            complaint_id,
            name,
            mobile,
            email,
            address,
            latitude,
            longitude,
            problem_type,
            description,
            photo,
            video,
            status,
            department,
            branch,
            officer,
            created_at,
            ai_problem,
            severity_score,
            priority
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, (

        complaint_id,

        name,

        mobile,

        email,

        address,

        latitude,

        longitude,

        problem_type,

        description,

        photo_filename,

        video_filename,

        "Submitted",

        department,

        "Not Assigned",

        "Not Assigned",

        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        ai_problem,

        severity_score,

        priority
    ))


    conn.commit()
    conn.close()


    # =====================================================
    # SUCCESS
    # =====================================================

    return render_template(
        "success.html",

        complaint_id=complaint_id,

        ai_problem=ai_problem,

        severity_score=severity_score,

        priority=priority
    )


# =========================================================
# UPLOADS
# =========================================================

@app.route(
    "/uploads/<filename>"
)
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# =========================================================
# PUBLIC TRACKING
# =========================================================

@app.route(
    "/track",
    methods=["GET", "POST"]
)
def track():

    complaint = None


    if request.method == "POST":

        complaint_id = request.form.get(
            "complaint_id",
            ""
        ).strip()


        conn = get_db()


        complaint = conn.execute("""
            SELECT *
            FROM complaints
            WHERE complaint_id = ?
        """, (
            complaint_id,
        )).fetchone()


        conn.close()


    return render_template(
        "track.html",
        complaint=complaint
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        )

        password = request.form.get(
            "password",
            ""
        )


        if (
            username == "admin"
            and password == "admin123"
        ):

            session["admin_logged_in"] = True

            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )


        return render_template(
            "admin_login.html",
            error="Invalid username or password"
        )


    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route(
    "/admin/logout"
)
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
def admin_dashboard():

    if not session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    complaints = conn.execute("""
        SELECT *
        FROM complaints
        ORDER BY id DESC
    """).fetchall()


    officers = conn.execute("""
        SELECT *
        FROM officers
        ORDER BY id DESC
    """).fetchall()


    total = conn.execute("""
        SELECT COUNT(*) AS count
        FROM complaints
    """).fetchone()["count"]


    submitted = conn.execute("""
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = 'Submitted'
    """).fetchone()["count"]


    pending = conn.execute("""
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = 'Pending'
    """).fetchone()["count"]


    in_progress = conn.execute("""
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = 'In Progress'
    """).fetchone()["count"]


    resolved = conn.execute("""
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = 'Resolved'
    """).fetchone()["count"]


    critical = conn.execute("""
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE priority = 'Critical'
    """).fetchone()["count"]


    high = conn.execute("""
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE priority = 'High'
    """).fetchone()["count"]


    medium = conn.execute("""
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE priority = 'Medium'
    """).fetchone()["count"]


    low = conn.execute("""
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE priority = 'Low'
    """).fetchone()["count"]


    conn.close()


    return render_template(
        "admin_dashboard.html",

        complaints=complaints,

        officers=officers,

        total=total,

        submitted=submitted,

        pending=pending,

        in_progress=in_progress,

        resolved=resolved,

        critical=critical,

        high=high,

        medium=medium,

        low=low
    )


# =========================================================
# ADD OFFICER
# =========================================================

@app.route(
    "/admin/officer/add",
    methods=["POST"]
)
def add_officer():

    if not session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for("admin_login")
        )


    name = request.form.get(
        "name",
        ""
    )

    department = request.form.get(
        "department",
        ""
    )

    branch = request.form.get(
        "branch",
        ""
    )

    mobile = request.form.get(
        "mobile",
        ""
    )


    conn = get_db()


    conn.execute("""
        INSERT INTO officers (
            name,
            department,
            branch,
            mobile,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (

        name,

        department,

        branch,

        mobile,

        "Active",

        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))


    conn.commit()
    conn.close()


    return redirect(
        url_for(
            "admin_dashboard"
        )
    )


# =========================================================
# DELETE OFFICER
# =========================================================

@app.route(
    "/admin/officer/<int:officer_id>/delete",
    methods=["POST"]
)
def delete_officer(
    officer_id
):

    if not session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    conn.execute("""
        DELETE FROM officers
        WHERE id = ?
    """, (
        officer_id,
    ))


    conn.commit()
    conn.close()


    return redirect(
        url_for(
            "admin_dashboard"
        )
    )


# =========================================================
# ASSIGN COMPLAINT
# =========================================================

@app.route(
    "/admin/complaint/<int:complaint_id>/assign",
    methods=["POST"]
)
def assign_complaint(
    complaint_id
):

    if not session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for("admin_login")
        )


    department = request.form.get(
        "department",
        "Not Assigned"
    )

    branch = request.form.get(
        "branch",
        "Not Assigned"
    )

    officer = request.form.get(
        "officer",
        "Not Assigned"
    )


    conn = get_db()


    conn.execute("""
        UPDATE complaints
        SET
            department = ?,
            branch = ?,
            officer = ?,
            status = 'Assigned'
        WHERE id = ?
    """, (

        department,

        branch,

        officer,

        complaint_id
    ))


    conn.commit()
    conn.close()


    return redirect(
        url_for(
            "admin_dashboard"
        )
    )


# =========================================================
# ADMIN UPDATE STATUS
# =========================================================

@app.route(
    "/admin/complaint/<int:complaint_id>/update",
    methods=["POST"]
)
def admin_update_complaint(
    complaint_id
):

    if not session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for("admin_login")
        )


    status = request.form.get(
        "status",
        "Submitted"
    )


    conn = get_db()


    conn.execute("""
        UPDATE complaints
        SET status = ?
        WHERE id = ?
    """, (

        status,

        complaint_id
    ))


    conn.commit()
    conn.close()


    return redirect(
        url_for(
            "admin_dashboard"
        )
    )


# =========================================================
# OFFICER LOGIN
# =========================================================

@app.route(
    "/officer/login",
    methods=["GET", "POST"]
)
def officer_login():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        mobile = request.form.get(
            "mobile",
            ""
        ).strip()


        conn = get_db()


        officer = conn.execute("""
            SELECT *
            FROM officers
            WHERE name = ?
            AND mobile = ?
        """, (
            name,
            mobile
        )).fetchone()


        conn.close()


        if officer:

            session["officer_logged_in"] = True

            session["officer_id"] = officer["id"]

            return redirect(
                url_for(
                    "officer_dashboard",
                    officer_id=officer["id"]
                )
            )


        return render_template(
            "officer_login.html",
            error="Invalid officer name or mobile number"
        )


    return render_template(
        "officer_login.html"
    )


# =========================================================
# OFFICER LOGOUT
# =========================================================

@app.route(
    "/officer/logout"
)
def officer_logout():

    session.pop(
        "officer_logged_in",
        None
    )

    session.pop(
        "officer_id",
        None
    )

    return redirect(
        url_for(
            "officer_login"
        )
    )


# =========================================================
# OFFICER DASHBOARD
# =========================================================

@app.route(
    "/officer/<int:officer_id>"
)
def officer_dashboard(
    officer_id
):

    # Officer login protection

    if (
        not session.get(
            "officer_logged_in"
        )
        or session.get(
            "officer_id"
        ) != officer_id
    ):

        return redirect(
            url_for(
                "officer_login"
            )
        )


    conn = get_db()


    officer = conn.execute("""
        SELECT *
        FROM officers
        WHERE id = ?
    """, (
        officer_id,
    )).fetchone()


    if not officer:

        conn.close()

        return "Officer not found", 404


    complaints = conn.execute("""
        SELECT *
        FROM complaints
        WHERE officer = ?
        ORDER BY id DESC
    """, (
        officer["name"],
    )).fetchall()


    total = len(
        complaints
    )


    submitted = sum(
        1
        for c in complaints
        if c["status"] == "Submitted"
    )


    pending = sum(
        1
        for c in complaints
        if c["status"] == "Pending"
    )


    in_progress = sum(
        1
        for c in complaints
        if c["status"] == "In Progress"
    )


    resolved = sum(
        1
        for c in complaints
        if c["status"] == "Resolved"
    )


    conn.close()


    return render_template(
        "officer_dashboard.html",

        officer=officer,

        complaints=complaints,

        total=total,

        submitted=submitted,

        pending=pending,

        in_progress=in_progress,

        resolved=resolved
    )


# =========================================================
# OFFICER UPDATE COMPLAINT
# =========================================================

@app.route(
    "/officer/<int:officer_id>/complaint/<int:complaint_id>/update",
    methods=["POST"]
)
def officer_update_complaint(
    officer_id,
    complaint_id
):

    if (
        not session.get(
            "officer_logged_in"
        )
        or session.get(
            "officer_id"
        ) != officer_id
    ):

        return redirect(
            url_for(
                "officer_login"
            )
        )


    status = request.form.get(
        "status",
        "Submitted"
    )


    conn = get_db()


    officer = conn.execute("""
        SELECT *
        FROM officers
        WHERE id = ?
    """, (
        officer_id,
    )).fetchone()


    if not officer:

        conn.close()

        return "Officer not found", 404


    conn.execute("""
        UPDATE complaints
        SET status = ?
        WHERE id = ?
        AND officer = ?
    """, (

        status,

        complaint_id,

        officer["name"]
    ))


    conn.commit()
    conn.close()


    return redirect(
        url_for(
            "officer_dashboard",
            officer_id=officer_id
        )
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health")
def health():

    try:

        conn = get_db()

        conn.execute(
            "SELECT 1"
        ).fetchone()

        conn.close()

        return "OK", 200

    except Exception as e:

        return (
            "Database Error: "
            + str(e),
            500
        )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True
    )


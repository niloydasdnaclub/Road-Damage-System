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
# DATABASE CONNECTION
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# DATABASE INITIALIZATION + MIGRATION
# =========================================================

def init_db():

    conn = get_db()

    # -----------------------------------------------------
    # COMPLAINTS TABLE
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            complaint_id TEXT UNIQUE,

            name TEXT NOT NULL,
            mobile TEXT NOT NULL,
            email TEXT,

            address TEXT NOT NULL,

            latitude TEXT,
            longitude TEXT,

            problem_type TEXT NOT NULL,

            description TEXT NOT NULL,

            photo TEXT,
            video TEXT,

            status TEXT DEFAULT 'Submitted',

            department TEXT DEFAULT 'Not Assigned',

            branch TEXT DEFAULT 'Not Assigned',

            officer TEXT DEFAULT 'Not Assigned',

            created_at TEXT NOT NULL,

            ai_problem TEXT DEFAULT 'Not Analyzed',

            severity_score INTEGER DEFAULT 0,

            priority TEXT DEFAULT 'Low'
        )
    """)

    # -----------------------------------------------------
    # OFFICERS TABLE
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS officers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            department TEXT NOT NULL,

            branch TEXT NOT NULL,

            mobile TEXT,

            status TEXT DEFAULT 'Active',

            created_at TEXT
        )
    """)

    # -----------------------------------------------------
    # MIGRATION FOR OLD DATABASE
    # -----------------------------------------------------

    complaint_columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(complaints)"
        ).fetchall()
    ]

    # AI problem column
    if "ai_problem" not in complaint_columns:

        conn.execute("""
            ALTER TABLE complaints
            ADD COLUMN ai_problem TEXT DEFAULT 'Not Analyzed'
        """)

    # Severity score column
    if "severity_score" not in complaint_columns:

        conn.execute("""
            ALTER TABLE complaints
            ADD COLUMN severity_score INTEGER DEFAULT 0
        """)

    # Priority column
    if "priority" not in complaint_columns:

        conn.execute("""
            ALTER TABLE complaints
            ADD COLUMN priority TEXT DEFAULT 'Low'
        """)

    # -----------------------------------------------------
    # OFFICER CREATED_AT MIGRATION
    # -----------------------------------------------------

    officer_columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(officers)"
        ).fetchall()
    ]

    if "created_at" not in officer_columns:

        conn.execute("""
            ALTER TABLE officers
            ADD COLUMN created_at TEXT
        """)

    # Fill missing officer created_at
    conn.execute("""
        UPDATE officers
        SET created_at = ?
        WHERE created_at IS NULL OR created_at = ''
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))

    conn.commit()

    conn.close()


# =========================================================
# SMART AI / SEVERITY ANALYZER
# =========================================================

def analyze_complaint(problem_type, description):

    """
    Smart rule-based complaint analyzer.

    It analyzes:
    - Problem type
    - Complaint description

    And returns:
    - AI detected problem
    - Severity score 0-100
    - Priority
    """

    problem_text = str(problem_type or "")
    description_text = str(description or "")

    text = (
        problem_text
        + " "
        + description_text
    ).lower()

    # -----------------------------------------------------
    # BASE SCORE
    # -----------------------------------------------------

    score = 20

    # -----------------------------------------------------
    # SEVERE KEYWORDS
    # -----------------------------------------------------

    severe_words = [

        "danger",
        "dangerous",
        "accident",
        "accidents",

        "life threatening",
        "life-threatening",

        "collapsed",
        "collapse",

        "bridge broken",
        "bridge collapse",
        "bridge collapsed",

        "road completely broken",
        "road fully broken",

        "major damage",
        "massive damage",

        "very deep",
        "extremely deep",

        "huge pothole",
        "large pothole",

        "electric shock",
        "electrocution",

        "fire",

        "flood",

        "death",
        "dead",

        "school accident",
        "hospital danger"
    ]

    # -----------------------------------------------------
    # HIGH PRIORITY KEYWORDS
    # -----------------------------------------------------

    high_words = [

        "deep pothole",
        "big pothole",
        "large crack",

        "broken road",
        "road broken",

        "severe",
        "heavy damage",

        "unsafe",
        "dangerous road",

        "traffic problem",
        "traffic danger",

        "waterlogging",
        "water logging",

        "blocked road",
        "road blocked",

        "fallen tree",

        "broken electric pole",
        "electric pole broken",

        "wire hanging",
        "electric wire",

        "drain blocked",
        "drain broken",

        "bridge damage"
    ]

    # -----------------------------------------------------
    # MEDIUM PRIORITY KEYWORDS
    # -----------------------------------------------------

    medium_words = [

        "pothole",
        "crack",

        "damaged",
        "damage",

        "broken",

        "drain problem",
        "drainage problem",

        "street light",
        "streetlight",

        "road damage",

        "water problem",
        "water leakage",

        "garbage",

        "footpath",
        "sidewalk"
    ]

    # -----------------------------------------------------
    # SCORE CALCULATION
    # -----------------------------------------------------

    for word in severe_words:

        if word in text:
            score += 25

    for word in high_words:

        if word in text:
            score += 15

    for word in medium_words:

        if word in text:
            score += 8

    # -----------------------------------------------------
    # ROAD DAMAGE BOOST
    # -----------------------------------------------------

    if "road" in text:

        score += 10

    if "pothole" in text:

        score += 10

    # -----------------------------------------------------
    # BRIDGE BOOST
    # -----------------------------------------------------

    if "bridge" in text:

        score += 20

    # -----------------------------------------------------
    # ELECTRICAL BOOST
    # -----------------------------------------------------

    if (
        "electric" in text
        or "electricity" in text
        or "wire" in text
        or "pole" in text
    ):

        score += 20

    # -----------------------------------------------------
    # WATER / FLOOD BOOST
    # -----------------------------------------------------

    if (
        "water" in text
        or "flood" in text
        or "waterlogging" in text
        or "drain" in text
    ):

        score += 15

    # -----------------------------------------------------
    # SAFETY BOOST
    # -----------------------------------------------------

    if (
        "school" in text
        or "hospital" in text
        or "market" in text
        or "main road" in text
    ):

        score += 10

    # -----------------------------------------------------
    # LIMIT SCORE
    # -----------------------------------------------------

    score = max(0, min(score, 100))

    # -----------------------------------------------------
    # PRIORITY
    # -----------------------------------------------------

    if score >= 80:

        priority = "Critical"

    elif score >= 60:

        priority = "High"

    elif score >= 35:

        priority = "Medium"

    else:

        priority = "Low"

    # -----------------------------------------------------
    # AI PROBLEM CLASSIFICATION
    # -----------------------------------------------------

    # Bridge
    if (
        "bridge" in text
        or "culvert" in text
    ):

        ai_problem = "Bridge / Culvert Damage"

    # Electrical
    elif (
        "electric" in text
        or "electricity" in text
        or "street light" in text
        or "streetlight" in text
        or "wire" in text
        or "electric pole" in text
        or "pole" in text
    ):

        ai_problem = "Electrical Problem"

    # Water / Drainage
    elif (
        "water" in text
        or "flood" in text
        or "waterlogging" in text
        or "water logging" in text
        or "drain" in text
        or "drainage" in text
    ):

        ai_problem = "Water / Drainage Problem"

    # Road
    elif (
        "road" in text
        or "pothole" in text
        or "crack" in text
        or "highway" in text
        or "street" in text
    ):

        ai_problem = "Road Damage"

    # Garbage
    elif (
        "garbage" in text
        or "waste" in text
        or "trash" in text
    ):

        ai_problem = "Waste Management Problem"

    # Footpath
    elif (
        "footpath" in text
        or "sidewalk" in text
    ):

        ai_problem = "Footpath Problem"

    # Tree
    elif (
        "tree" in text
        or "fallen tree" in text
    ):

        ai_problem = "Fallen Tree / Obstruction"

    # General
    else:

        ai_problem = "General Infrastructure Problem"

    return ai_problem, score, priority


# =========================================================
# RUN DATABASE INITIALIZATION
# IMPORTANT FOR RENDER / GUNICORN
# =========================================================

init_db()


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return render_template("index.html")


# =========================================================
# REPORT COMPLAINT
# =========================================================

@app.route("/report", methods=["GET", "POST"])
def report():

    if request.method == "POST":

        # -------------------------------------------------
        # FORM DATA
        # -------------------------------------------------

        name = request.form.get("name", "").strip()

        mobile = request.form.get("mobile", "").strip()

        email = request.form.get("email", "").strip()

        address = request.form.get("address", "").strip()

        location = request.form.get("location", "").strip()

        problem_type = request.form.get(
            "problem_type",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        # -------------------------------------------------
        # LOCATION
        # -------------------------------------------------

        latitude = ""

        longitude = ""

        if location:

            try:

                if "," in location:

                    parts = location.split(",")

                    latitude = parts[0].strip()

                    longitude = parts[1].strip()

            except Exception:

                latitude = ""

                longitude = ""

        # -------------------------------------------------
        # PHOTO UPLOAD
        # -------------------------------------------------

        photo_filename = None

        photo = request.files.get("photo")

        if photo and photo.filename:

            extension = os.path.splitext(
                photo.filename
            )[1]

            photo_filename = (
                str(uuid.uuid4())
                + extension
            )

            photo.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    photo_filename
                )
            )

        # -------------------------------------------------
        # VIDEO UPLOAD
        # -------------------------------------------------

        video_filename = None

        video = request.files.get("video")

        if video and video.filename:

            extension = os.path.splitext(
                video.filename
            )[1]

            video_filename = (
                str(uuid.uuid4())
                + extension
            )

            video.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    video_filename
                )
            )

        # -------------------------------------------------
        # GENERATE COMPLAINT ID
        # -------------------------------------------------

        complaint_id = (
            "CIVIC-"
            + datetime.now().strftime("%Y")
            + "-"
            + str(uuid.uuid4())[:6].upper()
        )

        # -------------------------------------------------
        # CREATED TIME
        # -------------------------------------------------

        created_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # -------------------------------------------------
        # SMART AI ANALYSIS
        # -------------------------------------------------

        ai_problem, severity_score, priority = (
            analyze_complaint(
                problem_type,
                description
            )
        )

        # -------------------------------------------------
        # DATABASE INSERT
        # -------------------------------------------------

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

                ?,

                ?,
                ?,
                ?,

                ?,

                ?,
                ?,

                ?,

                ?,

                ?,
                ?,

                'Submitted',

                'Not Assigned',
                'Not Assigned',
                'Not Assigned',

                ?,

                ?,
                ?,
                ?

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

            created_at,

            ai_problem,
            severity_score,
            priority
        ))

        conn.commit()

        conn.close()

        # -------------------------------------------------
        # SUCCESS PAGE
        # -------------------------------------------------

        return render_template(
            "success.html",
            complaint_id=complaint_id,
            ai_problem=ai_problem,
            severity_score=severity_score,
            priority=priority
        )

    # -----------------------------------------------------
    # GET REQUEST
    # -----------------------------------------------------

    return render_template("report.html")


# =========================================================
# TRACK COMPLAINT
# =========================================================

@app.route("/track", methods=["GET", "POST"])
def track():

    complaint = None

    error = None

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

        if not complaint:

            error = "Complaint ID not found."

    return render_template(
        "track.html",
        complaint=complaint,
        error=error
    )


# =========================================================
# SERVE UPLOADED FILES
# =========================================================

@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        if (
            username == "admin"
            and password == "Admin@123"
        ):

            session["admin"] = True

            return redirect(
                url_for("admin_dashboard")
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

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin", None)

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# ADMIN AUTH CHECK
# =========================================================

def admin_required():

    return session.get("admin") is True


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
def admin_dashboard():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    # -----------------------------------------------------
    # ALL COMPLAINTS
    # -----------------------------------------------------

    complaints = conn.execute("""
        SELECT *
        FROM complaints
        ORDER BY id DESC
    """).fetchall()

    # -----------------------------------------------------
    # ALL OFFICERS
    # -----------------------------------------------------

    officers = conn.execute("""
        SELECT *
        FROM officers
        ORDER BY id DESC
    """).fetchall()

    # -----------------------------------------------------
    # STATS
    # -----------------------------------------------------

    total = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
    """).fetchone()[0]

    submitted = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Submitted'
    """).fetchone()[0]

    pending = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Pending'
    """).fetchone()[0]

    in_progress = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'In Progress'
    """).fetchone()[0]

    resolved = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Resolved'
    """).fetchone()[0]

    # -----------------------------------------------------
    # NEW COMPLAINTS
    # -----------------------------------------------------

    new_complaints = conn.execute("""
        SELECT *
        FROM complaints
        WHERE status = 'Submitted'
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

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

        new_complaints=new_complaints
    )


# =========================================================
# OFFICER MANAGEMENT
# =========================================================

@app.route("/admin/officers")
def officers():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    officer_list = conn.execute("""
        SELECT *
        FROM officers
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "officers.html",
        officers=officer_list
    )


# =========================================================
# ADD OFFICER
# =========================================================

@app.route(
    "/admin/officers/add",
    methods=["GET", "POST"]
)
def add_officer():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        department = request.form.get(
            "department",
            ""
        ).strip()

        branch = request.form.get(
            "branch",
            ""
        ).strip()

        mobile = request.form.get(
            "mobile",
            ""
        ).strip()

        created_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
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

            VALUES (
                ?,
                ?,
                ?,
                ?,
                'Active',
                ?
            )
        """, (
            name,
            department,
            branch,
            mobile,
            created_at
        ))

        conn.commit()

        conn.close()

        return redirect(
            url_for("officers")
        )

    return render_template(
        "add_officer.html"
    )


# =========================================================
# DELETE OFFICER
# =========================================================

@app.route(
    "/admin/officers/delete/<int:officer_id>"
)
def delete_officer(officer_id):

    if not admin_required():

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
        url_for("officers")
    )


# =========================================================
# ASSIGN COMPLAINT
# =========================================================

@app.route(
    "/admin/complaint/<int:complaint_id>/assign",
    methods=["POST"]
)
def assign_complaint(complaint_id):

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    department = request.form.get(
        "department",
        "Not Assigned"
    ).strip()

    branch = request.form.get(
        "branch",
        "Not Assigned"
    ).strip()

    officer = request.form.get(
        "officer",
        "Not Assigned"
    ).strip()

    conn = get_db()

    conn.execute("""
        UPDATE complaints

        SET
            department = ?,
            branch = ?,
            officer = ?,
            status = 'Pending'

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
        url_for("admin_dashboard")
    )


# =========================================================
# ADMIN UPDATE COMPLAINT
# =========================================================

@app.route(
    "/admin/complaint/<int:complaint_id>/update",
    methods=["POST"]
)
def update_complaint(complaint_id):

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    status = request.form.get(
        "status",
        "Submitted"
    ).strip()

    department = request.form.get(
        "department",
        "Not Assigned"
    ).strip()

    branch = request.form.get(
        "branch",
        "Not Assigned"
    ).strip()

    officer = request.form.get(
        "officer",
        "Not Assigned"
    ).strip()

    conn = get_db()

    conn.execute("""
        UPDATE complaints

        SET
            status = ?,
            department = ?,
            branch = ?,
            officer = ?

        WHERE id = ?
    """, (
        status,
        department,
        branch,
        officer,
        complaint_id
    ))

    conn.commit()

    conn.close()

    return redirect(
        url_for("admin_dashboard")
    )


# =========================================================
# ADMIN STATUS UPDATE
# =========================================================

@app.route(
    "/admin/complaint/<int:complaint_id>/status",
    methods=["POST"]
)
def update_complaint_status(complaint_id):

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    status = request.form.get(
        "status",
        "Submitted"
    ).strip()

    allowed_statuses = [
        "Submitted",
        "Pending",
        "In Progress",
        "Resolved"
    ]

    if status not in allowed_statuses:

        status = "Submitted"

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
        url_for("admin_dashboard")
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

        officer_id = request.form.get(
            "officer_id",
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

            WHERE id = ?
            AND mobile = ?
            AND status = 'Active'
        """, (
            officer_id,
            mobile
        )).fetchone()

        conn.close()

        if officer:

            session["officer_id"] = officer["id"]

            return redirect(
                url_for(
                    "officer_dashboard",
                    officer_id=officer["id"]
                )
            )

        return render_template(
            "officer_login.html",
            error="Invalid Officer ID or Mobile Number"
        )

    return render_template(
        "officer_login.html"
    )


# =========================================================
# OFFICER LOGOUT
# =========================================================

@app.route("/officer/logout")
def officer_logout():

    session.pop("officer_id", None)

    return redirect(
        url_for("officer_login")
    )


# =========================================================
# OFFICER DASHBOARD
# =========================================================

@app.route(
    "/officer/<int:officer_id>"
)
def officer_dashboard(officer_id):

    if session.get("officer_id") != officer_id:

        return redirect(
            url_for("officer_login")
        )

    conn = get_db()

    # -----------------------------------------------------
    # OFFICER DETAILS
    # -----------------------------------------------------

    officer = conn.execute("""
        SELECT *
        FROM officers
        WHERE id = ?
    """, (
        officer_id,
    )).fetchone()

    if not officer:

        conn.close()

        return redirect(
            url_for("officer_login")
        )

    # -----------------------------------------------------
    # ASSIGNED COMPLAINTS
    # -----------------------------------------------------

    assigned_complaints = conn.execute("""
        SELECT *
        FROM complaints

        WHERE officer = ?

        ORDER BY id DESC
    """, (
        officer["name"],
    )).fetchall()

    # -----------------------------------------------------
    # OFFICER STATS
    # -----------------------------------------------------

    total_assigned = conn.execute("""
        SELECT COUNT(*)
        FROM complaints

        WHERE officer = ?
    """, (
        officer["name"],
    )).fetchone()[0]

    submitted = conn.execute("""
        SELECT COUNT(*)
        FROM complaints

        WHERE officer = ?
        AND status = 'Submitted'
    """, (
        officer["name"],
    )).fetchone()[0]

    pending = conn.execute("""
        SELECT COUNT(*)
        FROM complaints

        WHERE officer = ?
        AND status = 'Pending'
    """, (
        officer["name"],
    )).fetchone()[0]

    in_progress = conn.execute("""
        SELECT COUNT(*)
        FROM complaints

        WHERE officer = ?
        AND status = 'In Progress'
    """, (
        officer["name"],
    )).fetchone()[0]

    resolved = conn.execute("""
        SELECT COUNT(*)
        FROM complaints

        WHERE officer = ?
        AND status = 'Resolved'
    """, (
        officer["name"],
    )).fetchone()[0]

    conn.close()

    return render_template(
        "officer_dashboard.html",

        officer=officer,

        complaints=assigned_complaints,

        total_assigned=total_assigned,

        submitted=submitted,

        pending=pending,

        in_progress=in_progress,

        resolved=resolved
    )


# =========================================================
# OFFICER UPDATE COMPLAINT STATUS
# =========================================================

@app.route(
    "/officer/<int:officer_id>/complaint/<int:complaint_id>/update",
    methods=["POST"]
)
def officer_update_complaint(
    officer_id,
    complaint_id
):

    # -----------------------------------------------------
    # CHECK LOGIN
    # -----------------------------------------------------

    if session.get("officer_id") != officer_id:

        return redirect(
            url_for("officer_login")
        )

    status = request.form.get(
        "status",
        "Submitted"
    ).strip()

    allowed_statuses = [
        "Submitted",
        "Pending",
        "In Progress",
        "Resolved"
    ]

    if status not in allowed_statuses:

        status = "Submitted"

    conn = get_db()

    # -----------------------------------------------------
    # GET OFFICER
    # -----------------------------------------------------

    officer = conn.execute("""
        SELECT *
        FROM officers
        WHERE id = ?
    """, (
        officer_id,
    )).fetchone()

    if not officer:

        conn.close()

        return redirect(
            url_for("officer_login")
        )

    # -----------------------------------------------------
    # CHECK COMPLAINT ASSIGNMENT
    # -----------------------------------------------------

    complaint = conn.execute("""
        SELECT *
        FROM complaints

        WHERE id = ?
        AND officer = ?
    """, (
        complaint_id,
        officer["name"]
    )).fetchone()

    if not complaint:

        conn.close()

        return redirect(
            url_for(
                "officer_dashboard",
                officer_id=officer_id
            )
        )

    # -----------------------------------------------------
    # UPDATE STATUS
    # -----------------------------------------------------

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

    return {
        "status": "ok",
        "service": "CivicReport",
        "time": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )
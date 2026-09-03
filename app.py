import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    render_template_string,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
    jsonify
)

from werkzeug.utils import secure_filename


# ============================================================
# CIVICREPORT
# Public Infrastructure Complaint & Monitoring System
# ============================================================


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "civicreport-secret-key-change-this"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(
    BASE_DIR,
    "civicreport.db"
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "mp4",
    "mov",
    "avi",
    "mkv",
    "webm"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Maximum upload = 100 MB
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    conn = get_db()
    cursor = conn.cursor()

    # --------------------------------------------------------
    # COMPLAINTS TABLE
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            complaint_id TEXT UNIQUE,

            name TEXT NOT NULL,
            mobile TEXT NOT NULL,
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

            ai_problem TEXT DEFAULT '',
            severity_score INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'Low',

            created_at TEXT
        )
    """)

    # --------------------------------------------------------
    # OFFICERS TABLE
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS officers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            department TEXT NOT NULL,

            branch TEXT NOT NULL,

            mobile TEXT NOT NULL,

            status TEXT DEFAULT 'Active'
        )
    """)

    conn.commit()

    # ========================================================
    # MIGRATION FOR OLD DATABASE
    # ========================================================

    cursor.execute(
        "PRAGMA table_info(complaints)"
    )

    existing_columns = [
        column["name"]
        for column in cursor.fetchall()
    ]

    columns_to_add = {

        "complaint_id":
            "TEXT",

        "email":
            "TEXT",

        "address":
            "TEXT",

        "latitude":
            "TEXT",

        "longitude":
            "TEXT",

        "photo":
            "TEXT",

        "video":
            "TEXT",

        "status":
            "TEXT DEFAULT 'Submitted'",

        "department":
            "TEXT DEFAULT 'Not Assigned'",

        "branch":
            "TEXT DEFAULT 'Not Assigned'",

        "officer":
            "TEXT DEFAULT 'Not Assigned'",

        "ai_problem":
            "TEXT DEFAULT ''",

        "severity_score":
            "INTEGER DEFAULT 0",

        "priority":
            "TEXT DEFAULT 'Low'",

        "created_at":
            "TEXT"
    }

    for column_name, column_type in columns_to_add.items():

        if column_name not in existing_columns:

            try:

                cursor.execute(
                    f"""
                    ALTER TABLE complaints
                    ADD COLUMN {column_name} {column_type}
                    """
                )

            except sqlite3.OperationalError:
                pass

    # ========================================================
    # OFFICER MIGRATION
    # ========================================================

    cursor.execute(
        "PRAGMA table_info(officers)"
    )

    officer_columns = [
        column["name"]
        for column in cursor.fetchall()
    ]

    officer_columns_to_add = {

        "department":
            "TEXT DEFAULT 'Not Assigned'",

        "branch":
            "TEXT DEFAULT 'Not Assigned'",

        "mobile":
            "TEXT DEFAULT ''",

        "status":
            "TEXT DEFAULT 'Active'"
    }

    for column_name, column_type in officer_columns_to_add.items():

        if column_name not in officer_columns:

            try:

                cursor.execute(
                    f"""
                    ALTER TABLE officers
                    ADD COLUMN {column_name} {column_type}
                    """
                )

            except sqlite3.OperationalError:
                pass

    conn.commit()
    conn.close()


# ============================================================
# FILE HELPERS
# ============================================================

def allowed_file(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(
        ".",
        1
    )[1].lower()

    return extension in ALLOWED_EXTENSIONS


def save_uploaded_file(file):

    if not file:
        return None

    if not file.filename:
        return None

    if not allowed_file(file.filename):
        return None

    original_name = secure_filename(
        file.filename
    )

    if not original_name:
        return None

    extension = ""

    if "." in original_name:

        extension = original_name.rsplit(
            ".",
            1
        )[1].lower()

    unique_name = (
        uuid.uuid4().hex
        + "."
        + extension
    )

    save_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_name
    )

    file.save(save_path)

    return unique_name


# ============================================================
# AI COMPLAINT ANALYSIS
# ============================================================

def analyze_complaint(
    problem_type,
    description
):

    text = (
        str(problem_type or "")
        + " "
        + str(description or "")
    ).lower()

    ai_problem = (
        problem_type
        or "General Infrastructure Issue"
    )

    severity_score = 30

    # --------------------------------------------------------
    # ROAD
    # --------------------------------------------------------

    if any(
        word in text
        for word in [
            "pothole",
            "road damage",
            "broken road",
            "road broken",
            "crack",
            "road"
        ]
    ):

        ai_problem = "Road Damage"

        severity_score = 55

        if any(
            word in text
            for word in [
                "huge",
                "large",
                "deep",
                "dangerous",
                "accident",
                "accident risk",
                "major",
                "severe"
            ]
        ):

            severity_score = 85

    # --------------------------------------------------------
    # DRAINAGE
    # --------------------------------------------------------

    elif any(
        word in text
        for word in [
            "drain",
            "drainage",
            "waterlogging",
            "water logging",
            "flood",
            "sewer"
        ]
    ):

        ai_problem = "Drainage Problem"

        severity_score = 65

        if any(
            word in text
            for word in [
                "flood",
                "severe",
                "dangerous",
                "overflow",
                "blocked"
            ]
        ):

            severity_score = 90

    # --------------------------------------------------------
    # ELECTRICAL
    # --------------------------------------------------------

    elif any(
        word in text
        for word in [
            "electric",
            "electrical",
            "electricity",
            "street light",
            "streetlight",
            "light pole",
            "wire",
            "transformer",
            "pole"
        ]
    ):

        ai_problem = "Electrical Problem"

        severity_score = 70

        if any(
            word in text
            for word in [
                "spark",
                "fire",
                "shock",
                "broken wire",
                "dangerous",
                "live wire"
            ]
        ):

            severity_score = 95

    # --------------------------------------------------------
    # WATER
    # --------------------------------------------------------

    elif any(
        word in text
        for word in [
            "water supply",
            "water pipe",
            "pipeline",
            "pipe leakage",
            "water leak",
            "water leakage",
            "drinking water",
            "tap water"
        ]
    ):

        ai_problem = "Water Supply Problem"

        severity_score = 60

        if any(
            word in text
            for word in [
                "burst",
                "major leak",
                "contaminated",
                "dirty water"
            ]
        ):

            severity_score = 80

    # --------------------------------------------------------
    # PUBLIC STRUCTURE
    # --------------------------------------------------------

    elif any(
        word in text
        for word in [
            "building",
            "wall",
            "bridge",
            "public building",
            "collapse",
            "collapsed",
            "footpath",
            "footpath damage"
        ]
    ):

        ai_problem = "Public Structure Problem"

        severity_score = 70

        if any(
            word in text
            for word in [
                "collapse",
                "collapsed",
                "dangerous",
                "falling",
                "major crack"
            ]
        ):

            severity_score = 95

    # --------------------------------------------------------
    # GARBAGE / WASTE
    # --------------------------------------------------------

    elif any(
        word in text
        for word in [
            "garbage",
            "waste",
            "rubbish",
            "dustbin",
            "dump"
        ]
    ):

        ai_problem = "Waste Management Problem"

        severity_score = 45

    # --------------------------------------------------------
    # PRIORITY
    # --------------------------------------------------------

    if severity_score >= 90:

        priority = "Critical"

    elif severity_score >= 75:

        priority = "High"

    elif severity_score >= 50:

        priority = "Medium"

    else:

        priority = "Low"

    return (
        ai_problem,
        severity_score,
        priority
    )


# ============================================================
# ADMIN AUTHENTICATION
# ============================================================

def admin_required():

    return (
        session.get("admin_logged_in")
        is True
    )


def admin_login_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if not admin_required():

            return redirect(
                url_for("admin_login")
            )

        return function(
            *args,
            **kwargs
        )

    return decorated_function


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# REPORT COMPLAINT
# ============================================================

@app.route(
    "/report",
    methods=["GET", "POST"]
)
def report():

    if request.method == "GET":

        return render_template(
            "report.html"
        )

    # --------------------------------------------------------
    # FORM DATA
    # --------------------------------------------------------

    name = request.form.get(
        "name",
        ""
    ).strip()

    mobile = request.form.get(
        "mobile",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip()

    address = request.form.get(
        "address",
        ""
    ).strip()

    latitude = request.form.get(
        "latitude",
        ""
    ).strip()

    longitude = request.form.get(
        "longitude",
        ""
    ).strip()

    problem_type = request.form.get(
        "problem_type",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not name:

        flash(
            "Please enter your name.",
            "error"
        )

        return redirect(
            url_for("report")
        )

    if not mobile:

        flash(
            "Please enter your mobile number.",
            "error"
        )

        return redirect(
            url_for("report")
        )

    if not problem_type:

        flash(
            "Please select a problem type.",
            "error"
        )

        return redirect(
            url_for("report")
        )

    if not description:

        flash(
            "Please enter problem description.",
            "error"
        )

        return redirect(
            url_for("report")
        )

    # --------------------------------------------------------
    # FILES
    # --------------------------------------------------------

    photo = None
    video = None

    photo_file = request.files.get(
        "photo"
    )

    video_file = request.files.get(
        "video"
    )

    if photo_file and photo_file.filename:

        photo = save_uploaded_file(
            photo_file
        )

    if video_file and video_file.filename:

        video = save_uploaded_file(
            video_file
        )

    # --------------------------------------------------------
    # AI ANALYSIS
    # --------------------------------------------------------

    (
        ai_problem,
        severity_score,
        priority
    ) = analyze_complaint(
        problem_type,
        description
    )

    # --------------------------------------------------------
    # COMPLAINT ID
    # --------------------------------------------------------

    complaint_id = (
        "CR-"
        + datetime.now().strftime("%Y%m%d")
        + "-"
        + uuid.uuid4().hex[:6].upper()
    )

    created_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    conn = get_db()

    try:

        conn.execute(
            """
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

                ai_problem,
                severity_score,
                priority,

                created_at

            )

            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
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

                "Submitted",

                "Not Assigned",
                "Not Assigned",
                "Not Assigned",

                ai_problem,
                severity_score,
                priority,

                created_at
            )
        )

        conn.commit()

    except sqlite3.Error as error:

        conn.rollback()

        print(
            "Database Error:",
            error
        )

        flash(
            "Could not save complaint.",
            "error"
        )

        conn.close()

        return redirect(
            url_for("report")
        )

    conn.close()

    return render_template(
        "success.html",
        complaint_id=complaint_id
    )


# ============================================================
# TRACK COMPLAINT
# ============================================================

@app.route(
    "/track",
    methods=["GET", "POST"]
)
def track():

    complaint = None
    searched = False

    if request.method == "POST":

        searched = True

        complaint_id = request.form.get(
            "complaint_id",
            ""
        ).strip()

        if complaint_id:

            conn = get_db()

            complaint = conn.execute(
                """
                SELECT *
                FROM complaints
                WHERE complaint_id = ?
                """,
                (complaint_id,)
            ).fetchone()

            conn.close()

    return render_template(
        "track.html",
        complaint=complaint,
        searched=searched
    )


# ============================================================
# TRACK BY COMPLAINT ID
# Example:
# /track/CR-20260903-ABC123
# ============================================================

@app.route(
    "/track/<complaint_id>"
)
def track_by_id(complaint_id):

    conn = get_db()

    complaint = conn.execute(
        """
        SELECT *
        FROM complaints
        WHERE complaint_id = ?
        """,
        (complaint_id,)
    ).fetchone()

    conn.close()

    return render_template(
        "track.html",
        complaint=complaint,
        searched=True
    )


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if admin_required():

        return redirect(
            url_for("admin_dashboard")
        )

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if admin_required():

        return redirect(
            url_for("admin_dashboard")
        )

    if request.method == "POST":

        # ----------------------------------------------------
        # LOGIN FORM
        # ----------------------------------------------------

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        ).strip()

        access_key = request.form.get(
            "access_key",
            ""
        ).strip()

        # ----------------------------------------------------
        # ADMIN CREDENTIALS
        #
        # Render Environment Variables:
        #
        # ADMIN_EMAIL
        # ADMIN_PASSWORD
        # ADMIN_ACCESS_KEY
        # ----------------------------------------------------

        admin_email = os.environ.get(
            "ADMIN_EMAIL",
            "admin@civicreport.com"
        ).strip().lower()

        admin_password = os.environ.get(
            "ADMIN_PASSWORD",
            "admin123"
        ).strip()

        admin_access_key = os.environ.get(
            "ADMIN_ACCESS_KEY",
            "ADM-2030"
        ).strip()

        # ----------------------------------------------------
        # CHECK LOGIN
        # ----------------------------------------------------

        if (
            email == admin_email
            and
            password == admin_password
            and
            access_key == admin_access_key
        ):

            session.clear()

            session["admin_logged_in"] = True
            session["admin_email"] = email
            session["admin_role"] = "Admin"

            return redirect(
                url_for("admin_dashboard")
            )

        # ----------------------------------------------------
        # INVALID LOGIN
        # ----------------------------------------------------

        flash(
            "Invalid admin credentials.",
            "error"
        )

    return render_template(
        "admin_login.html"
    )


# ============================================================
# ADMIN LOGIN ALIASES
# ============================================================

@app.route(
    "/admin-login",
    methods=["GET", "POST"]
)
def admin_login_alias():

    return admin_login()


@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login_alias():

    return admin_login()


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin/dashboard")
@app.route("/admin")
@app.route("/admin_dashboard")
@admin_login_required
def admin_dashboard():

    conn = get_db()

    # --------------------------------------------------------
    # ALL COMPLAINTS
    # --------------------------------------------------------

    complaints = conn.execute(
        """
        SELECT *
        FROM complaints
        ORDER BY id DESC
        """
    ).fetchall()

    # --------------------------------------------------------
    # OFFICERS
    # --------------------------------------------------------

    officers = conn.execute(
        """
        SELECT *
        FROM officers
        ORDER BY id DESC
        """
    ).fetchall()

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    total_complaints = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        """
    ).fetchone()[0]

    submitted_complaints = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Submitted'
        """
    ).fetchone()[0]

    pending_complaints = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Pending'
        """
    ).fetchone()[0]

    in_progress_complaints = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'In Progress'
        """
    ).fetchone()[0]

    resolved_complaints = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Resolved'
        """
    ).fetchone()[0]

    # --------------------------------------------------------
    # NEW COMPLAINTS
    # --------------------------------------------------------

    new_complaints = conn.execute(
        """
        SELECT *
        FROM complaints
        WHERE status = 'Submitted'
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",

        complaints=complaints,

        officers=officers,

        total_complaints=total_complaints,

        submitted_complaints=submitted_complaints,

        pending_complaints=pending_complaints,

        in_progress_complaints=in_progress_complaints,

        resolved_complaints=resolved_complaints,

        new_complaints=new_complaints
    )


# ============================================================
# ASSIGN COMPLAINT
# ============================================================

@app.route(
    "/admin/assign/<int:complaint_id>",
    methods=["POST"]
)
@app.route(
    "/assign_complaint/<int:complaint_id>",
    methods=["POST"]
)
@admin_login_required
def assign_complaint(complaint_id):

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

    # --------------------------------------------------------
    # CHECK COMPLAINT
    # --------------------------------------------------------

    conn = get_db()

    complaint = conn.execute(
        """
        SELECT *
        FROM complaints
        WHERE id = ?
        """,
        (complaint_id,)
    ).fetchone()

    if not complaint:

        conn.close()

        flash(
            "Complaint not found.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    # --------------------------------------------------------
    # CHECK OFFICER
    # --------------------------------------------------------

    if officer != "Not Assigned":

        selected_officer = conn.execute(
            """
            SELECT *
            FROM officers
            WHERE name = ?
            LIMIT 1
            """,
            (officer,)
        ).fetchone()

        if selected_officer:

            if department in [
                "",
                "Not Assigned"
            ]:

                department = selected_officer[
                    "department"
                ]

            if branch in [
                "",
                "Not Assigned"
            ]:

                branch = selected_officer[
                    "branch"
                ]

        else:

            officer = "Not Assigned"

    # --------------------------------------------------------
    # AUTO STATUS
    # --------------------------------------------------------

    # If officer is assigned but status was still Submitted,
    # move complaint to Pending.

    if (
        officer != "Not Assigned"
        and
        status == "Submitted"
    ):

        status = "Pending"

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------

    conn.execute(
        """
        UPDATE complaints

        SET
            department = ?,
            branch = ?,
            officer = ?,
            status = ?

        WHERE id = ?
        """,
        (
            department,
            branch,
            officer,
            status,
            complaint_id
        )
    )

    conn.commit()
    conn.close()

    flash(
        "Complaint updated successfully.",
        "success"
    )

    return redirect(
        url_for("admin_dashboard")
    )


# ============================================================
# OFFICER MANAGEMENT
# ============================================================

@app.route("/admin/officers")
@app.route("/officer_management")
@admin_login_required
def officer_management():

    conn = get_db()

    officers = conn.execute(
        """
        SELECT *
        FROM officers
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    # --------------------------------------------------------
    # Normal template
    # --------------------------------------------------------

    template_path = os.path.join(
        BASE_DIR,
        "templates",
        "officer_management.html"
    )

    if os.path.exists(template_path):

        return render_template(
            "officer_management.html",
            officers=officers
        )

    # --------------------------------------------------------
    # FALLBACK PAGE
    # If officer_management.html does not exist
    # --------------------------------------------------------

    return render_template_string(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Officer Management - CivicReport</title>

            <meta name="viewport"
                  content="width=device-width, initial-scale=1">

            <style>

                body {
                    font-family: Arial, sans-serif;
                    background: #f4f7fb;
                    margin: 0;
                    padding: 30px;
                }

                .container {
                    max-width: 1100px;
                    margin: auto;
                }

                .top {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 25px;
                }

                .card {
                    background: white;
                    padding: 25px;
                    border-radius: 12px;
                    margin-bottom: 25px;
                    box-shadow:
                        0 4px 15px rgba(0,0,0,.08);
                }

                input,
                select {
                    width: 100%;
                    padding: 12px;
                    margin-top: 6px;
                    margin-bottom: 15px;
                    box-sizing: border-box;
                    border: 1px solid #ddd;
                    border-radius: 7px;
                }

                button,
                .btn {
                    background: #2563eb;
                    color: white;
                    padding: 11px 18px;
                    border: 0;
                    border-radius: 7px;
                    cursor: pointer;
                    text-decoration: none;
                }

                .delete {
                    background: #dc2626;
                }

                table {
                    width: 100%;
                    border-collapse: collapse;
                }

                th,
                td {
                    padding: 12px;
                    border-bottom: 1px solid #eee;
                    text-align: left;
                }

            </style>
        </head>

        <body>

        <div class="container">

            <div class="top">

                <h1>Officer Management</h1>

                <a class="btn"
                   href="{{ url_for('admin_dashboard') }}">
                    Dashboard
                </a>

            </div>

            <div class="card">

                <h2>Add Officer</h2>

                <form method="POST"
                      action="{{ url_for('add_officer') }}">

                    <label>Name</label>
                    <input name="name"
                           required>

                    <label>Department</label>
                    <input name="department"
                           required>

                    <label>Branch</label>
                    <input name="branch"
                           required>

                    <label>Mobile</label>
                    <input name="mobile"
                           required>

                    <label>Status</label>

                    <select name="status">

                        <option value="Active">
                            Active
                        </option>

                        <option value="Inactive">
                            Inactive
                        </option>

                    </select>

                    <button type="submit">
                        Add Officer
                    </button>

                </form>

            </div>

            <div class="card">

                <h2>Officers</h2>

                <table>

                    <tr>
                        <th>Name</th>
                        <th>Department</th>
                        <th>Branch</th>
                        <th>Mobile</th>
                        <th>Status</th>
                        <th>Action</th>
                    </tr>

                    {% for officer in officers %}

                    <tr>

                        <td>
                            {{ officer["name"] }}
                        </td>

                        <td>
                            {{ officer["department"] }}
                        </td>

                        <td>
                            {{ officer["branch"] }}
                        </td>

                        <td>
                            {{ officer["mobile"] }}
                        </td>

                        <td>
                            {{ officer["status"] }}
                        </td>

                        <td>

                            <a class="btn delete"
                               href="{{ url_for(
                                   'delete_officer',
                                   officer_id=officer['id']
                               ) }}"
                               onclick="return confirm(
                                   'Delete this officer?'
                               );">
                                Delete
                            </a>

                        </td>

                    </tr>

                    {% else %}

                    <tr>
                        <td colspan="6">
                            No officers found.
                        </td>
                    </tr>

                    {% endfor %}

                </table>

            </div>

        </div>

        </body>
        </html>
        """,
        officers=officers
    )


# ============================================================
# ADD OFFICER
# ============================================================

@app.route(
    "/admin/officer/add",
    methods=["GET", "POST"]
)
@app.route(
    "/add_officer",
    methods=["GET", "POST"]
)
@admin_login_required
def add_officer():

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

        status = request.form.get(
            "status",
            "Active"
        ).strip()

        if status not in [
            "Active",
            "Inactive"
        ]:

            status = "Active"

        if not name:

            flash(
                "Officer name is required.",
                "error"
            )

            return redirect(
                url_for("add_officer")
            )

        if not department:

            flash(
                "Department is required.",
                "error"
            )

            return redirect(
                url_for("add_officer")
            )

        if not branch:

            flash(
                "Branch is required.",
                "error"
            )

            return redirect(
                url_for("add_officer")
            )

        if not mobile:

            flash(
                "Mobile number is required.",
                "error"
            )

            return redirect(
                url_for("add_officer")
            )

        conn = get_db()

        conn.execute(
            """
            INSERT INTO officers (
                name,
                department,
                branch,
                mobile,
                status
            )

            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                department,
                branch,
                mobile,
                status
            )
        )

        conn.commit()
        conn.close()

        flash(
            "Officer added successfully.",
            "success"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    # --------------------------------------------------------
    # Normal template
    # --------------------------------------------------------

    template_path = os.path.join(
        BASE_DIR,
        "templates",
        "add_officer.html"
    )

    if os.path.exists(template_path):

        return render_template(
            "add_officer.html"
        )

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    return render_template_string(
        """
        <!DOCTYPE html>

        <html>

        <head>

            <title>Add Officer</title>

            <meta name="viewport"
                  content="width=device-width, initial-scale=1">

            <style>

                body {
                    font-family: Arial;
                    background: #f4f7fb;
                    padding: 30px;
                }

                .card {
                    max-width: 600px;
                    margin: auto;
                    background: white;
                    padding: 25px;
                    border-radius: 12px;
                }

                input,
                select {
                    width: 100%;
                    padding: 12px;
                    margin: 8px 0 15px;
                    box-sizing: border-box;
                }

                button,
                a {
                    background: #2563eb;
                    color: white;
                    border: 0;
                    padding: 12px 18px;
                    border-radius: 6px;
                    text-decoration: none;
                }

            </style>

        </head>

        <body>

            <div class="card">

                <h1>Add Officer</h1>

                <form method="POST">

                    <label>Name</label>

                    <input name="name"
                           required>

                    <label>Department</label>

                    <input name="department"
                           required>

                    <label>Branch</label>

                    <input name="branch"
                           required>

                    <label>Mobile</label>

                    <input name="mobile"
                           required>

                    <label>Status</label>

                    <select name="status">

                        <option value="Active">
                            Active
                        </option>

                        <option value="Inactive">
                            Inactive
                        </option>

                    </select>

                    <button type="submit">
                        Add Officer
                    </button>

                    <a href="{{ url_for('admin_dashboard') }}">
                        Dashboard
                    </a>

                </form>

            </div>

        </body>

        </html>
        """
    )


# ============================================================
# DELETE OFFICER
# ============================================================

@app.route(
    "/admin/officer/delete/<int:officer_id>"
)
@app.route(
    "/delete_officer/<int:officer_id>"
)
@admin_login_required
def delete_officer(officer_id):

    conn = get_db()

    officer = conn.execute(
        """
        SELECT *
        FROM officers
        WHERE id = ?
        """,
        (officer_id,)
    ).fetchone()

    if not officer:

        conn.close()

        flash(
            "Officer not found.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    # --------------------------------------------------------
    # Unassign officer
    # --------------------------------------------------------

    conn.execute(
        """
        UPDATE complaints

        SET
            officer = 'Not Assigned',
            department = 'Not Assigned',
            branch = 'Not Assigned',
            status = CASE
                WHEN status = 'Resolved'
                THEN status
                ELSE 'Submitted'
            END

        WHERE officer = ?
        """,
        (officer["name"],)
    )

    # --------------------------------------------------------
    # Delete officer
    # --------------------------------------------------------

    conn.execute(
        """
        DELETE FROM officers
        WHERE id = ?
        """,
        (officer_id,)
    )

    conn.commit()
    conn.close()

    flash(
        "Officer deleted successfully.",
        "success"
    )

    return redirect(
        url_for("admin_dashboard")
    )


# ============================================================
# OFFICER DASHBOARD
# ============================================================

@app.route(
    "/officer/<int:officer_id>"
)
@app.route(
    "/officer_dashboard/<int:officer_id>"
)
@admin_login_required
def officer_dashboard(officer_id):

    conn = get_db()

    # --------------------------------------------------------
    # OFFICER
    # --------------------------------------------------------

    officer = conn.execute(
        """
        SELECT *
        FROM officers
        WHERE id = ?
        """,
        (officer_id,)
    ).fetchone()

    if not officer:

        conn.close()

        flash(
            "Officer not found.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    # --------------------------------------------------------
    # ASSIGNED COMPLAINTS
    # --------------------------------------------------------

    complaints = conn.execute(
        """
        SELECT *
        FROM complaints

        WHERE officer = ?

        ORDER BY id DESC
        """,
        (officer["name"],)
    ).fetchall()

    # --------------------------------------------------------
    # STATS
    # --------------------------------------------------------

    total_assigned = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE officer = ?
        """,
        (officer["name"],)
    ).fetchone()[0]

    submitted = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE officer = ?
        AND status = 'Submitted'
        """,
        (officer["name"],)
    ).fetchone()[0]

    pending = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE officer = ?
        AND status = 'Pending'
        """,
        (officer["name"],)
    ).fetchone()[0]

    in_progress = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE officer = ?
        AND status = 'In Progress'
        """,
        (officer["name"],)
    ).fetchone()[0]

    resolved = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE officer = ?
        AND status = 'Resolved'
        """,
        (officer["name"],)
    ).fetchone()[0]

    conn.close()

    # --------------------------------------------------------
    # Normal template
    # --------------------------------------------------------

    template_path = os.path.join(
        BASE_DIR,
        "templates",
        "officer_dashboard.html"
    )

    if os.path.exists(template_path):

        return render_template(
            "officer_dashboard.html",

            officer=officer,

            complaints=complaints,

            total_assigned=total_assigned,

            submitted=submitted,

            pending=pending,

            in_progress=in_progress,

            resolved=resolved
        )

    # --------------------------------------------------------
    # FALLBACK OFFICER DASHBOARD
    # --------------------------------------------------------

    return render_template_string(
        """
        <!DOCTYPE html>

        <html>

        <head>

            <title>Officer Dashboard - CivicReport</title>

            <meta name="viewport"
                  content="width=device-width, initial-scale=1">

            <style>

                body {
                    margin: 0;
                    font-family: Arial, sans-serif;
                    background: #f4f7fb;
                }

                header {
                    background: #172554;
                    color: white;
                    padding: 20px;
                }

                .container {
                    max-width: 1300px;
                    margin: auto;
                    padding: 25px;
                }

                .profile {
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                }

                .stats {
                    display: grid;
                    grid-template-columns:
                        repeat(auto-fit, minmax(150px, 1fr));
                    gap: 15px;
                    margin-bottom: 20px;
                }

                .stat {
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    text-align: center;
                }

                .stat h2 {
                    margin: 0;
                    font-size: 30px;
                }

                .table-card {
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    overflow-x: auto;
                }

                table {
                    width: 100%;
                    border-collapse: collapse;
                    min-width: 900px;
                }

                th,
                td {
                    padding: 12px;
                    border-bottom: 1px solid #eee;
                    text-align: left;
                }

                select,
                button {
                    padding: 9px;
                }

                button {
                    background: #2563eb;
                    color: white;
                    border: 0;
                    border-radius: 6px;
                    cursor: pointer;
                }

                .back {
                    color: white;
                    text-decoration: none;
                }

            </style>

        </head>

        <body>

            <header>

                <div class="container">

                    <h1>
                        Officer Dashboard
                    </h1>

                    <a class="back"
                       href="{{ url_for('admin_dashboard') }}">
                        ← Back to Admin Dashboard
                    </a>

                </div>

            </header>

            <div class="container">

                <div class="profile">

                    <h2>
                        Welcome,
                        {{ officer["name"] }}
                    </h2>

                    <p>
                        <strong>Department:</strong>
                        {{ officer["department"] }}
                    </p>

                    <p>
                        <strong>Branch:</strong>
                        {{ officer["branch"] }}
                    </p>

                    <p>
                        <strong>Mobile:</strong>
                        {{ officer["mobile"] }}
                    </p>

                    <p>
                        <strong>Status:</strong>
                        {{ officer["status"] }}
                    </p>

                </div>

                <div class="stats">

                    <div class="stat">
                        <h2>{{ total_assigned }}</h2>
                        <p>Total Assigned</p>
                    </div>

                    <div class="stat">
                        <h2>{{ submitted }}</h2>
                        <p>Submitted</p>
                    </div>

                    <div class="stat">
                        <h2>{{ pending }}</h2>
                        <p>Pending</p>
                    </div>

                    <div class="stat">
                        <h2>{{ in_progress }}</h2>
                        <p>In Progress</p>
                    </div>

                    <div class="stat">
                        <h2>{{ resolved }}</h2>
                        <p>Resolved</p>
                    </div>

                </div>

                <div class="table-card">

                    <h2>
                        Assigned Complaints
                    </h2>

                    <table>

                        <tr>

                            <th>Complaint ID</th>
                            <th>Citizen</th>
                            <th>Problem</th>
                            <th>Location</th>
                            <th>Priority</th>
                            <th>Status</th>
                            <th>Update</th>

                        </tr>

                        {% for complaint in complaints %}

                        <tr>

                            <td>
                                {{ complaint["complaint_id"] }}
                            </td>

                            <td>
                                {{ complaint["name"] }}
                            </td>

                            <td>
                                {{ complaint["ai_problem"] or complaint["problem_type"] }}
                            </td>

                            <td>
                                {{ complaint["address"] }}
                            </td>

                            <td>
                                {{ complaint["priority"] }}
                            </td>

                            <td>
                                {{ complaint["status"] }}
                            </td>

                            <td>

                                <form method="POST"
                                      action="{{ url_for(
                                        'officer_update_complaint',
                                        officer_id=officer['id'],
                                        complaint_id=complaint['id']
                                      ) }}">

                                    <select name="status">

                                        <option value="Submitted"
                                            {% if complaint["status"] == "Submitted" %}
                                                selected
                                            {% endif %}>
                                            Submitted
                                        </option>

                                        <option value="Pending"
                                            {% if complaint["status"] == "Pending" %}
                                                selected
                                            {% endif %}>
                                            Pending
                                        </option>

                                        <option value="In Progress"
                                            {% if complaint["status"] == "In Progress" %}
                                                selected
                                            {% endif %}>
                                            In Progress
                                        </option>

                                        <option value="Resolved"
                                            {% if complaint["status"] == "Resolved" %}
                                                selected
                                            {% endif %}>
                                            Resolved
                                        </option>

                                    </select>

                                    <button type="submit">
                                        Update
                                    </button>

                                </form>

                            </td>

                        </tr>

                        {% else %}

                        <tr>

                            <td colspan="7">
                                No complaints assigned.
                            </td>

                        </tr>

                        {% endfor %}

                    </table>

                </div>

            </div>

        </body>

        </html>
        """,

        officer=officer,

        complaints=complaints,

        total_assigned=total_assigned,

        submitted=submitted,

        pending=pending,

        in_progress=in_progress,

        resolved=resolved
    )


# ============================================================
# OFFICER UPDATE COMPLAINT
# ============================================================

@app.route(
    "/officer/<int:officer_id>/complaint/<int:complaint_id>/update",
    methods=["POST"]
)
@admin_login_required
def officer_update_complaint(
    officer_id,
    complaint_id
):

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

        flash(
            "Invalid status.",
            "error"
        )

        return redirect(
            url_for(
                "officer_dashboard",
                officer_id=officer_id
            )
        )

    conn = get_db()

    # --------------------------------------------------------
    # OFFICER
    # --------------------------------------------------------

    officer = conn.execute(
        """
        SELECT *
        FROM officers
        WHERE id = ?
        """,
        (officer_id,)
    ).fetchone()

    if not officer:

        conn.close()

        flash(
            "Officer not found.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    # --------------------------------------------------------
    # CHECK COMPLAINT ASSIGNMENT
    # --------------------------------------------------------

    complaint = conn.execute(
        """
        SELECT *
        FROM complaints

        WHERE id = ?
        AND officer = ?
        """,
        (
            complaint_id,
            officer["name"]
        )
    ).fetchone()

    if not complaint:

        conn.close()

        flash(
            "Complaint is not assigned to this officer.",
            "error"
        )

        return redirect(
            url_for(
                "officer_dashboard",
                officer_id=officer_id
            )
        )

    # --------------------------------------------------------
    # UPDATE STATUS
    # --------------------------------------------------------

    conn.execute(
        """
        UPDATE complaints

        SET status = ?

        WHERE id = ?
        """,
        (
            status,
            complaint_id
        )
    )

    conn.commit()
    conn.close()

    flash(
        "Complaint status updated.",
        "success"
    )

    return redirect(
        url_for(
            "officer_dashboard",
            officer_id=officer_id
        )
    )


# ============================================================
# UPLOADED FILE
# ============================================================

@app.route(
    "/uploads/<path:filename>"
)
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok",
        "application": "CivicReport"
    })


# ============================================================
# API - COMPLAINT COUNT
# Useful for dashboard notification polling
# ============================================================

@app.route(
    "/api/complaint-stats"
)
@admin_login_required
def complaint_stats():

    conn = get_db()

    total = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        """
    ).fetchone()[0]

    submitted = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Submitted'
        """
    ).fetchone()[0]

    pending = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Pending'
        """
    ).fetchone()[0]

    in_progress = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'In Progress'
        """
    ).fetchone()[0]

    resolved = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Resolved'
        """
    ).fetchone()[0]

    conn.close()

    return jsonify({

        "total": total,

        "submitted": submitted,

        "pending": pending,

        "in_progress": in_progress,

        "resolved": resolved

    })


# ============================================================
# ERROR - FILE TOO LARGE
# ============================================================

@app.errorhandler(413)
def too_large(error):

    flash(
        "Uploaded file is too large. Maximum size is 100 MB.",
        "error"
    )

    return redirect(
        url_for("report")
    )


# ============================================================
# ERROR - 404
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return """
    <!DOCTYPE html>

    <html>

    <head>

        <title>404 - CivicReport</title>

        <meta name="viewport"
              content="width=device-width, initial-scale=1">

        <style>

            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 60px;
                background: #f4f7fb;
            }

            .box {
                max-width: 600px;
                margin: auto;
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow:
                    0 5px 20px rgba(0,0,0,.08);
            }

            h1 {
                font-size: 60px;
                margin: 0;
                color: #172554;
            }

            h2 {
                color: #334155;
            }

            a {
                display: inline-block;
                margin-top: 15px;
                background: #2563eb;
                color: white;
                padding: 12px 20px;
                text-decoration: none;
                border-radius: 7px;
            }

        </style>

    </head>

    <body>

        <div class="box">

            <h1>404</h1>

            <h2>Page Not Found</h2>

            <p>
                The requested CivicReport page
                does not exist.
            </p>

            <a href="/">
                Go Home
            </a>

        </div>

    </body>

    </html>
    """, 404


# ============================================================
# ERROR - 500
# ============================================================

@app.errorhandler(500)
def internal_server_error(error):

    return """
    <!DOCTYPE html>

    <html>

    <head>

        <title>500 - CivicReport</title>

        <meta name="viewport"
              content="width=device-width, initial-scale=1">

        <style>

            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 60px;
                background: #f4f7fb;
            }

            .box {
                max-width: 600px;
                margin: auto;
                background: white;
                padding: 40px;
                border-radius: 15px;
            }

        </style>

    </head>

    <body>

        <div class="box">

            <h1>500</h1>

            <h2>Internal Server Error</h2>

            <p>
                Something went wrong on the server.
            </p>

            <a href="/">
                Go Home
            </a>

        </div>

    </body>

    </html>
    """, 500


# ============================================================
# START APPLICATION
# ============================================================

# Initialize database when Flask starts.
init_db()


if __name__ == "__main__":

    print("")
    print("==============================================")
    print("          CIVICREPORT SERVER")
    print("==============================================")
    print("")

    print("Database :")
    print(DATABASE)

    print("")

    print("Uploads :")
    print(UPLOAD_FOLDER)

    print("")

    print("Admin Login")
    print("----------------------------")
    print("Username : admin")
    print("Password : admin123")
    print("----------------------------")

    print("")

    print("Local URL:")
    print("http://127.0.0.1:5000")

    print("")

    print("Admin:")
    print("http://127.0.0.1:5000/admin/login")

    print("")

    print("==============================================")
    print("")

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
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

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE = os.path.join(
    BASE_DIR,
    "database.db"
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# DATABASE INITIALIZATION
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

            created_at TEXT NOT NULL

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
    # DATABASE MIGRATION
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


    # -----------------------------------------------------
    # UPDATE EMPTY CREATED DATE
    # -----------------------------------------------------

    conn.execute("""
        UPDATE officers
        SET created_at = ?
        WHERE created_at IS NULL
    """, (
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    ))


    conn.commit()

    conn.close()


# =========================================================
# PUBLIC HOME PAGE
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# PUBLIC REPORT COMPLAINT
# =========================================================

@app.route(
    "/report",
    methods=["GET", "POST"]
)
def report():

    if request.method == "POST":

        # -------------------------------------------------
        # CITIZEN INFORMATION
        # -------------------------------------------------

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


        # -------------------------------------------------
        # LOCATION
        # -------------------------------------------------

        location = request.form.get(
            "location",
            ""
        ).strip()

        latitude = ""

        longitude = ""

        if "," in location:

            latitude, longitude = [
                value.strip()
                for value in location.split(
                    ",",
                    1
                )
            ]


        # -------------------------------------------------
        # PROBLEM DETAILS
        # -------------------------------------------------

        problem_type = request.form.get(
            "problem_type",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()


        # -------------------------------------------------
        # FILE UPLOAD
        # -------------------------------------------------

        photo_file = request.files.get(
            "photo"
        )

        video_file = request.files.get(
            "video"
        )

        photo_name = ""

        video_name = ""


        # -------------------------------------------------
        # SAVE PHOTO
        # -------------------------------------------------

        if (
            photo_file
            and photo_file.filename
        ):

            extension = os.path.splitext(
                photo_file.filename
            )[1]

            photo_name = (
                uuid.uuid4().hex
                + extension
            )

            photo_file.save(
                os.path.join(
                    UPLOAD_FOLDER,
                    photo_name
                )
            )


        # -------------------------------------------------
        # SAVE VIDEO
        # -------------------------------------------------

        if (
            video_file
            and video_file.filename
        ):

            extension = os.path.splitext(
                video_file.filename
            )[1]

            video_name = (
                uuid.uuid4().hex
                + extension
            )

            video_file.save(
                os.path.join(
                    UPLOAD_FOLDER,
                    video_name
                )
            )


        # -------------------------------------------------
        # GENERATE COMPLAINT ID
        # -------------------------------------------------

        complaint_id = (
            "CIVIC-"
            + datetime.now().strftime("%Y")
            + "-"
            + uuid.uuid4().hex[:6].upper()
        )


        # -------------------------------------------------
        # CREATED DATE
        # -------------------------------------------------

        created_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )


        # -------------------------------------------------
        # SAVE COMPLAINT
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
                created_at

            )

            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?
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
            photo_name,
            video_name,
            "Submitted",
            "Not Assigned",
            "Not Assigned",
            "Not Assigned",
            created_at

        ))


        conn.commit()

        conn.close()


        return render_template(
            "success.html",
            complaint_id=complaint_id
        )


    return render_template(
        "report.html"
    )


# =========================================================
# PUBLIC COMPLAINT TRACKING
# =========================================================

@app.route(
    "/track",
    methods=["GET", "POST"]
)
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


        if complaint is None:

            error = (
                "Complaint ID not found."
            )


    return render_template(
        "track.html",
        complaint=complaint,
        error=error
    )


# =========================================================
# SERVE UPLOADED FILES
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
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    error = None


    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )


        if (
            username == "admin"
            and password == "Admin@123"
        ):

            session[
                "admin_logged_in"
            ] = True


            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )


        error = (
            "Invalid username or password."
        )


    return render_template(
        "admin_login.html",
        error=error
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
        url_for(
            "admin_login"
        )
    )


# =========================================================
# ADMIN LOGIN CHECK
# =========================================================

def admin_required():

    return session.get(
        "admin_logged_in"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
def admin_dashboard():

    if not admin_required():

        return redirect(
            url_for(
                "admin_login"
            )
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
    # STATISTICS
    # -----------------------------------------------------

    total_complaints = len(
        complaints
    )


    submitted_complaints = sum(
        1
        for c in complaints
        if c["status"] == "Submitted"
    )


    pending_complaints = sum(
        1
        for c in complaints
        if c["status"] == "Pending"
    )


    in_progress_complaints = sum(
        1
        for c in complaints
        if c["status"] == "In Progress"
    )


    resolved_complaints = sum(
        1
        for c in complaints
        if c["status"] == "Resolved"
    )


    # -----------------------------------------------------
    # NEW COMPLAINTS
    # -----------------------------------------------------

    new_complaints = [
        c
        for c in complaints
        if c["status"] == "Submitted"
    ]


    notification_count = len(
        new_complaints
    )


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

        new_complaints=new_complaints,

        notification_count=notification_count
    )


# =========================================================
# OFFICER MANAGEMENT
# =========================================================

@app.route(
    "/admin/officers"
)
def officer_management():

    if not admin_required():

        return redirect(
            url_for(
                "admin_login"
            )
        )


    conn = get_db()


    officers = conn.execute("""
        SELECT *
        FROM officers
        ORDER BY id DESC
    """).fetchall()


    conn.close()


    return render_template(
        "officer_management.html",
        officers=officers
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
            url_for(
                "admin_login"
            )
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

        status = request.form.get(
            "status",
            "Active"
        ).strip()


        if not status:

            status = "Active"


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

            VALUES (?, ?, ?, ?, ?, ?)
        """, (

            name,
            department,
            branch,
            mobile,
            status,
            created_at

        ))


        conn.commit()

        conn.close()


        return redirect(
            url_for(
                "officer_management"
            )
        )


    return render_template(
        "add_officer.html"
    )


# =========================================================
# DELETE OFFICER
# =========================================================

@app.route(
    "/admin/officers/delete/<int:officer_id>",
    methods=["GET", "POST"]
)
def delete_officer(officer_id):

    if not admin_required():

        return redirect(
            url_for(
                "admin_login"
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


    if officer is None:

        conn.close()

        return "Officer not found", 404


    # -----------------------------------------------------
    # UNASSIGN OFFICER
    # -----------------------------------------------------

    conn.execute("""
        UPDATE complaints

        SET
            officer = 'Not Assigned',
            department = 'Not Assigned',
            branch = 'Not Assigned'

        WHERE officer = ?
    """, (
        officer["name"],
    ))


    # -----------------------------------------------------
    # DELETE OFFICER
    # -----------------------------------------------------

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
            "officer_management"
        )
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
            url_for(
                "admin_login"
            )
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


    status = request.form.get(
        "status",
        "Pending"
    ).strip()


    allowed_statuses = [
        "Submitted",
        "Pending",
        "In Progress",
        "Resolved"
    ]


    if status not in allowed_statuses:

        status = "Pending"


    conn = get_db()


    # -----------------------------------------------------
    # IF OFFICER SELECTED
    # AUTOMATICALLY GET DEPARTMENT AND BRANCH
    # -----------------------------------------------------

    if officer != "Not Assigned":

        selected_officer = conn.execute("""
            SELECT *
            FROM officers
            WHERE name = ?
            ORDER BY id DESC
            LIMIT 1
        """, (
            officer,
        )).fetchone()


        if selected_officer is not None:

            department = selected_officer[
                "department"
            ]

            branch = selected_officer[
                "branch"
            ]


    # -----------------------------------------------------
    # UPDATE COMPLAINT
    # -----------------------------------------------------

    conn.execute("""
        UPDATE complaints

        SET
            department = ?,
            branch = ?,
            officer = ?,
            status = ?

        WHERE id = ?
    """, (

        department,
        branch,
        officer,
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
# ADMIN UPDATE COMPLAINT
# =========================================================

@app.route(
    "/admin/complaint/<int:complaint_id>/update",
    methods=["POST"]
)
def admin_update_complaint(
    complaint_id
):

    if not admin_required():

        return redirect(
            url_for(
                "admin_login"
            )
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

        return "Invalid status", 400


    conn = get_db()


    # -----------------------------------------------------
    # IF OFFICER SELECTED
    # GET DEPARTMENT AND BRANCH
    # -----------------------------------------------------

    if officer != "Not Assigned":

        selected_officer = conn.execute("""
            SELECT *
            FROM officers
            WHERE name = ?
            ORDER BY id DESC
            LIMIT 1
        """, (
            officer,
        )).fetchone()


        if selected_officer is not None:

            department = selected_officer[
                "department"
            ]

            branch = selected_officer[
                "branch"
            ]


    # -----------------------------------------------------
    # UPDATE
    # -----------------------------------------------------

    conn.execute("""
        UPDATE complaints

        SET
            department = ?,
            branch = ?,
            officer = ?,
            status = ?

        WHERE id = ?
    """, (

        department,
        branch,
        officer,
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
# ADMIN STATUS ONLY UPDATE
# =========================================================

@app.route(
    "/admin/complaint/<int:complaint_id>/status",
    methods=["POST"]
)
def admin_update_status(
    complaint_id
):

    if not admin_required():

        return redirect(
            url_for(
                "admin_login"
            )
        )


    status = request.form.get(
        "status",
        ""
    ).strip()


    allowed_statuses = [
        "Submitted",
        "Pending",
        "In Progress",
        "Resolved"
    ]


    if status not in allowed_statuses:

        return "Invalid status", 400


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

    error = None


    if request.method == "POST":

        officer_id = request.form.get(
            "officer_id",
            ""
        ).strip()


        mobile = request.form.get(
            "mobile",
            ""
        ).strip()


        if not officer_id or not mobile:

            error = (
                "Officer ID and Mobile Number "
                "are required."
            )


        else:

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

                session[
                    "officer_logged_in"
                ] = True


                session[
                    "officer_id"
                ] = officer["id"]


                return redirect(
                    url_for(
                        "officer_dashboard",
                        officer_id=officer["id"]
                    )
                )


            else:

                error = (
                    "Invalid Officer ID "
                    "or Mobile Number."
                )


    return render_template(
        "officer_login.html",
        error=error
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

    # -----------------------------------------------------
    # OFFICER LOGIN CHECK
    # -----------------------------------------------------

    if not session.get(
        "officer_logged_in"
    ):

        return redirect(
            url_for(
                "officer_login"
            )
        )


    # -----------------------------------------------------
    # OFFICER ACCESS CHECK
    # -----------------------------------------------------

    if session.get(
        "officer_id"
    ) != officer_id:

        return "Access denied", 403


    conn = get_db()


    # -----------------------------------------------------
    # FIND OFFICER
    # -----------------------------------------------------

    officer = conn.execute("""
        SELECT *
        FROM officers
        WHERE id = ?
    """, (
        officer_id,
    )).fetchone()


    if officer is None:

        conn.close()

        return "Officer not found", 404


    # -----------------------------------------------------
    # FIND ASSIGNED COMPLAINTS
    # -----------------------------------------------------

    complaints = conn.execute("""
        SELECT *
        FROM complaints
        WHERE officer = ?
        ORDER BY id DESC
    """, (
        officer["name"],
    )).fetchall()


    # -----------------------------------------------------
    # STATISTICS
    # -----------------------------------------------------

    total_assigned = len(
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

        total_assigned=total_assigned,

        submitted=submitted,

        pending=pending,

        in_progress=in_progress,

        resolved=resolved,

        success=None

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
    # OFFICER LOGIN CHECK
    # -----------------------------------------------------

    if not session.get(
        "officer_logged_in"
    ):

        return redirect(
            url_for(
                "officer_login"
            )
        )


    # -----------------------------------------------------
    # OFFICER ACCESS CHECK
    # -----------------------------------------------------

    if session.get(
        "officer_id"
    ) != officer_id:

        return "Access denied", 403


    # -----------------------------------------------------
    # NEW STATUS
    # -----------------------------------------------------

    new_status = request.form.get(
        "status",
        ""
    ).strip()


    allowed_statuses = [
        "Submitted",
        "Pending",
        "In Progress",
        "Resolved"
    ]


    if new_status not in allowed_statuses:

        return "Invalid status", 400


    conn = get_db()


    # -----------------------------------------------------
    # FIND OFFICER
    # -----------------------------------------------------

    officer = conn.execute("""
        SELECT *
        FROM officers
        WHERE id = ?
    """, (
        officer_id,
    )).fetchone()


    if officer is None:

        conn.close()

        return "Officer not found", 404


    # -----------------------------------------------------
    # CHECK COMPLAINT BELONGS TO OFFICER
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


    if complaint is None:

        conn.close()

        return (
            "Complaint is not assigned "
            "to this officer"
        ), 403


    # -----------------------------------------------------
    # UPDATE STATUS
    # -----------------------------------------------------

    conn.execute("""
        UPDATE complaints

        SET status = ?

        WHERE id = ?
        AND officer = ?

    """, (

        new_status,
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
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True
    )

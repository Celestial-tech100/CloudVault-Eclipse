import os
import sqlite3
import random
from datetime import datetime, timedelta

from flask import Flask, render_template
from flask import session, redirect, request, flash
from flask import send_from_directory
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = "cloudvault_eclipse_2026"

app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT"))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS") == "True"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")

mail = Mail(app)


def init_db():
    conn = sqlite3.connect("database/cloudvault.db")

    with open("database/schema.sql", "r") as f:
        conn.executescript(f.read())

    conn.commit()
    conn.close()
# init_db()


@app.route("/")
def home():
    return render_template("landing.html")

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database/cloudvault.db")
    cursor = conn.cursor()

    # Total Documents
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM documents
        WHERE user_id=?
        """,
        (session["user_id"],)
    )
    total_documents = cursor.fetchone()[0]

    # Total Categories
    cursor.execute(
        """
        SELECT COUNT(DISTINCT category)
        FROM documents
        WHERE user_id=?
        """,
        (session["user_id"],)
    )
    total_categories = cursor.fetchone()[0]

    # Total Storage Used
    cursor.execute(
        """
        SELECT SUM(file_size)
        FROM documents
        WHERE user_id=?
        """,
        (session["user_id"],)
    )

    total_storage = cursor.fetchone()[0]

    if total_storage is None:
        storage_used = "0 KB"
    elif total_storage < 1024 * 1024:
        storage_used = f"{round(total_storage / 1024, 2)} KB"
    else:
        storage_used = f"{round(total_storage / (1024 * 1024), 2)} MB"

    # Today's Uploads
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM documents
        WHERE user_id=?
        AND DATE(upload_date)=DATE('now')
        """,
        (session["user_id"],)
    )

    today_uploads = cursor.fetchone()[0]

    # Recent Uploads
    cursor.execute(
        """
        SELECT *
        FROM documents
        WHERE user_id=?
        ORDER BY upload_date DESC
        LIMIT 5
        """,
        (session["user_id"],)
    )

    recent_documents = cursor.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        total_documents=total_documents,
        total_categories=total_categories,
        storage_used=storage_used,
        today_uploads=today_uploads,
        recent_documents=recent_documents
    )

@app.route("/admin")
def admin():

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "admin":
        flash("Access denied.")
        return redirect("/dashboard")

    conn = sqlite3.connect("database/cloudvault.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM documents")
    total_documents = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(file_size) FROM documents")
    storage = cursor.fetchone()[0] or 0

    if storage < 1024 * 1024:
        storage_used = f"{round(storage/1024,2)} KB"
    else:
        storage_used = f"{round(storage/(1024*1024),2)} MB"

    cursor.execute("""
        SELECT COUNT(*)
        FROM documents
        WHERE DATE(upload_date)=DATE('now')
    """)

    today_uploads = cursor.fetchone()[0]

    cursor.execute("""
        SELECT id, full_name, email, role
        FROM users
        ORDER BY created_at DESC
    """)

    users = cursor.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        total_users=total_users,
        total_documents=total_documents,
        storage_used=storage_used,
        today_uploads=today_uploads,
        users=users
    )
    
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

import time
@app.route("/upload", methods=["GET", "POST"])
def upload():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        file = request.files["document"]
        category = request.form["category"]

        if file:

            filename = secure_filename(file.filename)

            stored_name = f"{int(time.time())}_{filename}"

            file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    stored_name
                )
            )

            file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

            conn = sqlite3.connect("database/cloudvault.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO documents
                (user_id,file_name,stored_name,file_type,file_size,category)
                VALUES(?,?,?,?,?,?)
                """,
                (
                    session["user_id"],
                    filename,
                    stored_name,
                    file.content_type,
                    os.path.getsize(
                        os.path.join(
                            app.config["UPLOAD_FOLDER"],
                            stored_name
                        )
                    ),
                    category
                )
            )

            conn.commit()
            conn.close()

            return redirect("/documents")

    return render_template("upload.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database/cloudvault.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, full_name, password, role
            FROM users
            WHERE email=?
            """,
            (email,)
        )

        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):

            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["user_email"] = email
            session["role"] = user[3]

            return redirect("/dashboard")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form["full_name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        conn = sqlite3.connect("database/cloudvault.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE email=?",
            (email,)
        )

        existing_user = cursor.fetchone()
        conn.close()

        if existing_user:
            flash("Email already registered. Please login.", "error")
            return redirect("/register")

        otp = str(random.randint(100000, 999999))

        session["pending_registration"] = {
            "full_name": full_name,
            "email": email,
            "password": password,
            "otp": otp,
            "expires_at": (
                datetime.now() + timedelta(minutes=5)
            ).strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            msg = Message(
                subject="CloudVault Eclipse - Email Verification",
                sender=app.config["MAIL_USERNAME"],
                recipients=[email]
            )

            msg.body = f"""
            Hello {full_name},

            Welcome to CloudVault Eclipse!

            Your verification code is:

            {otp}

            This code is valid for 5 minutes.

            If you did not create this account, please ignore this email.

            Regards,
            CloudVault Eclipse
            """

            mail.send(msg)

            flash("Verification code sent to your email.", "success")
            return redirect("/verify-otp")

        except Exception as e:
            flash(f"Unable to send email: {e}", "error")
            return redirect("/register")

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database/cloudvault.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT full_name, email, role, created_at
        FROM users
        WHERE id=?
    """, (session["user_id"],))

    user = cursor.fetchone()

    conn.close()

    return render_template(
        "profile.html",
        user=user
    )

@app.route("/documents")
def documents():

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database/cloudvault.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM documents
        WHERE user_id=?
        ORDER BY upload_date DESC
        """,
        (session["user_id"],)
    )

    docs = cursor.fetchall()

    conn.close()

    return render_template(
        "documents.html",
        documents=docs
    )

@app.route("/download-document/<int:id>")
def download_document(id):

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database/cloudvault.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT stored_name, file_name
        FROM documents
        WHERE id=? AND user_id=?
        """,
        (id, session["user_id"])
    )

    document = cursor.fetchone()

    conn.close()

    if not document:
        flash("Document not found.", "error")
        return redirect("/documents")

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        document[0],
        as_attachment=True,
        download_name=document[1]
    )

@app.route("/delete-document/<int:id>")
def delete_document(id):

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database/cloudvault.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT stored_name
        FROM documents
        WHERE id=? AND user_id=?
        """,
        (id, session["user_id"])
    )

    doc = cursor.fetchone()

    if doc:

        path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            doc[0]
        )

        if os.path.exists(path):
            os.remove(path)

        cursor.execute(
            """
            DELETE FROM documents
            WHERE id=?
            """,
            (id,)
        )

        conn.commit()

    conn.close()

    return redirect("/documents")

from datetime import datetime

@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():

    if "pending_registration" not in session:
        flash("Registration session expired. Please register again.", "error")
        return redirect("/register")

    pending = session["pending_registration"]

    # Mask email for display
    email = pending["email"]
    username, domain = email.split("@")

    if len(username) > 2:
        masked_email = username[:2] + "*" * (len(username) - 2)
    else:
        masked_email = username[0] + "*"

    masked_email += "@" + domain

    if request.method == "POST":

        entered_otp = request.form["otp"]

        expiry = datetime.strptime(
            pending["expires_at"],
            "%Y-%m-%d %H:%M:%S"
        )

        if datetime.now() > expiry:
            session.pop("pending_registration", None)
            flash("OTP has expired. Please register again.", "error")
            return redirect("/register")

        if entered_otp != pending["otp"]:
            flash("Invalid OTP. Please try again.", "error")
            return redirect("/verify-otp")

        conn = sqlite3.connect("database/cloudvault.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO users(full_name, email, password)
            VALUES (?, ?, ?)
            """,
            (
                pending["full_name"],
                pending["email"],
                pending["password"]
            )
        )

        conn.commit()
        conn.close()

        session.pop("pending_registration", None)

        flash(
            "Email verified successfully. Please login.",
            "success"
        )

        return redirect("/login")

    return render_template(
        "verify_otp.html",
        masked_email=masked_email
    )

@app.route("/resend-otp")
def resend_otp():

    if "pending_registration" not in session:
        flash("Registration session expired.", "error")
        return redirect("/register")

    pending = session["pending_registration"]

    otp = str(random.randint(100000, 999999))

    pending["otp"] = otp
    pending["expires_at"] = (
        datetime.now() + timedelta(minutes=5)
    ).strftime("%Y-%m-%d %H:%M:%S")

    session["pending_registration"] = pending

    try:

        msg = Message(
            subject="CloudVault Eclipse - Verification Code",
            sender=app.config["MAIL_USERNAME"],
            recipients=[pending["email"]]
        )

        msg.body = f"""
Hello {pending['full_name']},

Your new verification code is:

{otp}

This code will expire in 5 minutes.

Regards,
CloudVault Eclipse
"""

        mail.send(msg)

        flash("A new OTP has been sent to your email.", "success")

    except Exception as e:

        flash(f"Unable to resend OTP: {e}", "error")

    return redirect("/verify-otp")

@app.route("/contact", methods=["GET", "POST"])
def contact():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        subject = request.form["subject"]
        message = request.form["message"]

        try:

            msg = Message(
                subject=f"CloudVault Contact - {subject}",
                sender=app.config["MAIL_USERNAME"],
                recipients=[app.config["MAIL_USERNAME"]]
            )

            msg.body = f"""
CloudVault Eclipse Contact Form

Name: {name}
Email: {email}

Subject:
{subject}

Message:
{message}
"""

            mail.send(msg)

            flash("Your message has been sent successfully!", "success")

            return redirect("/contact")

        except Exception as e:

            flash(f"Unable to send message: {e}", "error")

            return redirect("/contact")

    return render_template("contact.html")

@app.route("/admin/delete-user/<int:user_id>")
def admin_delete_user(user_id):

    # User must be logged in
    if "user_id" not in session:
        return redirect("/login")

    # Must be an admin
    if session.get("role") != "admin":
        flash("Access denied.", "error")
        return redirect("/dashboard")

    # Prevent deleting yourself
    if user_id == session["user_id"]:
        flash("You cannot delete your own account.", "error")
        return redirect("/admin")

    conn = sqlite3.connect("database/cloudvault.db")
    cursor = conn.cursor()

    # Check if user exists
    cursor.execute(
        """
        SELECT id
        FROM users
        WHERE id=?
        """,
        (user_id,)
    )

    user = cursor.fetchone()

    if not user:
        conn.close()
        flash("User not found.", "error")
        return redirect("/admin")

    # Get all uploaded files
    cursor.execute(
        """
        SELECT stored_name
        FROM documents
        WHERE user_id=?
        """,
        (user_id,)
    )

    documents = cursor.fetchall()

    # Delete physical files
    for document in documents:

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            document[0]
        )

        if os.path.exists(file_path):
            os.remove(file_path)

    # Delete document records
    cursor.execute(
        """
        DELETE FROM documents
        WHERE user_id=?
        """,
        (user_id,)
    )

    # Delete user
    cursor.execute(
        """
        DELETE FROM users
        WHERE id=?
        """,
        (user_id,)
    )

    conn.commit()
    conn.close()

    flash("User deleted successfully.", "success")

    return redirect("/admin")

if __name__ == "__main__":
    app.run(debug=True) 
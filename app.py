import os
import sqlite3
import random
from datetime import datetime, timedelta
from flask import Flask, render_template
from flask import session, redirect, request, flash , Response
from flask import send_from_directory
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = "cloudvault_eclipse_2026"
app.secret_key = os.getenv("SECRET_KEY")
# AWS S3 Configuration
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

AWS_BUCKET = os.getenv("AWS_BUCKET_NAME")
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

        if file and file.filename != "":

            filename = secure_filename(file.filename)
            stored_name = f"{int(time.time())}_{filename}"

            # Get file size BEFORE uploading
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            try:

                # Upload to AWS S3
                s3.upload_fileobj(
                    file,
                    AWS_BUCKET,
                    stored_name,
                    ExtraArgs={
                        "ContentType": file.content_type
                    }
                )

                conn = sqlite3.connect("database/cloudvault.db")
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO documents
                    (user_id, file_name, stored_name, file_type, file_size, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session["user_id"],
                        filename,
                        stored_name,
                        file.content_type,
                        file_size,
                        category
                    )
                )

                conn.commit()
                conn.close()

                flash("Document uploaded successfully.", "success")
                return redirect("/documents")

            except Exception as e:
                print("UPLOAD ERROR:", e)   # <-- print to terminal
                flash(f"Upload failed: {e}", "error")

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

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    conn = sqlite3.connect("database/cloudvault.db")
    cursor = conn.cursor()

    # Base query
    query = """
        SELECT *
        FROM documents
        WHERE user_id=?
    """

    params = [session["user_id"]]

    # Search by filename
    if search:
        query += " AND file_name LIKE ?"
        params.append(f"%{search}%")

    # Filter by category
    if category and category != "All":
        query += " AND category=?"
        params.append(category)

    # Latest uploads first
    query += " ORDER BY upload_date DESC"

    cursor.execute(query, tuple(params))
    docs = cursor.fetchall()

    # Fetch unique categories for dropdown
    cursor.execute(
        """
        SELECT DISTINCT category
        FROM documents
        WHERE user_id=?
        ORDER BY category
        """,
        (session["user_id"],)
    )

    categories = [row[0] for row in cursor.fetchall()]

    conn.close()

    return render_template(
        "documents.html",
        documents=docs,
        categories=categories,
        search=search,
        selected_category=category
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

    stored_name = document[0]
    original_name = document[1]

    try:

        file_obj = s3.get_object(
            Bucket=AWS_BUCKET,
            Key=stored_name
        )

        return Response(
            file_obj["Body"].read(),
            mimetype=file_obj["ContentType"],
            headers={
                "Content-Disposition": f'attachment; filename="{original_name}"'
            }
        )

    except Exception as e:
        flash(f"Download failed: {e}", "error")
        return redirect("/documents")

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

    document = cursor.fetchone()

    if not document:
        conn.close()
        flash("Document not found.", "error")
        return redirect("/documents")

    stored_name = document[0]

    try:

        # Delete from AWS S3
        s3.delete_object(
            Bucket=AWS_BUCKET,
            Key=stored_name
        )

        # Delete metadata from SQLite
        cursor.execute(
            """
            DELETE FROM documents
            WHERE id=?
            """,
            (id,)
        )

        conn.commit()

        flash("Document deleted successfully.", "success")

    except Exception as e:

        flash(f"Delete failed: {e}", "error")

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

@app.route("/change_password", methods=["GET", "POST"])
def change_password():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        conn = sqlite3.connect("database/cloudvault.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT password FROM users WHERE id=?",
            (session["user_id"],)
        )

        user = cursor.fetchone()

        if not check_password_hash(user[0], current_password):
            flash("Current password is incorrect.", "error")
            conn.close()
            return redirect("/change-password")

        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            conn.close()
            return redirect("/change-password")

        hashed_password = generate_password_hash(new_password)

        cursor.execute(
            "UPDATE users SET password=? WHERE id=?",
            (hashed_password, session["user_id"])
        )

        conn.commit()
        conn.close()

        flash("Password changed successfully.", "success")

        return redirect("/profile")

    return render_template("change_password.html")

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

@app.route("/admin/change-role/<int:user_id>")
def change_user_role(user_id):

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "admin":
        flash("Access denied.", "error")
        return redirect("/dashboard")

    if user_id == session["user_id"]:
        flash("You cannot change your own role.", "error")
        return redirect("/admin")

    conn = sqlite3.connect("database/cloudvault.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role
        FROM users
        WHERE id=?
    """, (user_id,))

    user = cursor.fetchone()

    if not user:
        conn.close()
        flash("User not found.", "error")
        return redirect("/admin")

    new_role = "admin" if user[0] == "user" else "user"

    cursor.execute("""
        UPDATE users
        SET role=?
        WHERE id=?
    """, (new_role, user_id))

    conn.commit()
    conn.close()

    flash(f"User role changed to {new_role.title()}.", "success")

    return redirect("/admin")

@app.route("/admin/documents")
def admin_documents():

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "admin":
        flash("Access denied.", "error")
        return redirect("/dashboard")

    conn = sqlite3.connect("database/cloudvault.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            documents.id,
            users.full_name,
            documents.file_name,
            documents.category,
            documents.file_type,
            documents.file_size,
            documents.upload_date
        FROM documents
        JOIN users
        ON documents.user_id = users.id
        ORDER BY documents.upload_date DESC
    """)

    documents = cursor.fetchall()

    conn.close()

    return render_template(
        "admin_documents.html",
        documents=documents
    )

@app.route("/admin/download-document/<int:document_id>")
def admin_download_document(document_id):

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "admin":
        flash("Access denied.", "error")
        return redirect("/dashboard")

    conn = sqlite3.connect("database/cloudvault.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT stored_name, file_name
        FROM documents
        WHERE id=?
    """, (document_id,))

    document = cursor.fetchone()

    conn.close()

    if not document:
        flash("Document not found.", "error")
        return redirect("/admin/documents")

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        document[0],
        as_attachment=True,
        download_name=document[1]
    )

@app.route("/admin/delete-document/<int:document_id>")
def admin_delete_document(document_id):

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "admin":
        flash("Access denied.", "error")
        return redirect("/dashboard")

    conn = sqlite3.connect("database/cloudvault.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT stored_name
        FROM documents
        WHERE id=?
    """, (document_id,))

    document = cursor.fetchone()

    if not document:
        conn.close()
        flash("Document not found.", "error")
        return redirect("/admin/documents")

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        document[0]
    )

    if os.path.exists(file_path):
        os.remove(file_path)

    cursor.execute("""
        DELETE FROM documents
        WHERE id=?
    """, (document_id,))

    conn.commit()
    conn.close()

    flash("Document deleted successfully.", "success")

    return redirect("/admin/documents")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
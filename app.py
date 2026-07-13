from flask import Flask, render_template
from flask import session, redirect, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from werkzeug.utils import secure_filename
from flask import send_from_directory

app = Flask(__name__)
import os
print("Current Working Directory:", os.getcwd())
print("Database Path:", os.path.abspath("database/cloudvault.db"))
app.secret_key = "cloudvault_eclipse_2026"


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
            "INSERT INTO users(full_name,email,password) VALUES(?,?,?)",
            (full_name, email, password)
        )

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

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


if __name__ == "__main__":
    app.run(debug=True) 
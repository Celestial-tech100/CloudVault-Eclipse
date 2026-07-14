# ☁️ CloudVault Eclipse

A Secure Cloud Document Management System built using **Python Flask** and **Amazon AWS S3**.

CloudVault Eclipse enables users to securely upload, organize, download, and manage documents in the cloud with role-based authentication, email OTP verification, and an administrator dashboard.

---

# System Architecture

![CloudVault Eclipse Architecture](screenshots/architecture.png)

# 📌 Features

### 👤 User Authentication

- User Registration
- Secure Login
- Password Hashing
- Email OTP Verification
- Change Password
- Logout

---

### ☁️ Cloud Document Management

- Upload Documents
- Store Documents on AWS S3
- Download Documents
- Delete Documents
- Category-based Organization
- Search Documents
- Document Metadata Storage

---

### 🛡️ Security

- Password Hashing
- Session Authentication
- Role-Based Access Control
- Secure File Access
- Email Verification via OTP
- AWS Cloud Storage

---

### 👨‍💼 Admin Dashboard

- View Total Users
- View Total Documents
- Storage Statistics
- Today's Upload Count
- Promote User to Admin
- Delete Users

---

# 🛠️ Tech Stack

| Technology     | Purpose                   |
| -------------- | ------------------------- |
| Python Flask   | Backend                   |
| HTML5          | Frontend                  |
| CSS3           | Styling                   |
| JavaScript     | Client-side Functionality |
| SQLite         | Database                  |
| Amazon AWS S3  | Cloud File Storage        |
| Docker         | Containerization          |
| GitHub Actions | Continuous Integration    |

---

# 📁 Project Structure

```
CloudVault Eclipse/
│
├── app.py
├── database/
├── static/
├── templates/
├── .github/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

# ☁️ AWS S3 Integration

Uploaded documents are securely stored in an Amazon S3 bucket.

The SQLite database stores only:

- File Name
- Category
- File Size
- File Type
- Upload Date
- S3 Object Key

Actual document files remain securely stored in AWS S3.

---

# 🐳 Docker

Build the application

```bash
docker compose build
```

Run

```bash
docker compose up
```

Application runs on

```
http://localhost:5000
```

---

# ⚙️ Installation

Clone the repository

```bash
git clone https://github.com/Celestial-tech100/CloudVault-Eclipse.git
```

Install dependencies

```bash
pip install -r requirements.txt
```

Run the application

```bash
python app.py
```

---

# 🔑 Environment Variables

Create a `.env` file containing:

```env
SECRET_KEY=your_secret_key

EMAIL_USER=your_email
EMAIL_PASSWORD=your_password

AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_BUCKET_NAME=your_bucket
AWS_REGION=your_region
```

---

# 📷 Screenshots

- Landing Page
- Login
- Dashboard
- Upload Document
- Documents
- Admin Dashboard
- AWS S3 Bucket

(Add screenshots before submission.)

---

# 🚀 Future Enhancements

- PostgreSQL Integration
- File Sharing
- Version Control
- Multi-Factor Authentication
- Audit Logs
- AI-based Document Classification

---

# 👨‍💻 Developed By

**Celestial-tech100**
**Divya H Kishore**
2026

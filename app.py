from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory
from werkzeug.utils import secure_filename
import sqlite3
import bcrypt
import os
from datetime import datetime
import secrets

# ===== OCR INTEGRATION =====
from ocr import perform_ocr, extract_invoice_details

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------- DB INIT ----------
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS receipts(
            receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            vendor_name TEXT,
            invoice_number TEXT,
            date TEXT,
            total_amount REAL,
            tax REAL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()

init_db()

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


# ---------- HOME ----------
@app.route("/")
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login_page.html')

@app.route("/register_page")
def register_page():
    return render_template('register.html')

@app.route("/forgot_password_page")
def forgot_password_page():
    return render_template('forgotpassword.html')

@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('home.html')


# ---------- REGISTER ----------
@app.route("/api/register", methods=["POST"])
def register():
    username = request.form["username"]
    email = request.form["email"]
    password = request.form["password"]
    phone = request.form.get("phone", "")

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username=? OR email=?", (username, email))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False}), 400

    cursor.execute("""
        INSERT INTO users(username, email, password, phone)
        VALUES (?,?,?,?)
    """, (username, email, hashed, phone))

    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ---------- LOGIN ----------
@app.route("/api/login", methods=["POST"])
def login():
    user_input = request.form["username"]
    password = request.form["password"]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, username, password FROM users
        WHERE username=? OR email=?
    """, (user_input, user_input))

    result = cursor.fetchone()
    conn.close()

    if result is None:
        return jsonify({"success": False}), 404

    user_id, username, stored_password = result

    if bcrypt.checkpw(password.encode(), stored_password):
        session['user_id'] = user_id
        session['username'] = username
        return jsonify({"success": True})
    else:
        return jsonify({"success": False}), 401


# ---------- LOGOUT ----------
@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


# ---------- UPLOAD WITH OCR ----------
@app.route("/api/upload", methods=["POST"])
def upload_receipt():

    print("\n🔥 UPLOAD API HIT 🔥")

    if 'user_id' not in session:
        return jsonify({"success": False}), 401

    if 'file' not in request.files:
        return jsonify({"success": False}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"success": False}), 400

    if file and allowed_file(file.filename):

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # ===== OCR START =====
        text = perform_ocr(filepath)

        details = extract_invoice_details(text)

        print("\nEXTRACTED DETAILS:")
        print(details)

        vendor = details.get("Vendor")
        invoice = details.get("Invoice Number")
        date = details.get("Date")
        total = details.get("Total Amount")
        tax = details.get("Tax")

        try:
            total = float(total) if total else 0.0
        except:
            total = 0.0

        try:
            tax = float(tax) if tax else 0.0
        except:
            tax = 0.0
        # ===== OCR END =====

        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO receipts(user_id, filename, vendor_name, invoice_number, date, total_amount, tax)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session['user_id'], filename, vendor, invoice, date, total, tax))

        receipt_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({"success": True, "receipt_id": receipt_id})

    return jsonify({"success": False}), 400


# ---------- GET RECEIPTS ----------
@app.route("/api/receipts", methods=["GET"])
def get_receipts():
    if 'user_id' not in session:
        return jsonify({"success": False}), 401

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT receipt_id, filename, upload_date, vendor_name, invoice_number, date, total_amount, tax
        FROM receipts WHERE user_id=?
    """, (session['user_id'],))

    receipts = cursor.fetchall()
    conn.close()

    result = []
    for r in receipts:
        result.append({
            "receipt_id": r[0],
            "filename": r[1],
            "upload_date": r[2],
            "vendor_name": r[3],
            "invoice_number": r[4],
            "date": r[5],
            "total_amount": r[6],
            "tax": r[7]
        })

    return jsonify({"success": True, "receipts": result})


# ---------- SERVE FILE ----------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ---------- START SERVER ----------
if __name__ == "__main__":
    app.run(debug=True, port=5000)

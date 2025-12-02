from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from functools import wraps
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret_key_here"  # セッション用

# DB接続
def get_db():
    conn = sqlite3.connect("inventory.db")
    conn.row_factory = sqlite3.Row
    return conn

# 権限デコレーター
def role_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            if session['role'] not in roles:
                return "権限がありません", 403
            return f(*args, **kwargs)
        return decorated
    return wrapper

# --- ログイン ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        if user and check_password_hash(user["password"], password):
            session["user"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("index"))
        return "ユーザー名またはパスワードが間違っています"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def index():
    return render_template("index.html")

# --- 在庫取得 ---
@app.route("/stock", methods=["GET"])
def get_stock():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT i.item_id, i.item_name, i.category, i.unit, i.reorder_point, i.standard_price,
               IFNULL(inv.quantity,0) AS quantity,
               inv.expiration_date,
               CASE WHEN IFNULL(inv.quantity,0) <= i.reorder_point THEN 1 ELSE 0 END AS reorder_flag
        FROM items i
        LEFT JOIN inventory inv ON i.item_id = inv.item_id
        ORDER BY i.item_id
    """)
    rows = cur.fetchall()
    return jsonify([dict(row) for row in rows])

# --- 入庫 ---
@app.route("/stock/in", methods=["POST"])
@role_required("owner", "manager")
def stock_in():
    data = request.json
    item_id = data["item_id"]
    qty = data["qty"]
    supplier_id = data.get("supplier_id")
    expiration_date = data.get("expiration_date")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM inventory WHERE item_id = ?", (item_id,))
    inv = cur.fetchone()
    if inv:
        cur.execute(
            "UPDATE inventory SET quantity = quantity + ?, last_update = CURRENT_TIMESTAMP WHERE item_id = ?",
            (qty, item_id)
        )
    else:
        cur.execute(
            "INSERT INTO inventory (item_id, quantity, expiration_date) VALUES (?, ?, ?)",
            (item_id, qty, expiration_date)
        )

    # 入庫履歴
    if supplier_id:
        cur.execute(
            "INSERT INTO stockin (item_id, supplier_id, quantity, expiration_date) VALUES (?, ?, ?, ?)",
            (item_id, supplier_id, qty, expiration_date)
        )

    conn.commit()
    return jsonify({"status": "ok"})

# --- 出庫 ---
@app.route("/stock/out", methods=["POST"])
@role_required("owner", "manager")
def stock_out():
    data = request.json
    item_id = data["item_id"]
    qty = data["qty"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE inventory SET quantity = quantity - ?, last_update = CURRENT_TIMESTAMP WHERE item_id = ?",
        (qty, item_id)
    )

    # 出庫履歴
    cur.execute(
        "INSERT INTO stockout (item_id, quantity) VALUES (?, ?)",
        (item_id, qty)
    )

    conn.commit()
    return jsonify({"status": "ok"})

# --- 履歴取得 ---
@app.route("/history", methods=["GET"])
def get_history():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT stockin_id AS id, item_id, quantity, date AS time, 'IN' AS action
        FROM stockin
        UNION ALL
        SELECT stockout_id AS id, item_id, quantity, date AS time, 'OUT' AS action
        FROM stockout
        ORDER BY time DESC
    """)
    rows = cur.fetchall()
    return jsonify([dict(row) for row in rows])

if __name__ == "__main__":
    app.run(debug=True)

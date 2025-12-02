import sqlite3
from datetime import datetime, timedelta
import random

DB_PATH = "inventory.db"
print("RUNNING sample_data.py")
print("DB path:", DB_PATH)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("=== サンプルデータ挿入開始 ===")

# ---------------------------
# items サンプル
# ---------------------------
items = [
    ("コーヒー豆", "ブラジル産", "袋", 10, 1200.0),
    ("紅茶", "ダージリン", "箱", 5, 800.0),
    ("ミルク", "低脂肪", "本", 20, 200.0),
    ("砂糖", "グラニュー糖", "袋", 15, 150.0),
    ("カップ", "紙製", "個", 50, 30.0),
    ("コーヒーフィルター", "円錐型", "袋", 20, 100.0),
    ("チョコレート", "スイス産", "個", 10, 500.0),
    ("ケーキ", "チーズケーキ", "個", 5, 600.0),
    ("紅茶ポット", "ガラス製", "個", 2, 3000.0),
    ("ミネラルウォーター", "500ml", "本", 30, 120.0),
]

cur.executemany("""
INSERT INTO items (item_name, category, unit, reorder_point, standard_price)
VALUES (?, ?, ?, ?, ?)
""", items)

# ---------------------------
# suppliers サンプル
# ---------------------------
suppliers = [
    ("サプライA", "田中太郎", "tanaka@example.com", "東京都港区1-1-1"),
    ("サプライB", "鈴木次郎", "suzuki@example.com", "東京都渋谷区2-2-2"),
    ("サプライC", "佐藤三郎", "sato@example.com", "東京都新宿区3-3-3"),
    ("サプライD", "高橋四郎", "takahashi@example.com", "東京都千代田区4-4-4"),
    ("サプライE", "伊藤五郎", "ito@example.com", "東京都中央区5-5-5"),
    ("サプライF", "渡辺六郎", "watanabe@example.com", "東京都台東区6-6-6"),
    ("サプライG", "山本七郎", "yamamoto@example.com", "東京都墨田区7-7-7"),
    ("サプライH", "中村八郎", "nakamura@example.com", "東京都江東区8-8-8"),
    ("サプライI", "小林九郎", "kobayashi@example.com", "東京都品川区9-9-9"),
    ("サプライJ", "加藤十郎", "kato@example.com", "東京都目黒区10-10-10"),
]

cur.executemany("""
INSERT INTO suppliers (supplier_name, contact, email, address)
VALUES (?, ?, ?, ?)
""", suppliers)

# ---------------------------
# inventory サンプル
# ---------------------------
inventory = []
for item_id in range(1, 11):
    quantity = random.randint(5, 50)
    expiration_date = datetime.now() + timedelta(days=random.randint(30, 180))
    inventory.append((item_id, quantity, expiration_date.strftime("%Y-%m-%d")))

cur.executemany("""
INSERT INTO inventory (item_id, quantity, expiration_date)
VALUES (?, ?, ?)
""", inventory)

# ---------------------------
# stockin サンプル
# ---------------------------
stockin = []
for i in range(1, 11):
    item_id = i
    supplier_id = random.randint(1, 10)
    quantity = random.randint(5, 30)
    expiration_date = datetime.now() + timedelta(days=random.randint(30, 180))
    stockin.append((item_id, supplier_id, quantity, expiration_date.strftime("%Y-%m-%d")))

cur.executemany("""
INSERT INTO stockin (item_id, supplier_id, quantity, expiration_date)
VALUES (?, ?, ?, ?)
""", stockin)

# ---------------------------
# stockout サンプル
# ---------------------------
stockout = []
usage_options = ["販売", "試食", "廃棄"]
for i in range(1, 11):
    item_id = i
    quantity = random.randint(1, 10)
    usage = random.choice(usage_options)
    stockout.append((item_id, quantity, usage))

cur.executemany("""
INSERT INTO stockout (item_id, quantity, usage)
VALUES (?, ?, ?)
""", stockout)

# ---------------------------
# orders サンプル
# ---------------------------
orders = []
status_options = ["発注済", "入荷待ち", "キャンセル"]
for i in range(1, 11):
    item_id = i
    supplier_id = random.randint(1, 10)
    quantity = random.randint(5, 20)
    status = random.choice(status_options)
    orders.append((item_id, supplier_id, quantity, status))

cur.executemany("""
INSERT INTO orders (item_id, supplier_id, quantity, status)
VALUES (?, ?, ?, ?)
""", orders)

# ---------------------------
# 保存・終了
# ---------------------------
conn.commit()
conn.close()
print("サンプルデータ挿入完了")

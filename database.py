import sqlite3
import datetime

DB_NAME = "ai_lecture_assistant.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            main_cat TEXT NOT NULL,
            sub_cat TEXT NOT NULL,
            UNIQUE(username, main_cat, sub_cat)
        )
    ''')
    # 👑 V3.0 终极架构：确保所有字段都在！
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            category_id INTEGER,
            filename TEXT,
            image_bytes BLOB,  
            record_type TEXT DEFAULT 'error', 
            user_annotation TEXT DEFAULT '',  -- 这是关键：专属注记字段
            is_starred INTEGER DEFAULT 0,     
            is_confused INTEGER DEFAULT 0,    -- ❓ 还没弄懂标记
            tags TEXT DEFAULT '',             -- AI 标签
            custom_tags TEXT DEFAULT '',      -- 自定义标签
            sort_order INTEGER DEFAULT 0,     -- 卡片排序号
            recognition TEXT,
            latex TEXT,
            analysis TEXT,
            exercise TEXT,
            mindmap TEXT,
            created_at TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ V3.0 数据库架构初始化完成！所有注记、状态字段已就位！")

def add_category(username, main_cat, sub_cat):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (username, main_cat, sub_cat) VALUES (?, ?, ?)", (username, main_cat, sub_cat))
        conn.commit()
        cat_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id FROM categories WHERE username=? AND main_cat=? AND sub_cat=?", (username, main_cat, sub_cat))
        cat_id = cursor.fetchone()[0]
    conn.close()
    return cat_id

def get_categories(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, main_cat, sub_cat FROM categories WHERE username=?", (username,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "main_cat": r[1], "sub_cat": r[2]} for r in rows]

# 👑 V3.0 核心修正：这个函数必须支持保存 user_annotation！ (注意第 8 个参数)
def save_note_to_db(username, category_id, filename, image_bytes, data_dict, record_type="error", custom_tags="", user_annotation=""):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now()
    
    # 🗂️ 计算新卡片的排序权重
    cursor.execute("SELECT MAX(sort_order) FROM saved_notes WHERE category_id=? AND username=?", (category_id, username))
    max_order = cursor.fetchone()[0]
    next_order = (max_order or 0) + 1
    
    # 👑 INSERT 语句必须把 user_annotation 塞进去！
    cursor.execute('''
        INSERT INTO saved_notes 
        (username, category_id, filename, image_bytes, record_type, user_annotation, tags, custom_tags, sort_order, recognition, latex, analysis, exercise, mindmap, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        username, category_id, filename, image_bytes, record_type, 
        user_annotation, # 🚀 关键：用户即时写的注记！
        data_dict.get("tags", ""), custom_tags, next_order,
        data_dict.get("recognition", ""), data_dict.get("latex", ""),
        data_dict.get("analysis", ""), data_dict.get("exercise", ""),
        data_dict.get("mindmap", ""), now
    ))
    conn.commit()
    conn.close()

def get_saved_notes(username, category_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    if category_id:
        cursor.execute("SELECT * FROM saved_notes WHERE username=? AND category_id=? ORDER BY sort_order DESC, created_at DESC", (username, category_id))
    else:
        cursor.execute("SELECT * FROM saved_notes WHERE username=? ORDER BY sort_order DESC, created_at DESC", (username,))
    rows = cursor.fetchall()
    conn.close()
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

def delete_saved_note(note_id, username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_notes WHERE id=? AND username=?", (note_id, username))
    conn.commit()
    conn.close()

def delete_category_and_notes(category_id, username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_notes WHERE category_id=? AND username=?", (category_id, username))
    cursor.execute("DELETE FROM categories WHERE id=? AND username=?", (category_id, username))
    conn.commit()
    conn.close()

# 👑 全能元数据更新通道 (⭐、❓、注记、自定义标签)
def update_note_metadata(note_id, username, new_annotation, is_starred, is_confused, custom_tags):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE saved_notes 
        SET user_annotation=?, is_starred=?, is_confused=?, custom_tags=? 
        WHERE id=? AND username=?
    ''', (new_annotation, is_starred, is_confused, custom_tags, note_id, username))
    conn.commit()
    conn.close()

# 🗂️ 交互式上移/下调顺序魔法
def swap_notes_order(id1, order1, id2, order2, username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE saved_notes SET sort_order=? WHERE id=? AND username=?", (order2, id1, username))
    cursor.execute("UPDATE saved_notes SET sort_order=? WHERE id=? AND username=?", (order1, id2, username))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()

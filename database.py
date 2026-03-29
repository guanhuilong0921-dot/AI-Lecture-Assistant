import os
import psycopg2
import datetime
from dotenv import load_dotenv

# 加载环境变量里的隐藏钥匙
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

def get_connection():
    # 连接到 Supabase 云端 PostgreSQL
    return psycopg2.connect(DB_URL)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 创建分类表 (注意 PostgreSQL 使用 SERIAL 作为自增主键)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            main_cat TEXT NOT NULL,
            sub_cat TEXT NOT NULL,
            UNIQUE(username, main_cat, sub_cat)
        )
    ''')
    
    # 创建主数据表 (注意图片字段变成了 BYTEA)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_notes (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            category_id INTEGER REFERENCES categories (id) ON DELETE CASCADE,
            filename TEXT,
            image_bytes BYTEA,  
            record_type TEXT DEFAULT 'error', 
            user_annotation TEXT DEFAULT '',  
            is_starred INTEGER DEFAULT 0,     
            is_confused INTEGER DEFAULT 0,    
            tags TEXT DEFAULT '',             
            custom_tags TEXT DEFAULT '',      
            sort_order INTEGER DEFAULT 0,     
            recognition TEXT,
            latex TEXT,
            analysis TEXT,
            exercise TEXT,
            mindmap TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ 伟大的时刻！Supabase 云端数据库架构初始化成功！")

def add_category(username, main_cat, sub_cat):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # PostgreSQL 使用 %s 作为占位符，且支持 RETURNING 直接返回新 ID
        cursor.execute(
            "INSERT INTO categories (username, main_cat, sub_cat) VALUES (%s, %s, %s) RETURNING id", 
            (username, main_cat, sub_cat)
        )
        cat_id = cursor.fetchone()[0]
        conn.commit()
    except psycopg2.IntegrityError:
        # 如果触发了 UNIQUE 约束，PostgreSQL 必须先 rollback 才能继续查询
        conn.rollback()
        cursor.execute(
            "SELECT id FROM categories WHERE username=%s AND main_cat=%s AND sub_cat=%s", 
            (username, main_cat, sub_cat)
        )
        cat_id = cursor.fetchone()[0]
    conn.close()
    return cat_id

def get_categories(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, main_cat, sub_cat FROM categories WHERE username=%s", (username,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "main_cat": r[1], "sub_cat": r[2]} for r in rows]

def save_note_to_db(username, category_id, filename, image_bytes, data_dict, record_type="error", custom_tags="", user_annotation=""):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now()
    
    cursor.execute("SELECT MAX(sort_order) FROM saved_notes WHERE category_id=%s AND username=%s", (category_id, username))
    max_order = cursor.fetchone()[0]
    next_order = (max_order or 0) + 1
    
    cursor.execute('''
        INSERT INTO saved_notes 
        (username, category_id, filename, image_bytes, record_type, user_annotation, tags, custom_tags, sort_order, recognition, latex, analysis, exercise, mindmap, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (
        username, category_id, filename, psycopg2.Binary(image_bytes), record_type, 
        user_annotation, 
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
        cursor.execute("SELECT * FROM saved_notes WHERE username=%s AND category_id=%s ORDER BY sort_order DESC, created_at DESC", (username, category_id))
    else:
        cursor.execute("SELECT * FROM saved_notes WHERE username=%s ORDER BY sort_order DESC, created_at DESC", (username,))
    rows = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    conn.close()
    
    # 将二进制数据解包回正常的 bytes 以供前端渲染
    results = []
    for row in rows:
        row_dict = dict(zip(columns, row))
        if row_dict['image_bytes']:
            row_dict['image_bytes'] = bytes(row_dict['image_bytes'])
        results.append(row_dict)
    return results

def delete_saved_note(note_id, username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_notes WHERE id=%s AND username=%s", (note_id, username))
    conn.commit()
    conn.close()

def delete_category_and_notes(category_id, username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_notes WHERE category_id=%s AND username=%s", (category_id, username))
    cursor.execute("DELETE FROM categories WHERE id=%s AND username=%s", (category_id, username))
    conn.commit()
    conn.close()

def update_note_metadata(note_id, username, new_annotation, is_starred, is_confused, custom_tags):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE saved_notes 
        SET user_annotation=%s, is_starred=%s, is_confused=%s, custom_tags=%s 
        WHERE id=%s AND username=%s
    ''', (new_annotation, is_starred, is_confused, custom_tags, note_id, username))
    conn.commit()
    conn.close()

def swap_notes_order(id1, order1, id2, order2, username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE saved_notes SET sort_order=%s WHERE id=%s AND username=%s", (order2, id1, username))
    cursor.execute("UPDATE saved_notes SET sort_order=%s WHERE id=%s AND username=%s", (order1, id2, username))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()

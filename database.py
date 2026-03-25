import sqlite3
import datetime

# 定义数据库文件的名字，它会自动生成在你的项目目录里
DB_NAME = "ai_lecture_assistant.db"

def get_connection():
    """获取数据库连接"""
    # check_same_thread=False 是为了让 Streamlit 的多线程也能安全访问数据库
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    """
    初始化数据库：如果表不存在，就自动创建两张表。
    一张存分类目录（categories），一张存具体的笔记和错题（saved_notes）。
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. 创建分类目录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            main_cat TEXT NOT NULL,
            sub_cat TEXT NOT NULL,
            UNIQUE(username, main_cat, sub_cat) -- 防止同一个用户建重复的目录
        )
    ''')
    
    # 2. 创建笔记与错题档案表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            category_id INTEGER,
            filename TEXT,
            image_bytes BLOB,  -- 用 BLOB 格式直接把原始图片以二进制形式存进硬盘！
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
    print("✅ 数据库初始化完成！")

def add_category(username, main_cat, sub_cat):
    """添加一个新的分类目录（如果已经存在就不重复添加），返回该目录的 ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO categories (username, main_cat, sub_cat) VALUES (?, ?, ?)",
            (username, main_cat, sub_cat)
        )
        conn.commit()
        cat_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # 如果触发了 UNIQUE 约束，说明目录已存在，我们就直接查出它的 ID
        cursor.execute(
            "SELECT id FROM categories WHERE username=? AND main_cat=? AND sub_cat=?",
            (username, main_cat, sub_cat)
        )
        cat_id = cursor.fetchone()[0]
        
    conn.close()
    return cat_id

def get_categories(username):
    """获取某个用户的所有分类目录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, main_cat, sub_cat FROM categories WHERE username=?", (username,))
    rows = cursor.fetchall()
    conn.close()
    
    # 组装成好用的字典格式
    cat_list = [{"id": r[0], "main_cat": r[1], "sub_cat": r[2]} for r in rows]
    return cat_list

def save_note_to_db(username, category_id, filename, image_bytes, data_dict):
    """将一条完整的解析记录（连同原图）硬核保存到数据库中"""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.datetime.now()
    
    cursor.execute('''
        INSERT INTO saved_notes 
        (username, category_id, filename, image_bytes, recognition, latex, analysis, exercise, mindmap, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        username,
        category_id,
        filename,
        image_bytes,  # 原始图片字节！
        data_dict.get("recognition", ""),
        data_dict.get("latex", ""),
        data_dict.get("analysis", ""),
        data_dict.get("exercise", ""),
        data_dict.get("mindmap", ""),
        now
    ))
    
    conn.commit()
    conn.close()

def get_saved_notes(username, category_id=None):
    """读取某个用户保存的笔记。如果传了 category_id，就只读那个目录下的。"""
    conn = get_connection()
    cursor = conn.cursor()
    
    if category_id:
        cursor.execute("SELECT * FROM saved_notes WHERE username=? AND category_id=? ORDER BY created_at DESC", (username, category_id))
    else:
        cursor.execute("SELECT * FROM saved_notes WHERE username=? ORDER BY created_at DESC", (username,))
        
    rows = cursor.fetchall()
    conn.close()
    
    # 提取字段名，方便转成字典
    columns = [column[0] for column in cursor.description]
    results = []
    for row in rows:
        results.append(dict(zip(columns, row)))
        
    return results
def delete_saved_note(note_id, username):
    """
    删除单条错题/笔记记录。
    【安全设计】：必须同时匹配 note_id 和 username，防止黑客恶意删除别人的笔记！
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 执行删除指令
    cursor.execute("DELETE FROM saved_notes WHERE id=? AND username=?", (note_id, username))
    
    conn.commit()
    conn.close()
    return True

def delete_category_and_notes(category_id, username):
    """
    删除整个分类目录（例如直接删掉“大一上-高数”这个文件夹）。
    【级联删除】：不仅要删掉目录本身，还要把这个目录下存放的所有错题一起清空。
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. 先把属于这个目录的所有笔记统统删掉
    cursor.execute("DELETE FROM saved_notes WHERE category_id=? AND username=?", (category_id, username))
    
    # 2. 再把目录本身删掉
    cursor.execute("DELETE FROM categories WHERE id=? AND username=?", (category_id, username))
    
    conn.commit()
    conn.close()
    return True

# 当你直接运行这个文件时，它会自动帮你建表
if __name__ == "__main__":
    init_db()
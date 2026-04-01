from fastapi import FastAPI, HTTPException, File, UploadFile, Form # 新增了 File 和 UploadFile
import json
from pydantic import BaseModel
from typing import List
import shutil
import os
import database as db
from fastapi.middleware.cors import CORSMiddleware
import main as ai_main # 👈 引入你原来写好的通义千问核心逻辑
from PIL import Image
import io
import json
import base64
import dashscope
from dashscope import MultiModalConversation



app = FastAPI()

# 允许跨域请求（前端 HTML 和后端 API 运行在不同端口时需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def stitch_images_vertically(image_bytes_list):
    """将多张图片的字节流垂直拼接成长图"""
    if not image_bytes_list: return None
    try:
        images = [Image.open(io.BytesIO(b)).convert('RGB') for b in image_bytes_list]
        total_height = sum(img.height for img in images)
        max_width = max(img.width for img in images)
        # 创建空白长图
        new_img = Image.new('RGB', (max_width, total_height), (255, 255, 255))
        y_offset = 0
        for img in images:
            # 水平居中粘贴
            x_offset = (max_width - img.width) // 2
            new_img.paste(img, (x_offset, y_offset))
            y_offset += img.height
        # 转回 bytes
        img_byte_arr = io.BytesIO()
        new_img.save(img_byte_arr, format='JPEG', quality=85)
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"❌ 图片拼接失败: {str(e)}")
        return None

# 定义前端传过来的数据格式
class LoginRequest(BaseModel):
    username: str
    password: str

# 提取你原本 app.py 中的硬编码用户数据
VALID_USERS = {"huilong": "gaoling2026", "teacher": "ruc123"}

@app.get("/")
def read_root():
    return {"message": "Hello World"}
@app.post("/api/login")
async def login(request: LoginRequest):
    """处理登录请求的接口"""
    user = request.username
    pwd = request.password
    
    if user in VALID_USERS and VALID_USERS[user] == pwd:
        return {"status": "success", "message": f"欢迎, {user}!"}
    else:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

@app.get("/api/categories/{username}")
async def get_categories(username: str):
    """获取用户分类列表的接口"""
    # 直接调用你写的数据库函数
    categories = db.get_categories(username)
    return {"status": "success", "data": categories}

@app.post("/api/parse_images")
async def parse_images(files: List[UploadFile] = File(...)):
    """接收前端传来的多张图片，拼接后调用大模型解析"""
    if not files:
        raise HTTPException(status_code=400, detail="没有上传任何图片")

    print(f"🚀 收到前端请求！共有 {len(files)} 张图片，正在准备合并...")
    
    try:
        # 1. 把所有上传的图片读取为字节流
        image_bytes_list = []
        for file in files:
            content = await file.read()
            image_bytes_list.append(content)
            
        # 2. 只有一张图就直接用，多张图就调用缝合函数
        if len(image_bytes_list) > 1:
            print("📸 正在将多张图片垂直拼接成长图...")
            final_image_bytes = stitch_images_vertically(image_bytes_list)
        else:
            final_image_bytes = image_bytes_list[0]
            
        # 3. 把最终要解析的图片保存为临时文件，供 main.py 调用
        temp_file_path = "temp_merged_for_ai.jpg"
        with open(temp_file_path, "wb") as f:
            f.write(final_image_bytes)
            
        print(f"✅ 图片准备完毕，正在召唤大模型视觉引擎...")
        
        # 4. 调用大模型！
        result_dict = ai_main.process_image_to_dict(temp_file_path)
        
        # 5. 打扫战场
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
        if result_dict:
            # 这里我们把拼图的字节流也暂存在后端，为以后存入数据库做准备
            return {"status": "success", "data": result_dict}
        else:
            raise HTTPException(status_code=500, detail="大模型解析失败，请检查 API Key 或网络")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
@app.post("/api/save_note")
async def save_note(
    username: str = Form(...),
    main_cat: str = Form(...),
    sub_cat: str = Form(...), # 前端已经把二级和三级目录拼装好传进来了
    record_type: str = Form(...),
    custom_tags: str = Form(""),
    user_annotation: str = Form(""), # 🌟 新增：接收前端传来的批注
    ai_data_json: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """接收前端的数据，拼接图片并永久存入 Supabase"""
    try:
        # ... 前面的图片读取和 json 解析保持不变 ...
        image_bytes_list = [await f.read() for f in files]
        if len(image_bytes_list) > 1:
            final_image_bytes = stitch_images_vertically(image_bytes_list)
        else:
            final_image_bytes = image_bytes_list[0]
            
        ai_data = json.loads(ai_data_json)
        
        # 调用你的 database.py
        cat_id = db.add_category(username, main_cat, sub_cat)
        filename = f"Web_Note_{files[0].filename}"
        
        # 🌟 关键修改：把批注存入数据库
        success = db.save_note_to_db(
            username=username,
            category_id=cat_id,
            filename=filename,
            image_bytes=final_image_bytes,
            data=ai_data,
            record_type=record_type,
            custom_tags=custom_tags,
            user_annotation=user_annotation # 👈 这里不再是空字符串，而是用前端传来的真实批注
        )
        
        if success:
            return {"status": "success", "message": f"成功保存到 {main_cat} - {sub_cat}！"}
        else:
            raise HTTPException(status_code=500, detail="数据库写入失败")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存报错: {str(e)}")
@app.get("/api/notes/{username}")
async def get_user_notes(username: str, category_id: int = None):
    """拉取用户的复习笔记，并将图片转码为前端可显示的 Base64 格式"""
    try:
        # 调用你写好的数据库函数获取字典列表
        notes = db.get_saved_notes(username, category_id)
        
        # 遍历每一条笔记，对图片进行 Base64 "翻译"
        for note in notes:
            # 1. 处理主图片
            if note.get('image_bytes'):
                # 将 bytes 编码为 base64 字符串
                b64_str = base64.b64encode(note['image_bytes']).decode('utf-8')
                # 拼凑成 HTML 认识的 data URI 格式
                note['image_base64'] = f"data:image/jpeg;base64,{b64_str}"
                # 删掉原始的 bytes 数据，否则等会儿转换 JSON 会报错！
                del note['image_bytes']
                
            # 2. 如果有手写的补充图片，也做同样处理
            if note.get('annotation_image_bytes'):
                b64_str = base64.b64encode(note['annotation_image_bytes']).decode('utf-8')
                note['anno_image_base64'] = f"data:image/jpeg;base64,{b64_str}"
                del note['annotation_image_bytes']
                
        return {"status": "success", "data": notes}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取笔记失败: {str(e)}")
# 定义前端传过来的更新数据格式
class NoteUpdateRequest(BaseModel):
    username: str
    user_annotation: str

@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: int, username: str):
    """删除指定的复习卡片"""
    try:
        db.delete_saved_note(note_id, username)
        return {"status": "success", "message": "卡片已彻底删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/notes/{note_id}")
async def update_note(note_id: int, request: NoteUpdateRequest):
    """更新复习卡片的批注内容"""
    try:
        # 调用 database.py 里的更新逻辑（0, 0 是预留给星号和疑问标记的）
        res = db.update_note_metadata(
            note_id, 
            request.username, 
            request.user_annotation, 
            0, 
            0, 
            "" 
        )
        if res == "SUCCESS":
            return {"status": "success", "message": "注记更新成功"}
        else:
            raise HTTPException(status_code=500, detail=res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# 定义前端传过来的助教请求格式
from typing import List

# 接收前端传来的多题 ID 列表
class TutorRequest(BaseModel):
    note_ids: List[int] 
    username: str
    question: str

@app.post("/api/ask_tutor")
async def ask_tutor(request: TutorRequest):
    """召唤全局悬浮助教：支持读取多张图片合并解答"""
    try:
        if not request.note_ids:
            raise HTTPException(status_code=400, detail="未选择任何题目")

        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 批量查询选中的多张图片
        format_strings = ','.join(['%s'] * len(request.note_ids))
        query = f"SELECT image_bytes FROM saved_notes WHERE username=%s AND id IN ({format_strings})"
        cursor.execute(query, [request.username] + request.note_ids)
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            raise HTTPException(status_code=404, detail="找不到图片数据")
            
        image_bytes_list = [bytes(row[0]) for row in rows]
        
        # 调用拼接函数，把多图拼成一张发给大模型
        if len(image_bytes_list) > 1:
            final_image_bytes = stitch_images_vertically(image_bytes_list)
        else:
            final_image_bytes = image_bytes_list[0]
            
        temp_path = f"temp_tutor_multi.jpg"
        with open(temp_path, "wb") as f:
            f.write(final_image_bytes)
            
        prompt_text = rf"""你是一个极其专业的 AI 学习助教。请结合图片，极具针对性地回答用户的疑问。
用户的问题是：【 {request.question} 】

⚠️【排版铁律】：所有的数学公式必须用 $（行内）或 $$（独立行）包裹！不要使用任何 Markdown 代码块！"""
        
        messages = [{"role": "user", "content": [{"image": f"file://{os.path.abspath(temp_path)}"}, {"text": prompt_text}]}]
        
        resp = MultiModalConversation.call(model='qwen-vl-plus', messages=messages)
        
        if os.path.exists(temp_path): os.remove(temp_path)
            
        if resp.status_code == 200:
            reply = resp.output.choices[0].message.content[0]['text']
            return {"status": "success", "reply": reply}
        else:
            raise HTTPException(status_code=500, detail=resp.message)
            
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"AI 助教开小差了: {str(e)}")

# 启动命令: uvicorn api:app --reload
import streamlit as st
import os
import subprocess
import time
from PIL import Image
import io
import dashscope
from dashscope import MultiModalConversation
from main import process_image_to_dict
import database as db

st.set_page_config(layout="wide", page_title="高瓴 AI 学习 OS")

# ================= 🛡️ 注入全局 CSS (横向滚动条 & 换行) =================
st.markdown("""
    <style>
    /* 解决 LaTeX 数学公式溢出问题 */
    .katex-display {
        overflow-x: auto !important;
        overflow-y: hidden !important;
        padding-bottom: 10px;
    }
    /* 解决长段落文本不换行的问题 */
    .stMarkdown p {
        word-break: break-word;
    }
    /* 美化侧边栏单选框 */
    .stRadio > label {
        font-weight: bold;
        font-size: 1.1rem;
    }
    </style>
""", unsafe_allow_html=True)

# ================= 👑 提速引擎：云端数据缓存 (传引用版) =================
@st.cache_resource(ttl=3600)
def fetch_categories(username): return db.get_categories(username)

@st.cache_resource(ttl=3600)
def fetch_notes(username, category_id): return db.get_saved_notes(username, category_id)

def clear_db_cache(): fetch_categories.clear(); fetch_notes.clear()

# ================= 辅助函数：图片纵向拼接 (用于最终存储) =================
def stitch_images_vertically(image_bytes_list):
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
        st.error(f"❌ 图片拼接失败: {str(e)}")
        return None

# ================= 辅助函数：PDF 编译 =================
def compile_latex_to_pdf(latex_code, filename="generated_notes"):
    tex_file = f"{filename}.tex"
    pdf_file = f"{filename}.pdf"
    with open(tex_file, "w", encoding="utf-8") as f: f.write(latex_code)
    try:
        subprocess.run(["xelatex", "-interaction=nonstopmode", tex_file], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(pdf_file): return pdf_file
        return "ERROR_COMPILE"
    except FileNotFoundError: return "ERROR_NO_COMPILER"

# ================= 辅助函数：调用多模态答疑室 (支持单图/多图) =================
def call_ai_tutor_multi(image_bytes_list, question):
    messages = [{"role": "user", "content": []}]
    temp_paths = []
    
    # 💥 核心修改：如果有图片，循环加入大模型的 Context
    if image_bytes_list:
        for idx, img_b in enumerate(image_bytes_list):
            temp_path = f"temp_tutor_{idx}.jpg"
            temp_paths.append(temp_path)
            with open(temp_path, "wb") as f: f.write(img_b)
            # 大模型同时“看”多张图，建立跨页逻辑理解
            messages[0]["content"].append({"image": f"file://{os.path.abspath(temp_path)}"})
            
    # 🧠 架构师级 Prompt 优化：纯正向示范，消除“恶意遵从”
    prompt_text = f"""你是一个极其专业的 AI 学习助教。请结合图片，极具针对性地回答用户的疑问。

用户的问题是：【 {question or '请详细解释一下这部分的重点。'} 】

⚠️【数学公式排版铁律】：
请直接输出纯文本（严禁使用 ``` 代码块包裹），并且所有的数学公式必须严格遵循以下规则：

1. 行内公式：必须使用单个 $ 符号包裹。
   👉 正确示例：由于函数 $f(x, y)$ 在点 $(x_0, y_0)$ 处连续...

2. 独立公式：必须使用双 $$ 符号包裹，并单独成行。
   👉 正确示例：
   $$
   z - z_0 = \frac{{\partial f}}{{\partial x}}(x_0, y_0)(x - x_0)
   $$
"""
    
    messages[0]["content"].append({"text": prompt_text})
    
    try:
        # 为了多图理解，必须用 dashscope 官方 SDK 调用 (main.py 的 process 改成了支持多图模式)
        # 🚀 架构师提权：把输出限制开到最大，防止长篇大论时被强制掐断！
        resp = MultiModalConversation.call(
            model='qwen-vl-plus', 
            messages=messages,
            max_tokens=4096  # 允许它一次性吐出多达 4000 个 Token
        )
        for p in temp_paths: 
            if os.path.exists(p): os.remove(p)
        if resp.status_code == 200:
            return resp.output.choices[0].message.content[0]['text']
        return f"API 错误: {resp.message}"
    except Exception as e:
        for p in temp_paths: 
            if os.path.exists(p): os.remove(p)
        return f"发生网络错误: {str(e)}"

# ================= 1. 极简身份认证 =================
VALID_USERS = {"huilong": "gaoling2026", "teacher": "ruc123"}
if "logged_in" not in st.session_state: st.session_state.update({"logged_in": False, "username": ""})
if not st.session_state["logged_in"]:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.title("🔐 高瓴 AI 学习 OS (Beta)")
        st.divider()
        input_user = st.text_input("👤 用户名")
        input_pwd = st.text_input("🔑 密码", type="password")
        if st.button("登录进入系统", type="primary", width="stretch"):
            if input_user in VALID_USERS and VALID_USERS[input_user] == input_pwd:
                st.session_state.update({"logged_in": True, "username": input_user})
                st.rerun() 
            else: st.error("❌ 密码错误！")

# ================= 2. 登录成功后的主系统 =================
else:
    if "db_inited" not in st.session_state: db.init_db(); st.session_state["db_inited"] = True
    username = st.session_state["username"]

    with st.sidebar:
        st.success(f"👋 欢迎, **{username}**!")
        if st.button("🚪 退出登录", width="stretch"):
            st.session_state.update({"logged_in": False, "username": ""}); st.rerun()
        st.divider()
        app_mode = st.radio("系统导航", ["🔮 知识提取工作台", "📚 复习空间"])
        st.divider()
        st.info("💡 系统提示：云端数据缓存已开启。")

    # ================= 模式 A：知识提取工作台 (彻底重构) =================
    if app_mode == "🔮 知识提取工作台":
        st.title("🔮 AI 知识提取工作台")
        st.markdown("上传多页笔记，选择需要合并解析的图片（支持跨页整合）。")
        
        if "wb_images" not in st.session_state: st.session_state.wb_images = [] # 存储待处理图片
        if "wb_sigs" not in st.session_state: st.session_state.wb_sigs = set()
        if "wb_merged_result" not in st.session_state: st.session_state.wb_merged_result = None # 存储合并解析结果

        uploaded_files = st.file_uploader("📥 选择笔记图片（可随时追加，支持批量）", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        if uploaded_files:
            for f in uploaded_files:
                sig = f"{f.name}_{f.size}"
                if sig not in st.session_state.wb_sigs:
                    st.session_state.wb_images.append({"name": f.name, "bytes": f.getvalue(), "sig": sig})
                    st.session_state.wb_sigs.add(sig)

        # 核心交互区：图片多选与操作按钮
        if st.session_state.wb_images:
            st.divider()
            c_op1, c_op2, c_op3 = st.columns([1, 1, 2])
            with c_op1:
                if st.button("🗑️ 清空工作台", use_container_width=True):
                    st.session_state.wb_images = []; st.session_state.wb_sigs = set()
                    st.session_state.wb_merged_result = None; st.rerun()
            
            # --- 多选控制逻辑 ---
            selected_indices = []
            st.markdown("##### 📌 请勾选需要合并解析的图片页面 (支持多选跨页题)：")
            
            # 瀑布流展示待处理图片，并加多选框
            cols_img = st.columns(4)
            for i, img_data in enumerate(st.session_state.wb_images):
                with cols_img[i % 4]:
                    with st.container(border=True):
                        st.image(img_data["bytes"], use_container_width=True)
                        if st.checkbox(f"✅ 选择第 {i+1} 页", key=f"check_{i}"):
                            selected_indices.append(i)
                        c_del_inner = st.empty()
                        if c_del_inner.button("❌ 移出", key=f"del_img_{i}"):
                            removed = st.session_state.wb_images.pop(i)
                            st.session_state.wb_sigs.remove(removed["sig"]); st.rerun()

            # --- 合并解析按钮逻辑 ---
            # --- 合并解析按钮与动态难度逻辑 ---
            with c_op2:
                # 🎛️ 新增：AI 解析深度控制台
                st.markdown("##### 🎛️ AI 解析深度引擎")
                parse_level = st.radio(
                    "请选择知识蒸馏模式：", 
                    ["🔥 极简学霸模式 (精炼考点 + 拔高难题)", "📖 详尽保姆模式 (完整推导 + 覆盖全知识点题组)"],
                    label_visibility="collapsed"
                )
                
                if not selected_indices:
                    st.button("🚀 请先勾选图片", disabled=True, use_container_width=True)
                else:
                    if st.button(f"🚀 按设定深度解析选图", type="primary", use_container_width=True):
                        if len(selected_indices) < 1: 
                            st.error("至少选择一张图")
                        else:
                            with st.spinner(f"⏳ 正在启动大模型视觉引擎 ({parse_level[:6]})..."):
                                
                                # 1. 准备大模型 Context (多图上传)
                                select_bytes_list = [st.session_state.wb_images[i]["bytes"] for i in selected_indices]
                                select_names = [st.session_state.wb_images[i]["name"] for i in selected_indices]
                                final_filename = f"Merged_{time.strftime('%m%d_%H%M')}.jpg"
                                
                                # 2. 纵向拼接原图 (用于最终归档)
                                stitched_bytes = stitch_images_vertically(select_bytes_list)
                                
                                # 3. 调用 main.py (需要稍微修改 process_image_to_dict 支持多图 temp 路径)
                                # 这里我为了稳定直接用 app.py 内置的多图逻辑调用答疑室的底层
                                temp_paths = []
                                messages = [{"role": "user", "content": []}]
                                for idx, b in enumerate(select_bytes_list):
                                    p = f"temp_stitch_{idx}.jpg"
                                    with open(p, "wb") as f: f.write(b)
                                    temp_paths.append(p)
                                    messages[0]["content"].append({"image": f"file://{os.path.abspath(p)}"})
                                # 核心 Prompt：明确指示这是完整的一页笔记
                                # 核心 Prompt：用绝对严厉的语气和模板，锁定 JSON 输出格式
                                # 🧠 动态核心逻辑：根据用户选择生成不同的教学指令
                                if "极简学霸" in parse_level:
                                    level_prompt = """
【解析深度要求】：极简拔高模式。
1. analysis字段：请用最精炼的语言提炼核心考点，直接点出破题的“题眼”和易错坑点，完全跳过基础的加减乘除推导过程。
2. exercise字段：不要简单的同类题。请生成 1-2 道难度极高、包含多知识点交汇的“压轴级变式题”（需附带答案详解）。"""
                                else:
                                    level_prompt = """
【解析深度要求】：详尽保姆模式。
1. analysis字段：请提供极其详尽、保姆级的知识推导过程。把每一步的逻辑依据（用了什么定理、公式）都详细写出来，确保初学者能看懂。
2. exercise字段：不要只生成一道题。请生成一个“巩固题组”（至少 3 道题目），难度从易到难递进，必须完整覆盖图片中涉及的所有核心知识点（需附带答案详解）。"""

                                # 🛡️ 架构师级合并 Prompt：动态教学指令 + 铁腕 JSON 格式与双重转义锁
                                prompt_text = f"""这是一道跨越了多页的高难题目或完整笔记。请结合以上所有图片的内容，建立整体上下文逻辑，进行精准的解析。
                                
{level_prompt}

⚠️【极度重要：数学公式渲染与 JSON 转义铁律】：
1. 你的所有输出都将被前端 Markdown 引擎渲染，请必须使用 LaTeX 语法编写数学公式。
2. 行内公式必须用单个 $ 包裹（例如 $x^2$），独立行公式用 $$ 包裹，且 $ 与公式内容之间【绝对不能有任何空格】！
3. 🚨【致命警告】：由于你的输出会被解析为 JSON，所有的 LaTeX 反斜杠必须进行【双重转义】！
   👉 必须写成：\\\\frac、\\\\leq、\\\\sqrt、\\\\int、\\\\partial
   ❌ 绝对不能写成：\\frac、\\leq、\\sqrt、\\int、\\partial
   如果不双重转义，前端渲染将彻底崩溃！

【极度重要格式警告】：你是一个无情的 API 接口，你必须、且只能输出一个合法的 JSON 字典对象！绝对不要包含任何开头问候语、结尾解释！绝对不要使用 Markdown 标题！
请你严格按照以下 JSON 模板输出，填入对应的内容：
{{
    "recognition": "在这里填入题目的完整文本识别内容",
    "latex": "在这里填入推导过程的核心 LaTeX 公式代码",
    "analysis": "在这里填入符合【解析深度要求】的解析文本（支持 Markdown 排版）",
    "exercise": "在这里填入符合【解析深度要求】的变式题组（支持 Markdown 排版）",
    "mindmap": "在这里提取出三个核心关键词（用逗号分隔）"
}}"""
                                messages[0]["content"].append({"text": prompt_text})

                                try:
                                    resp = MultiModalConversation.call(model='qwen-vl-plus', messages=messages)
                                    for p in temp_paths: 
                                        if os.path.exists(p): os.remove(p)
                                    
                                    if resp.status_code == 200:
                                        raw_text = resp.output.choices[0].message.content[0]['text']
                                        
                                        # 🛡️ 架构师级鲁棒性优化：暴力提取 JSON，无视大模型的废话
                                        import json
                                        start_idx = raw_text.find('{')
                                        end_idx = raw_text.rfind('}')
                                        
                                        if start_idx != -1 and end_idx != -1:
                                            json_str = raw_text[start_idx:end_idx+1]
                                            try:
                                                # 🛡️ 防御 1：尝试宽容模式解析
                                                try:
                                                    result_dict = json.loads(json_str, strict=False)
                                                except json.JSONDecodeError:
                                                    # 🛡️ 防御 2：暴力修复 LaTeX 反斜杠惹的祸！
                                                    fixed_str = json_str.replace('\\', '\\\\')
                                                    fixed_str = fixed_str.replace('\\\\n', '\\n').replace('\\\\"', '\\"')
                                                    result_dict = json.loads(fixed_str, strict=False)
                                                
                                                # 存储结果
                                                st.session_state.wb_merged_result = {
                                                    "filename": final_filename,
                                                    "image_bytes": stitched_bytes, 
                                                    "data": result_dict,
                                                    "raw_names": select_names
                                                }
                                                st.success("✅ 多图跨页解析成功！已整理为完整一页。下方查看结果。")
                                                
                                            except Exception as e:
                                                st.error(f"❌ JSON 格式严重损坏: {str(e)} \n\n大模型原话：\n\n{raw_text}")
                                        else:
                                            st.error(f"❌ 大模型完全没有输出 JSON 格式。大模型原话：\n\n{raw_text}")
                                    else:
                                        st.error(f"API 错误: {resp.message}")
                                except Exception as e:
                                    st.error(f"❌ 解析失败: {str(e)}")
                                    for p in temp_paths: 
                                        if os.path.exists(p): os.remove(p)

        # ================= 解析结果归档区 (展示合并后的结果) =================
        if st.session_state.wb_merged_result:
            st.divider()
            res = st.session_state.wb_merged_result
            st.subheader(f"📝 本次跨页合并解析结果: `{res['filename']}`")
            st.caption(f"由原文件 `{' + '.join(res['raw_names'])}` 整合而来。")
            
            with st.container(border=True):
                c_del_res = st.empty()
                if c_del_res.button("❌ 移出合并结果", type="secondary"):
                    st.session_state.wb_merged_result = None; st.rerun()
                st.divider()
                
                c_img, c_interact = st.columns([1, 1.4])
                with c_img:
                    st.image(res["image_bytes"], use_container_width=True) # 展示纵向拼接后的长图
                with c_interact:
                    data = res["data"]
                    with st.expander("💡 完整核心考点与 AI 解析", expanded=False): st.markdown(data.get("analysis", "解析失败"))
                    with st.expander("🎯 举一反三变式题 (基于完整题目生成)", expanded=False): st.info(data.get("exercise", "变式题失败"))
                    
                    st.markdown("---")
                    st.markdown("##### ✍️ 终极知识库归档与注记定制")
                    with st.form(key=f"save_form_merged"):
                        # 使用三级目录布局 (横向滚动 CSS 已注入)
                        c_t, c_m, c_s, c_d = st.columns([1.5, 1.5, 1.5, 1.5])
                        record_type_label = c_t.radio("类型", ["🚨 错题陷阱", "📚 知识总结"], horizontal=True, key="m_type")
                        db_record_type = "error" if "错题" in record_type_label else "note"
                        
                        main_cat_ui = c_m.text_input("📚 一级目录", placeholder="如: 大一上", key="m_cat1")
                        sub_cat_ui = c_s.text_input("📂 二级目录", placeholder="如: 高数", key="m_cat2")
                        detail_cat_ui = c_d.text_input("📄 三级目录(可选)", placeholder="如: 跨页错题", key="m_cat3")
                        custom_tags_ui = st.text_input("🏷️ 自定义标签", placeholder="期末重难点")
                        wb_anno_ui = st.text_area("在此写下你的专属最终注记 (可选)：", height=120)
                        # 📸 新增：图片注记上传组件
                        anno_img_ui = st.file_uploader("📸 附加手写推导/错题截图作为注记 (可选)", type=["jpg", "png", "jpeg"], key="anno_img_merged")

                        if st.form_submit_button("📁 永久存入我的专属复习空间"):
                            # 提取上传的图片字节流
                            anno_bytes = anno_img_ui.getvalue() if anno_img_ui else None
                            if main_cat_ui.strip() and sub_cat_ui.strip():
                                final_sub_cat = sub_cat_ui.strip()
                                if detail_cat_ui.strip(): final_sub_cat = f"{sub_cat_ui.strip()} / {detail_cat_ui.strip()}"
                                
                                # 存入数据库 (注意存图的是 stitched_bytes，data 是合并后的 data)
                                cat_id = db.add_category(username, main_cat_ui.strip(), final_sub_cat)
                                db.save_note_to_db(username, cat_id, res['filename'], res['image_bytes'], data, db_record_type, custom_tags_ui, wb_anno_ui, anno_bytes)
                                clear_db_cache(); st.session_state.wb_merged_result = None # 💥 保存后清除缓存和合并结果
                                st.success(f"已作为完整一页保存至 [{main_cat_ui.strip()} - {final_sub_cat}]！")
                                # 同时清空已被选中的图片，优化体验 (根据索引删除，需要反向删)
                                st.rerun()
                            else: st.error("目录不能为空！")

    # ================= 模式 B：复习空间 (支持横向公式滚动) =================
    elif app_mode == "📚 复习空间":
        st.title("📚 我的专属复习空间")
        st.markdown("每一道题（包括多页合并题）都是一张独立的卡片，支持**三级目录展示**与**公式横向滚动**。")
        
        categories = fetch_categories(username)
        if not categories: st.info("知识库空空如也，快去工作台解析归档吧！")
        else:
            st.caption("🎯 精准逐级检索 (已自动聚合重复目录)")
        
        # 将屏幕分为四个列：三级下拉框 + 一个删除按钮
        col1, col2, col3, col_del = st.columns([2, 2, 2, 1])
        
        # 1. 🧠 核心重构：安全解析目录树
        parsed_cats = []
        for c in categories:
            m_cat = c['main_cat'].strip()
            s_raw = c['sub_cat']
            
            # 巧妙拆解：把带 '/' 的拆成二级和三级
            if '/' in s_raw:
                parts = s_raw.split('/', 1)
                l2 = parts[0].strip()
                l3 = parts[1].strip()
            else:
                l2 = s_raw.strip()
                l3 = "基础考点"  # 容错机制：如果没有斜杠，默认归入此处
                
            parsed_cats.append({"id": c['id'], "l1": m_cat, "l2": l2, "l3": l3})
            
        # 2. 📚 级联第一层：学科
        l1_list = list(set([item['l1'] for item in parsed_cats]))
        with col1:
            sel_l1 = st.selectbox("📚 学科", l1_list)
            
        # 3. 📖 级联第二层：章节 (跟随第一层动态变化)
        l2_list = list(set([item['l2'] for item in parsed_cats if item['l1'] == sel_l1]))
        with col2:
            sel_l2 = st.selectbox("📖 章节", l2_list)
            
        # 4. 📝 级联第三层：考点 (跟随第一、二层动态变化)
        l3_list = list(set([item['l3'] for item in parsed_cats if item['l1'] == sel_l1 and item['l2'] == sel_l2]))
        with col3:
            sel_l3 = st.selectbox("📝 考点", l3_list)
            
        # 5. 🛡️ 自动聚合重复目录：找出所有符合这三个名字的底层 ID
        target_ids = [item['id'] for item in parsed_cats if item['l1'] == sel_l1 and item['l2'] == sel_l2 and item['l3'] == sel_l3]
        
        # 6. ⚠️ 批量删除逻辑
        with col_del:
            st.write("") # 占位换行，让按钮和旁边的选择框在同一水平线
            st.write("")
            if st.button("⚠️ 删除", type="secondary"):
                for t_id in target_ids:
                    db.delete_category_and_notes(t_id, username) # 循环干掉所有同名的重复空壳
                clear_db_cache()
                st.rerun()
                
        # 7. 🚀 批量拉取聚合笔记
        notes = []
        for t_id in target_ids:
            # 把所有重复目录下的笔记拼接在一起，完美解决你的痛点！
            notes.extend(fetch_notes(username, t_id))
            
        # ====== 下面正常接你循环展示卡片的逻辑： for note in notes: ======
            # ... 复习空间的检索过滤和卡片展示逻辑保持不变 ...
            # 💡 (关键：由于 CSS 已注入，复习空间里的 KaTeX 公式会自动拥有横向滚动条！)
            
            # --- 精准检索控制台 ---
            all_tags = set()
            for n in notes:
                if n['tags']:
                    for t in n['tags'].split(','):
                        if t.strip(): all_tags.add(t.strip())
                if n['custom_tags']:
                    for t in n['custom_tags'].split(','):
                        if t.strip(): all_tags.add(t.strip())
            
            with st.expander("🔍 精准检索过滤面板", expanded=False):
                c_f1, c_f2, c_f3 = st.columns([1.5, 1, 1.5])
                filter_type = c_f1.selectbox("类型", ["全部内容", "🚨 仅看错题陷阱", "📚 仅看笔记总结"])
                filter_star = c_f2.checkbox("⭐ 核心重难点"); filter_confused = c_f2.checkbox("❓ 尚未完全掌握")
                filter_tags = c_f3.multiselect("🏷️ 标签筛选", list(all_tags))
                
            filtered_notes = []
            for n in notes:
                if filter_type == "🚨 仅看错题陷阱" and n['record_type'] != 'error': continue
                if filter_type == "📚 仅看笔记总结" and n['record_type'] != 'note': continue
                if filter_star and n['is_starred'] == 0: continue
                if filter_confused and n['is_confused'] == 0: continue
                if filter_tags:
                    combined_tags = [t.strip() for t in (n['tags'] + "," + n['custom_tags']).split(',')]
                    if not any(t in combined_tags for t in filter_tags): continue
                filtered_notes.append(n)
            st.caption(f"🚀 检索完成：当前展示 **{len(filtered_notes)}** 条符合条件的收录记录。")
            
            for idx, note in enumerate(filtered_notes):
                with st.container(border=True):
                    c_h, c_u, c_d, c_del = st.columns([6, 1, 1, 1])
                    type_icon = "🚨 错题" if note['record_type'] == 'error' else "📚 笔记"
                    c_h.markdown(f"**[{type_icon}]** | AI标签: `{note['tags']}` | 自定义: `{note['custom_tags']}`")
                    
                    if c_u.button("🔼 上移", key=f"up_{note['id']}", disabled=(idx == 0)):
                        prev_note = filtered_notes[idx-1]
                        db.swap_notes_order(note['id'], note['sort_order'], prev_note['id'], prev_note['sort_order'], username)
                        clear_db_cache(); st.rerun() 
                    if c_d.button("🔽 下调", key=f"down_{note['id']}", disabled=(idx == len(filtered_notes)-1)):
                        next_note = filtered_notes[idx+1]
                        db.swap_notes_order(note['id'], note['sort_order'], next_note['id'], next_note['sort_order'], username)
                        clear_db_cache(); st.rerun()
                    if c_del.button("❌ 删卡", key=f"del_{note['id']}"):
                        db.delete_saved_note(note['id'], username)
                        clear_db_cache(); st.rerun()
                    st.divider()
                    
                    c_img, c_content = st.columns([1, 1.5])
                    with c_img:
                        st.image(note['image_bytes'], use_container_width=True) # 这里展示的可能是当初合并的长图
                    with c_content:
                        # 公式由于 CSS 注入，会自动支持横向滚动
                        with st.expander("💡 题目还原与 AI 解析", expanded=False):
                            st.markdown("###### LaTeX 还原")
                            st.markdown(note['latex']) # 公式溢出会被 CSS 秒杀
                            st.markdown("---")
                            st.markdown("###### AI 详尽解析")
                            st.markdown(note['analysis'])
                        if note['record_type'] == 'error':
                            with st.expander("🎯 举一反三变式题", expanded=False): st.info(note['exercise'])
                            
                        # ... 其余更新状态的代码保持不变 ...
                        with st.expander("🙋 召唤复习助教 (沉浸式答疑)", expanded=False):
                            # 这里我留一个接口：如果你要提问，可以把多张图一起发给大模型。为了稳定我暂时用旧代码
                            # tutor_img_list = st.file_uploader("🖼️ 附带相关截图 (可选，支持多张)", type=["jpg", "png", "jpeg"], key=f"db_tutor_img_{note['id']}", accept_multiple_files=True)
                            tutor_q_db = st.text_input("💬 你的疑问：", key=f"db_tutor_q_{note['id']}")
                            if st.button("🚀 发送给助教", key=f"db_tutor_btn_{note['id']}"):
                                with st.spinner("思考中..."):
                                    # 注意：如果是合并题，我们要把合并的长图bytes传给AI，建立上下文
                                    reply_db = call_ai_tutor_multi([note['image_bytes']], tutor_q_db)
                                    st.success("✅ 助教回复：")
                                    st.markdown(reply_db)
                                    # 👇 就是把下面这 3 行代码，直接粘贴在 st.success 或 st.markdown 的下面！
                                with st.expander("📋 点此一键无损复制（用于粘贴到你的专属注记，绝对不会乱码！）"):
                                    st.info("💡 必须点击下方黑框右上角的【复制（Copy）】小图标！千万不要用鼠标拖拽文字！")
                                    st.code(reply_db, language="markdown")

                        st.markdown("---")
                        st.markdown("##### ✍️ 我的专属思考与注记")
                        
                        # ================= 1. 优雅阅读区 (平时看着爽) =================
                        if note.get('user_annotation'):
                            st.info("💡 当前文字注记：")
                            # 直接用 markdown 渲染，这样复制进来的公式就能完美显示！
                            st.markdown(note['user_annotation']) 
                            
                        # 如果数据库里有手写图片注记，就在这里展示出来
                        if note.get('annotation_image_bytes'):
                            st.image(note['annotation_image_bytes'], caption="📸 我的手写补充注记", use_container_width=True)
                            
                        # ================= 2. 沉浸式编辑区 (点开折叠面板修改) =================
                        with st.expander("✏️ 展开编辑注记 / 补充手写图片 / 更改状态", expanded=False):
                            with st.form(key=f"anno_form_{note['id']}"):
                                c_s1, c_s2 = st.columns(2)
                                is_starred_ui_db = c_s1.checkbox("⭐ 设为核心重难点", value=bool(note['is_starred']))
                                is_confused_ui_db = c_s2.checkbox("❓ 尚未完全掌握", value=bool(note['is_confused']))
                                custom_tags_ui_db = st.text_input("🏷️ 更新自定义标签", value=note['custom_tags'], key=f"ct_db_{note['id']}")
                                
                                # 💡 巨无霸输入框！高度拉满到 400，再长的内容也放得下
                                anno_ui_db = st.text_area("在此粘贴或修改你的文字注记：", value=note['user_annotation'], key=f"anno_db_{note['id']}", height=400)
                                
                                # 📸 支持多选并自动拼接的长图上传器！
                                update_imgs_ui = st.file_uploader("📸 补充手写推导/截图 (支持多选，自动拼接)", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key=f"up_img_db_{note['id']}")
                                
                                if st.form_submit_button("💾 保存所有更新"):
                                    new_img_bytes = None
                                    if update_imgs_ui:
                                        img_bytes_list = [img.getvalue() for img in update_imgs_ui]
                                        new_img_bytes = stitch_images_vertically(img_bytes_list)
                                        
                                    # 🧠 接收从底层穿透出来的真实反馈
                                    db_result = db.update_note_metadata(int(note['id']), username, anno_ui_db, 1 if is_starred_ui_db else 0, 1 if is_confused_ui_db else 0, custom_tags_ui_db, new_img_bytes)
                                    
                                    if db_result == "SUCCESS":
                                        st.cache_data.clear() 
                                        try:
                                            clear_db_cache()
                                        except:
                                            pass
                                        st.success("✅ 注记已永久存入数据库！正在强制刷新数据...")
                                        import time
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        # 💣 直接把底层的真凶砸在网页红框里！
                                        st.error(f"❌ 数据库底层报错了！真凶是：{db_result}")

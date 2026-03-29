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
            
    prompt_suffix = "请结合以上所有图片的内容，建立整体逻辑，输出精准且结构清晰的解答。如果是跨页题目，请拼接完整后解析。"
    messages[0]["content"].append({"text": f"{question or '请详细解释一下核心推导步骤。'}\n\n{prompt_suffix}"})
    
    try:
        # 为了多图理解，必须用 dashscope 官方 SDK 调用 (main.py 的 process 改成了支持多图模式)
        resp = MultiModalConversation.call(model='qwen-vl-plus', messages=messages)
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
            with c_op2:
                if not selected_indices:
                    st.button("🚀 请先勾选图片", disabled=True, use_container_width=True)
                else:
                    if st.button(f"🚀 合并解析选中的 {len(selected_indices)} 张图", type="primary", use_container_width=True):
                        if len(selected_indices) < 1: st.error("至少选择一张图")
                        else:
                            with st.spinner("⏳ 正在进行多图联合上下文理解与高精度提炼 (跨页整合版)..."):
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
                                messages[0]["content"].append({"text": "这是一道跨越了多页的高难题目或完整笔记。请结合以上所有图片的内容，建立整体上下文逻辑，输出精准的整体 LaTeX 原文还原、详尽的分析、以及整理出一页完美的结构化笔记。一定要看全所有图，给出一个完整的 JSON 字典（必须包含 recognition, latex, analysis, exercise, mindmap 字段，且符合之前要求的 JSON 格式）。"})

                                try:
                                    resp = MultiModalConversation.call(model='qwen-vl-plus', messages=messages)
                                    for p in temp_paths: 
                                        if os.path.exists(p): os.remove(p)
                                    
                                    if resp.status_code == 200:
                                        raw_text = resp.output.choices[0].message.content[0]['text']
                                        # 解析 JSON (复用以前的逻辑)
                                        import json
                                        json_str = raw_text.replace("```json", "").replace("```", "").strip()
                                        result_dict = json.loads(json_str)
                                        
                                        # 存储结果
                                        st.session_state.wb_merged_result = {
                                            "filename": final_filename,
                                            "image_bytes": stitched_bytes, # 存的是拼接后的长图
                                            "data": result_dict,
                                            "raw_names": select_names
                                        }
                                        st.success("✅ 多图跨页解析成功！已整理为完整一页。下方查看结果。")
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
                        wb_anno_ui = st.text_area("在此写下你的专属最终注记：", height=120)
                        
                        if st.form_submit_button("📁 永久存入我的专属复习空间"):
                            if main_cat_ui.strip() and sub_cat_ui.strip():
                                final_sub_cat = sub_cat_ui.strip()
                                if detail_cat_ui.strip(): final_sub_cat = f"{sub_cat_ui.strip()} / {detail_cat_ui.strip()}"
                                
                                # 存入数据库 (注意存图的是 stitched_bytes，data 是合并后的 data)
                                cat_id = db.add_category(username, main_cat_ui.strip(), final_sub_cat)
                                db.save_note_to_db(username, cat_id, res['filename'], res['image_bytes'], data, db_record_type, custom_tags_ui, wb_anno_ui)
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
            cat_options = {f"{c['main_cat']} ➡️ {c['sub_cat']}": c['id'] for c in categories}
            c_cat, c_del_dir = st.columns([4, 1])
            selected_cat_name = c_cat.selectbox("📂 选择目录：", list(cat_options.keys()))
            selected_cat_id = cat_options[selected_cat_name]
            
            if c_del_dir.button("⚠️ 删除该目录", type="secondary"):
                db.delete_category_and_notes(selected_cat_id, username)
                clear_db_cache(); st.rerun()
            
            notes = fetch_notes(username, selected_cat_id)
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

                        st.markdown("---")
                        st.markdown("##### ✍️ 我的专属思考与注记")
                        with st.form(key=f"anno_form_{note['id']}"):
                            c_s1, c_s2 = st.columns(2)
                            is_starred_ui_db = c_s1.checkbox("⭐ 设为核心重难点", value=bool(note['is_starred']))
                            is_confused_ui_db = c_s2.checkbox("❓ 尚未完全掌握", value=bool(note['is_confused']))
                            custom_tags_ui_db = st.text_input("🏷️ 更新自定义标签", value=note['custom_tags'], key=f"ct_db_{note['id']}")
                            anno_ui_db = st.text_area("在此写下你的注记：", value=note['user_annotation'], key=f"anno_db_{note['id']}", height=100)
                            if st.form_submit_button("💾 更新卡片状态"):
                                db.update_note_metadata(note['id'], username, anno_ui_db, 1 if is_starred_ui_db else 0, 1 if is_confused_ui_db else 0, custom_tags_ui_db)
                                clear_db_cache(); st.success("状态已保存！"); st.rerun()

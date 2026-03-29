import streamlit as st
import os
import subprocess
import concurrent.futures
import time
import dashscope
from dashscope import MultiModalConversation
from main import process_image_to_dict
import database as db

st.set_page_config(layout="wide", page_title="AI 智能学习 OS")

# ================= 👑 提速引擎：云端数据缓存 (传引用版) =================
# 将 @st.cache_data 替换为 @st.cache_resource ！！
@st.cache_resource(ttl=3600)
def fetch_categories(username):
    return db.get_categories(username)

@st.cache_resource(ttl=3600)
def fetch_notes(username, category_id):
    return db.get_saved_notes(username, category_id)

def clear_db_cache():
    """当用户对数据进行增删改时，调用此函数清除旧缓存"""
    fetch_categories.clear()
    fetch_notes.clear()
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

# ================= 辅助函数：调用多模态答疑室 =================
def call_ai_tutor(image_bytes, question):
    temp_path = "temp_tutor.jpg"
    messages = [{"role": "user", "content": []}]
    if image_bytes:
        with open(temp_path, "wb") as f: f.write(image_bytes)
        messages[0]["content"].append({"image": f"file://{os.path.abspath(temp_path)}"})
    messages[0]["content"].append({"text": question or "请详细解释一下这张图里的核心推导步骤。"})
    try:
        resp = MultiModalConversation.call(model='qwen-vl-plus', messages=messages)
        if os.path.exists(temp_path): os.remove(temp_path)
        if resp.status_code == 200:
            return resp.output.choices[0].message.content[0]['text']
        return f"API 错误: {resp.message}"
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        return f"发生未知错误: {str(e)}"

# ================= 1. 极简身份认证 =================
VALID_USERS = {"huilong": "gaoling2026", "teacher": "ruc123"}

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "username": ""})

if not st.session_state["logged_in"]:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.title("🔐 高瓴 AI 学习 OS (Beta)")
        st.markdown("#### 你的专属多模态知识蒸馏平台")
        st.divider()
        input_user = st.text_input("👤 用户名 (Username)")
        input_pwd = st.text_input("🔑 密码 (Password)", type="password")
        if st.button("登录进入系统", type="primary", use_container_width=True):
            if input_user in VALID_USERS and VALID_USERS[input_user] == input_pwd:
                st.session_state.update({"logged_in": True, "username": input_user})
                st.rerun() 
            else:
                st.error("❌ 用户名或密码错误！")

# ================= 2. 登录成功后的主系统 =================
else:
    if "db_inited" not in st.session_state:
        db.init_db()
        st.session_state["db_inited"] = True
    username = st.session_state["username"]

    with st.sidebar:
        st.success(f"👋 欢迎回来, **{username}**!")
        if st.button("🚪 退出登录", use_container_width=True):
            st.session_state.update({"logged_in": False, "username": ""})
            st.rerun()
            
        st.divider()
        st.header("🧭 系统导航")
        app_mode = st.radio("请选择模式：", ["🔮 知识提取工作台", "📚 Notion 式复习空间"])
        st.divider()
        st.info("💡 **系统提示**：云端数据提速引擎已开启，缓存命中率 100%。")

    # ================= 模式 A：知识提取工作台 =================
    if app_mode == "🔮 知识提取工作台":
        st.title("🔮 AI 知识提取工作台")
        st.markdown("批量上传新笔记，系统将自动提炼，并让你在保存前**即时召唤助教**、**写下专属注记**！")
        
        if "multi_results" not in st.session_state:
            st.session_state.multi_results = []
            st.session_state.processed_sigs = set()

        for i, res in enumerate(st.session_state.multi_results): res["page_num"] = i + 1

        uploaded_files = st.file_uploader("📥 选择笔记图片（可随时追加）", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        new_files = [f for f in uploaded_files if f"{f.name}_{f.size}" not in st.session_state.processed_sigs] if uploaded_files else []
        
        c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 1])
        with c_btn1:
            if not uploaded_files: analyze_btn = st.button("🚀 请先上传图片", disabled=True, use_container_width=True)
            elif len(new_files) == 0: analyze_btn = st.button("✅ 已全部解析", disabled=True, use_container_width=True)
            else: analyze_btn = st.button(f"🚀 极速解析 {len(new_files)} 张图片", type="primary", use_container_width=True)
        with c_btn2:
            if st.button("🗑️ 清空工作台", use_container_width=True):
                st.session_state.multi_results = []; st.session_state.processed_sigs = set(); st.rerun()
        
        # 稳健串行解析 (防 API 熔断)
        if analyze_btn:
            start_idx = len(st.session_state.multi_results)
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, file in enumerate(new_files):
                status_text.markdown(f"**⏳ 正在处理第 {i+1}/{len(new_files)} 张图片: `{file.name}`...**")
                try:
                    file_bytes = file.getvalue()
                    file_sig = f"{file.name}_{file.size}"
                    temp_path = f"temp_{file.name}"
                    with open(temp_path, "wb") as f: f.write(file_bytes)
                    
                    result_data = process_image_to_dict(temp_path)
                    if os.path.exists(temp_path): os.remove(temp_path)
                        
                    if result_data:
                        st.session_state.multi_results.append({
                            "page_num": start_idx + i + 1, "filename": file.name, "data": result_data,
                            "image_bytes": file_bytes, "sig": file_sig
                        })
                        st.session_state.processed_sigs.add(file_sig)
                    time.sleep(2) 
                except Exception as e:
                    st.error(f"❌ 解析 `{file.name}` 时发生错误: {str(e)}")
                    if os.path.exists(temp_path): os.remove(temp_path)
                progress_bar.progress((i + 1) / len(new_files))
            status_text.success("✅ 解析任务结束！请往下滚动查看结果。")
            st.rerun()

        # 解析结果展示区
        if st.session_state.multi_results:
            st.divider()
            st.subheader("📝 本次解析结果（可即时定制）")
            for i, res in enumerate(st.session_state.multi_results):
                with st.container(border=True):
                    c_header, c_del = st.columns([6, 1])
                    c_header.markdown(f"**📄 第 {res['page_num']} 页: `{res['filename']}`** | AI标签: `{res['data'].get('tags', '未提取')}`")
                    if c_del.button("❌ 移出工作台", key=f"wb_del_{i}"):
                        deleted_item = st.session_state.multi_results.pop(i)
                        st.session_state.processed_sigs.remove(deleted_item["sig"])
                        st.rerun()
                    st.divider()
                    
                    c_img, c_interact = st.columns([1, 1.4])
                    with c_img:
                        st.image(res["image_bytes"], use_container_width=True)
                    with c_interact:
                        data = res["data"]
                        with st.expander("💡 核心考点与 AI 解析", expanded=False): st.markdown(data.get("analysis", "解析失败"))
                        with st.expander("🎯 举一反三变式题", expanded=False): st.info(data.get("exercise", "变式题失败"))
                        
                        st.markdown("---")
                        st.markdown("##### 🙋 召唤助教 (遇事不决，截图提问)")
                        with st.container():
                            tutor_img_ui = st.file_uploader("🖼️ 贴入讲义截图 (可选)", type=["jpg", "png", "jpeg"], key=f"wb_tutor_img_{i}")
                            tutor_q_ui = st.text_input("💬 你的疑问：", key=f"wb_tutor_q_{i}")
                            if st.button("🚀 发送给助教", key=f"wb_tutor_btn_{i}"):
                                with st.spinner("思考中..."):
                                    img_b = tutor_img_ui.getvalue() if tutor_img_ui else None
                                    reply = call_ai_tutor(img_b, tutor_q_ui)
                                    st.success("✅ 助教回复：")
                                    st.markdown(reply)
                        
                        st.markdown("---")
                        st.markdown("##### ✍️ 知识库归档与注记定制")
                        with st.form(key=f"save_form_{i}"):
                            c_t, c_m, c_s = st.columns([1.5, 2, 2])
                            record_type_label = c_t.radio("类型", ["🚨 错题陷阱", "📚 知识总结"], horizontal=True)
                            db_record_type = "error" if "错题" in record_type_label else "note"
                            
                            main_cat_ui = c_m.text_input("主分类", placeholder="如: 大一上", key=f"m_{i}")
                            sub_cat_ui = c_s.text_input("子分类", placeholder="如: 高数微积分", key=f"s_{i}")
                            custom_tags_ui = st.text_input("🏷️ 自定义标签 (逗号分隔)", placeholder="如：期末必考")
                            wb_anno_ui = st.text_area("在此写下你的专属注记：", height=120)
                            
                            if st.form_submit_button("📁 永久存入我的专属复习空间"):
                                if main_cat_ui.strip() and sub_cat_ui.strip():
                                    cat_id = db.add_category(username, main_cat_ui.strip(), sub_cat_ui.strip())
                                    db.save_note_to_db(username, cat_id, res['filename'], res['image_bytes'], data, db_record_type, custom_tags_ui, wb_anno_ui)
                                    clear_db_cache() # 💥 魔法：通知缓存，云端数据更新了，请下次重新拉取！
                                    st.success(f"已保存至 [{main_cat_ui} - {sub_cat_ui}]！")
                                else:
                                    st.error("分类名不能为空！")

    # ================= 模式 B：Notion 式复习空间 =================
    elif app_mode == "📚 Notion 式复习空间":
        st.title("📚 我的专属复习空间")
        st.markdown("每一道题都是一张独立的卡片，支持**自由排序**与**认知状态追踪**。")
        
        # 👑 提速：直接从内存缓存中读取分类，零延迟！
        categories = fetch_categories(username)
        
        if not categories:
            st.info("您的知识库空空如也，快去【知识提取工作台】解析并归档吧！")
        else:
            cat_options = {f"{c['main_cat']} ➡️ {c['sub_cat']}": c['id'] for c in categories}
            c_cat, c_del_dir = st.columns([4, 1])
            selected_cat_name = c_cat.selectbox("📂 选择要复习的分类目录：", list(cat_options.keys()))
            selected_cat_id = cat_options[selected_cat_name]
            
            if c_del_dir.button("⚠️ 删除该目录", type="secondary"):
                db.delete_category_and_notes(selected_cat_id, username)
                clear_db_cache() # 💥 触发数据库更新，清空缓存
                st.rerun()
            
            # 👑 提速：直接从内存缓存中读取图片和文字，告别跨洋下载的卡顿！
            notes = fetch_notes(username, selected_cat_id)
            
            # 精准知识检索控制台
            all_tags = set()
            for n in notes:
                if n['tags']:
                    for t in n['tags'].split(','):
                        if t.strip(): all_tags.add(t.strip())
                if n['custom_tags']:
                    for t in n['custom_tags'].split(','):
                        if t.strip(): all_tags.add(t.strip())
            
            with st.expander("🔍 展开精准检索过滤面板", expanded=False):
                c_f1, c_f2, c_f3 = st.columns([1.5, 1, 1.5])
                filter_type = c_f1.selectbox("类型", ["全部内容", "🚨 仅看错题陷阱", "📚 仅看笔记总结"])
                filter_star = c_f2.checkbox("⭐ 核心重难点")
                filter_confused = c_f2.checkbox("❓ 尚未完全掌握")
                filter_tags = c_f3.multiselect("🏷️ 知识点标签筛选", list(all_tags))
                
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
                        clear_db_cache() # 💥 清除旧顺序缓存
                        st.rerun() 
                    if c_d.button("🔽 下调", key=f"down_{note['id']}", disabled=(idx == len(filtered_notes)-1)):
                        next_note = filtered_notes[idx+1]
                        db.swap_notes_order(note['id'], note['sort_order'], next_note['id'], next_note['sort_order'], username)
                        clear_db_cache() # 💥 清除旧顺序缓存
                        st.rerun()
                    if c_del.button("❌ 删卡", key=f"del_{note['id']}"):
                        db.delete_saved_note(note['id'], username)
                        clear_db_cache() # 💥 清除数据缓存
                        st.rerun()
                    
                    st.divider()
                    
                    c_img, c_content = st.columns([1, 1.5])
                    with c_img:
                        st.image(note['image_bytes'], use_container_width=True)
                    with c_content:
                        with st.expander("💡 原文与解析对照", expanded=False):
                            st.markdown(note['recognition'])
                            st.markdown(note['analysis'])
                        if note['record_type'] == 'error':
                            with st.expander("🎯 举一反三变式题", expanded=False): st.info(note['exercise'])
                            
                        with st.expander("🙋 召唤复习助教 (传图提问，攻克硬骨头)", expanded=False):
                            tutor_img_db = st.file_uploader("🖼️ 附带相关截图 (可选)", type=["jpg", "png", "jpeg"], key=f"db_tutor_img_{note['id']}")
                            tutor_q_db = st.text_input("💬 你的疑问：", key=f"db_tutor_q_{note['id']}")
                            if st.button("🚀 发送给助教", key=f"db_tutor_btn_{note['id']}"):
                                with st.spinner("思考中..."):
                                    img_b_db = tutor_img_db.getvalue() if tutor_img_db else None
                                    reply_db = call_ai_tutor(img_b_db, tutor_q_db)
                                    st.success("✅ 助教回复：")
                                    st.markdown(reply_db)

                        st.markdown("---")
                        st.markdown("##### ✍️ 我的专属思考与注记")
                        with st.form(key=f"anno_form_{note['id']}"):
                            c_s1, c_s2 = st.columns(2)
                            is_starred_ui_db = c_s1.checkbox("⭐ 设为核心重难点", value=bool(note['is_starred']))
                            is_confused_ui_db = c_s2.checkbox("❓ 尚未完全掌握", value=bool(note['is_confused']))
                            
                            custom_tags_ui_db = st.text_input("🏷️ 更新自定义标签", value=note['custom_tags'], key=f"ct_db_{note['id']}")
                            anno_ui_db = st.text_area("在此写下你的注记与助教解答：", value=note['user_annotation'], key=f"anno_db_{note['id']}", height=100)
                            
                            if st.form_submit_button("💾 更新卡片状态"):
                                db.update_note_metadata(note['id'], username, anno_ui_db, 1 if is_starred_ui_db else 0, 1 if is_confused_ui_db else 0, custom_tags_ui_db)
                                clear_db_cache() # 💥 清除状态缓存
                                st.success("状态已保存至数据库！")
                                st.rerun()

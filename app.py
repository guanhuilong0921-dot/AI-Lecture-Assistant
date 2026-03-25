import streamlit as st
import os
import subprocess
import concurrent.futures
from main import process_image_to_dict
import database as db

def compile_latex_to_pdf(latex_code, filename="generated_notes"):
    """将 LaTeX 源码编译为 PDF"""
    tex_file = f"{filename}.tex"
    pdf_file = f"{filename}.pdf"
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(latex_code)
    try:
        subprocess.run(["xelatex", "-interaction=nonstopmode", tex_file], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(pdf_file):
            return pdf_file
        return "ERROR_COMPILE"
    except FileNotFoundError:
        return "ERROR_NO_COMPILER"

st.set_page_config(layout="wide", page_title="AI 智能笔记助教")

# ================= 1. 极简身份认证系统 =================
VALID_USERS = {"huilong": "gaoling2026", "teacher": "ruc123"}

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""

if not st.session_state["logged_in"]:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.title("🔐 《数字时代科技》课题系统")
        st.markdown("#### 智能交互式学习平台 - 专属复习空间")
        st.divider()
        input_user = st.text_input("👤 用户名 (Username)")
        input_pwd = st.text_input("🔑 密码 (Password)", type="password")
        if st.button("登录进入系统", type="primary", use_container_width=True):
            if input_user in VALID_USERS and VALID_USERS[input_user] == input_pwd:
                st.session_state["logged_in"] = True
                st.session_state["username"] = input_user
                st.rerun() 
            else:
                st.error("❌ 用户名或密码错误，请重试！")

# ================= 2. 登录成功后的主系统 =================
else:
    db.init_db()
    username = st.session_state["username"]

    with st.sidebar:
        st.success(f"👋 欢迎回来, 尊贵的 **{username}**!")
        if st.button("🚪 退出登录", use_container_width=True):
            st.session_state["logged_in"] = False
            st.session_state["username"] = ""
            st.rerun()
        st.divider()
        st.header("🧭 系统导航")
        app_mode = st.radio("请选择工作模式：", ["🔮 AI 解析工作台", "📚 我的专属错题库"])

    # ================= 模式 A：AI 解析工作台 (全功能满血版) =================
    if app_mode == "🔮 AI 解析工作台":
        st.title("🔮 AI 智能解析工作台")
        st.markdown("批量上传、**多线程极速解析**、自由排序，一键存入错题库或生成 PDF！")
        
        if "multi_results" not in st.session_state:
            st.session_state.multi_results = []
        if "processed_sigs" not in st.session_state:
            st.session_state.processed_sigs = set()

        for i, res in enumerate(st.session_state.multi_results):
            res["page_num"] = i + 1

        col1, col2 = st.columns([1.1, 1.4]) 
        with col1:
            uploaded_files = st.file_uploader("📥 请选择课堂笔记图片", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
            new_files = [f for f in uploaded_files if f"{f.name}_{f.size}" not in st.session_state.processed_sigs] if uploaded_files else []
            
            if not uploaded_files:
                analyze_btn = st.button("🚀 请先上传图片", disabled=True, use_container_width=True)
            elif len(new_files) == 0:
                analyze_btn = st.button("✅ 当前图片已全部解析", disabled=True, use_container_width=True)
            else:
                analyze_btn = st.button(f"🚀 开始多线程解析 {len(new_files)} 张新图片", type="primary", use_container_width=True)
                
            if st.button("🗑️ 清空当前工作台缓存", use_container_width=True):
                st.session_state.multi_results = [] 
                st.session_state.processed_sigs = set() 
                st.rerun()

            st.subheader("🖼️ 原始图文对照")
            for res in st.session_state.multi_results:
                st.divider() 
                st.markdown(f"#### 📄 第 {res['page_num']} 页: `{res['filename']}`")
                st.image(res["image_bytes"], use_container_width=True)

        with col2:
            # --- 满血恢复：多线程并发加速 ---
            if analyze_btn:
                start_idx = len(st.session_state.multi_results)
                with st.spinner(f"🚀 正在施展多线程魔法，同时并发解析 {len(new_files)} 张图片..."):
                    def process_single_file(file, idx):
                        file_bytes = file.getvalue()
                        file_sig = f"{file.name}_{file.size}"
                        temp_img_path = f"temp_{file.name}"
                        with open(temp_img_path, "wb") as f:
                            f.write(file_bytes)
                        result_data = process_image_to_dict(temp_img_path)
                        if os.path.exists(temp_img_path):
                            os.remove(temp_img_path)
                        return {"original_idx": idx, "filename": file.name, "data": result_data, "image_bytes": file_bytes, "sig": file_sig}

                    thread_results = []
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = [executor.submit(process_single_file, file, i) for i, file in enumerate(new_files)]
                        for future in concurrent.futures.as_completed(futures):
                            res = future.result()
                            if res["data"]: thread_results.append(res)
                    
                    thread_results.sort(key=lambda x: x["original_idx"])
                    for i, res in enumerate(thread_results):
                        st.session_state.multi_results.append({
                            "page_num": start_idx + i + 1, "filename": res["filename"], "data": res["data"],
                            "image_bytes": res["image_bytes"], "sig": res["sig"]
                        })
                        st.session_state.processed_sigs.add(res["sig"])
                st.success("✅ 多线程并发解析与持久化完成！")
                st.rerun()

            if st.session_state.multi_results:
                # --- 满血恢复：页面自由排序控制台 ---
                with st.expander("🎛️ 页面排序与删除 (调整顺序后 PDF 也会跟着变)", expanded=False):
                    for i, res in enumerate(st.session_state.multi_results):
                        c_name, c_up, c_down, c_del = st.columns([4, 1, 1, 1])
                        c_name.markdown(f"**第 {res['page_num']} 页**: `{res['filename']}`")
                        if c_up.button("🔼 上移", key=f"up_{i}", disabled=(i == 0)):
                            st.session_state.multi_results[i-1], st.session_state.multi_results[i] = st.session_state.multi_results[i], st.session_state.multi_results[i-1]
                            st.rerun() 
                        if c_down.button("🔽 下移", key=f"down_{i}", disabled=(i == len(st.session_state.multi_results)-1)):
                            st.session_state.multi_results[i+1], st.session_state.multi_results[i] = st.session_state.multi_results[i], st.session_state.multi_results[i+1]
                            st.rerun()
                        if c_del.button("❌ 删除", key=f"del_{i}"):
                            deleted_item = st.session_state.multi_results.pop(i)
                            if deleted_item["sig"] in st.session_state.processed_sigs:
                                st.session_state.processed_sigs.remove(deleted_item["sig"])
                            st.rerun()

                st.markdown("---")
                
                # 展示解析结果与入库表单
                tab_names = [f"第 {res['page_num']} 页" for res in st.session_state.multi_results]
                tabs = st.tabs(tab_names)
                for i, tab in enumerate(tabs):
                    with tab:
                        res = st.session_state.multi_results[i]
                        data = res["data"]
                        st.caption(f"文件名: {res['filename']}")
                        
                        # --- 满血恢复：所有细节面板 ---
                        with st.expander("🔍 识别原文与智能纠错", expanded=True): st.markdown(data.get("recognition", ""))
                        with st.expander("💡 核心考点与易错解析", expanded=True): st.markdown(data.get("analysis", ""))
                        with st.expander("🎯 举一反三：同类变式题", expanded=True): st.info(data.get("exercise", ""))
                        with st.expander("🧠 解题逻辑流向 (Mermaid)", expanded=False): st.code(data.get("mindmap", ""), language="mermaid")
                        with st.expander("📝 标准化 LaTeX 源码", expanded=False): st.code(data.get("latex", ""), language="latex")
                        
                        st.markdown("##### 💾 提取本页精髓至错题库")
                        with st.form(key=f"save_form_{i}"):
                            c_m, c_s, c_btn = st.columns([2, 2, 1])
                            main_cat = c_m.text_input("主分类", placeholder="如: 大一上", key=f"m_{i}")
                            sub_cat = c_s.text_input("子分类", placeholder="如: 线性代数", key=f"s_{i}")
                            submit_save = c_btn.form_submit_button("📁 入库")
                            if submit_save:
                                if main_cat.strip() and sub_cat.strip():
                                    cat_id = db.add_category(username, main_cat.strip(), sub_cat.strip())
                                    db.save_note_to_db(username, cat_id, res['filename'], res['image_bytes'], data)
                                    st.success(f"已永久保存至 [{main_cat} - {sub_cat}]！")
                                else:
                                    st.error("分类名不能为空！")

        # --- 满血恢复：PDF 导出面板 ---
        if st.session_state.multi_results:
            st.markdown("---")
            st.markdown("### 🖨️ 工作台资料按需定制 (PDF导出)")
            export_selections = {}
            for i, res in enumerate(st.session_state.multi_results):
                page_num = res["page_num"]
                st.markdown(f"**📄 第 {page_num} 页 : {res['filename']}**")
                c1, c2, c3, c4 = st.columns(4)
                with c1: inc_rec = st.checkbox("🔍 原文纠错", value=True, key=f"rec_{i}")
                with c2: inc_note = st.checkbox("📝 标椎笔记", value=True, key=f"note_{i}")
                with c3: inc_ana = st.checkbox("💡 考点解析", value=True, key=f"ana_{i}")
                with c4: inc_exe = st.checkbox("🎯 变式题", value=False, key=f"exe_{i}")
                export_selections[page_num] = {"res_data": res, "inc_rec": inc_rec, "inc_note": inc_note, "inc_ana": inc_ana, "inc_exe": inc_exe}
                st.divider()
                
            if st.button("✨ 将当前工作台编译为 PDF", type="primary"):
                with st.spinner("正在定制讲义，请稍候..."):
                    final_latex_code = r"\documentclass[UTF8, a4paper, 12pt]{ctexart}" + "\n" + r"\usepackage{amsmath, amssymb, amsthm, geometry}" + "\n" + r"\geometry{left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm}" + "\n" + r"\title{智能解析讲义}\author{AI-Lecture-Assistant}\date{}\begin{document}\maketitle\tableofcontents\newpage" + "\n"
                    pages_added = 0
                    for page_num, config in export_selections.items():
                        if not any([config["inc_rec"], config["inc_note"], config["inc_ana"], config["inc_exe"]]): continue
                        pages_added += 1
                        final_latex_code += f"\\section{{课堂笔记 - 第 {page_num} 页}}\n"
                        data = config["res_data"]["data"]
                        if config["inc_rec"]: final_latex_code += r"\subsection*{一、 原文识别与纠错}" + "\n" + data.get("recognition", "") + "\n\n"
                        if config["inc_note"]: final_latex_code += r"\subsection*{二、 标准化笔记}" + "\n" + data.get("latex", "") + "\n\n"
                        if config["inc_ana"]: final_latex_code += r"\subsection*{三、 核心考点与解析}" + "\n" + data.get("analysis", "") + "\n\n"
                        if config["inc_exe"]: final_latex_code += r"\subsection*{四、 变式练习题}" + "\n" + data.get("exercise", "") + "\n\n"
                        final_latex_code += r"\newpage" + "\n"
                    final_latex_code += r"\end{document}"
                    
                    if pages_added == 0: st.error("您没有勾选任何内容！")
                    else:
                        pdf_result = compile_latex_to_pdf(final_latex_code, filename="workspace_notes")
                        if pdf_result not in ["ERROR_NO_COMPILER", "ERROR_COMPILE"]:
                            st.success("🎉 PDF 编译成功！")
                            with open(pdf_result, "rb") as f:
                                st.download_button("📥 下载定制讲义", data=f, file_name="Workspace_Notes.pdf", mime="application/pdf")

    # ================= 模式 B：我的专属错题库 =================
    elif app_mode == "📚 我的专属错题库":
        st.title("📚 我的专属复习库")
        st.markdown("安全存放的高价值笔记，一键聚合为期末复习宝典。")
        
        categories = db.get_categories(username)
        if not categories:
            st.info("您还没有保存过错题哦，请先去【AI 解析工作台】解析并保存！")
        else:
            cat_options = {f"{c['main_cat']} ➡️ {c['sub_cat']}": c['id'] for c in categories}
            selected_cat_name = st.selectbox("📂 请选择要复习的目录：", list(cat_options.keys()))
            selected_cat_id = cat_options[selected_cat_name]
            
            notes = db.get_saved_notes(username, selected_cat_id)
            c_info, c_del_dir = st.columns([4, 1])
            c_info.write(f"当前目录下共有 **{len(notes)}** 条收录记录：")
            if c_del_dir.button("⚠️ 删除整个目录", type="secondary"):
                db.delete_category_and_notes(selected_cat_id, username)
                st.rerun()
            
            # --- 逆天功能：一键将整个数据库错题本导出为 PDF ---
            if st.button(f"📄 将当前目录下的 {len(notes)} 道错题打包成 PDF 复习册", type="primary"):
                with st.spinner("正在组装错题本 PDF..."):
                    db_latex_code = r"\documentclass[UTF8, a4paper, 12pt]{ctexart}" + "\n" + r"\usepackage{amsmath, amssymb, amsthm, geometry}" + "\n" + r"\geometry{left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm}" + "\n" + f"\\title{{专属错题本：{selected_cat_name}}}\\author{{{username}}}\\date{{}}\\begin{{document}}\\maketitle\\tableofcontents\\newpage\n"
                    for idx, note in enumerate(notes):
                        db_latex_code += f"\\section{{错题收录 - {idx+1}}}\n"
                        db_latex_code += r"\subsection*{考点解析}" + "\n" + note.get('analysis', '') + "\n\n"
                        db_latex_code += r"\subsection*{变式重测}" + "\n" + note.get('exercise', '') + "\n\n"
                        db_latex_code += r"\newpage" + "\n"
                    db_latex_code += r"\end{document}"
                    
                    pdf_result = compile_latex_to_pdf(db_latex_code, filename="db_error_book")
                    if pdf_result not in ["ERROR_NO_COMPILER", "ERROR_COMPILE"]:
                        st.success("🎉 错题本 PDF 生成完毕！")
                        with open(pdf_result, "rb") as f:
                            st.download_button("📥 下载错题本", data=f, file_name=f"ErrorBook_{username}.pdf", mime="application/pdf")

            for note in notes:
                with st.container():
                    st.divider()
                    c1, c2 = st.columns([1.2, 2])
                    with c1:
                        st.image(note['image_bytes'], use_container_width=True)
                        if st.button("🗑️ 删除此记录", key=f"del_note_{note['id']}"):
                            db.delete_saved_note(note['id'], username)
                            st.rerun()
                    with c2:
                        st.caption(f"入库时间: {note['created_at'][:19]}")
                        with st.expander("🔍 原文识别与纠错", expanded=True): st.markdown(note['recognition'])
                        with st.expander("💡 核心考点与易错解析", expanded=True): st.markdown(note['analysis'])
                        with st.expander("🎯 变式题", expanded=False): st.info(note['exercise'])

import streamlit as st
import os
import subprocess
from main import process_image_to_dict

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
        else:
            return "ERROR_COMPILE"
    except FileNotFoundError:
        return "ERROR_NO_COMPILER"

st.set_page_config(layout="wide", page_title="AI 智能笔记助教")

st.set_page_config(layout="wide", page_title="AI 智能笔记助教")

# ================= 极简用户身份系统 =================
# 这里相当于一个小型的内置数据库，用来校验身份
VALID_USERS = {
    "huilong": "gaoling2026",  # 你的专属管理员账号
    "teacher": "ruc123"        # 留给老师测试的体验账号
}

# 初始化登录状态（如果记忆盒子里没有，就默认没登录）
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
# ==================================================
# ================= 门卫拦截逻辑 =================
if not st.session_state["logged_in"]:
    # 还没登录时，只显示这个极简界面
    st.markdown("<br><br><br>", unsafe_allow_html=True) # 往下挪一点，居中好看
    
    col1, col2, col3 = st.columns([1, 1.2, 1]) # 把登录框挤到中间
    with col2:
        st.title("🔐 《数字时代科技》课题系统")
        st.markdown("#### 智能交互式学习平台 - 专属复习空间")
        st.divider()
        
        input_user = st.text_input("👤 用户名 (Username)")
        input_pwd = st.text_input("🔑 密码 (Password)", type="password") # 密码会自动变黑点
        
        if st.button("登录进入工作台", type="primary", use_container_width=True):
            if input_user in VALID_USERS and VALID_USERS[input_user] == input_pwd:
                # 账号密码对上了！发放通行证！
                st.session_state["logged_in"] = True
                st.session_state["username"] = input_user
                st.success("✅ 登录成功！正在为您配置专属环境...")
                st.rerun() # 瞬间刷新网页
            else:
                st.error("❌ 用户名或密码错误，请重试！")
                
# ================= 下面是你的核心业务逻辑 =================
else:
    with st.sidebar:
            st.success(f"👋 欢迎回来, 尊贵的 **{st.session_state['username']}**!")
            if st.button("🚪 退出登录"):
                st.session_state["logged_in"] = False
                st.session_state["username"] = ""
                st.session_state.multi_results = [] # 退出时顺便清空他的临时工作台
                st.rerun()
    st.title("📚 智能交互式学习平台 (防重复解析版)")
    st.markdown("批量上传、动态追加、图文对照、自由排序，一键生成 **完整课程讲义 PDF**！")

    # ================= 状态初始化 =================
    if "multi_results" not in st.session_state:
        st.session_state.multi_results = []
    # 👑 新增：专门记录已经解析过的文件的“身份证号” (文件名 + 文件大小)
    if "processed_sigs" not in st.session_state:
        st.session_state.processed_sigs = set()

    # ================= 侧边栏：上传与全局控制 =================
    with st.sidebar:
        st.header("📥 步骤一：上传笔记")
        uploaded_files = st.file_uploader("请选择课堂笔记图片（可随时追加）", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        
        # 👑 核心逻辑 1：计算哪些是“新文件”
        new_files = []
        if uploaded_files:
            for f in uploaded_files:
                # 给每个文件生成一个独一无二的身份证号
                file_sig = f"{f.name}_{f.size}"
                if file_sig not in st.session_state.processed_sigs:
                    new_files.append(f)
                    
        # 👑 核心逻辑 2：动态变换按钮状态！
        if not uploaded_files:
            analyze_btn = st.button("🚀 请先上传图片", disabled=True, use_container_width=True)
        elif len(new_files) == 0:
            analyze_btn = st.button("✅ 当前图片已全部解析", disabled=True, use_container_width=True)
        else:
            analyze_btn = st.button(f"🚀 开始解析 {len(new_files)} 张新图片", type="primary", use_container_width=True)
        
        st.markdown("---")
        st.header("⚙️ 全局设置")
        if st.button("🗑️ 清空工作台 (删除所有内容)", use_container_width=True):
            st.session_state.multi_results = [] 
            st.session_state.processed_sigs = set() # 清空黑名单
            st.rerun() 

    # ================= 动态维护页码 =================
    for i, res in enumerate(st.session_state.multi_results):
        res["page_num"] = i + 1

    # ================= 主界面排版 =================
    col1, col2 = st.columns([1.1, 1.4]) 

    with col1:
        st.subheader("🖼️ 原始笔记序列 (按输出顺序)")
        if st.session_state.multi_results:
            st.write(f"**当前工作台共有 {len(st.session_state.multi_results)} 页笔记，图文一一对应：**")
            for res in st.session_state.multi_results:
                st.divider() 
                st.markdown(f"#### 📄 第 {res['page_num']} 页: `{res['filename']}`")
                if "image_bytes" in res:
                    st.image(res["image_bytes"], use_container_width=True)
                else:
                    st.warning("图片内容未成功持久化，建议清空工作台重新解析。")
        else:
            if not uploaded_files:
                st.info("👈 请先在左侧侧边栏上传手写笔记图片。")

    with col2:
        st.subheader("✨ AI 整理与解析控制台")
        
        # ---------------- 核心逻辑：只解析新文件 ----------------
        if analyze_btn:
            start_idx = len(st.session_state.multi_results)
            # 👑 注意：这里循环的是 new_files，而不是 uploaded_files！
            for i, file in enumerate(new_files):
                with st.spinner(f"正在深度解析新增的 第 {start_idx + i + 1} 页 ({file.name})..."):
                    file_bytes = file.getvalue()
                    file_sig = f"{file.name}_{file.size}" # 获取身份证号
                    
                    temp_img_path = f"temp_{file.name}"
                    with open(temp_img_path, "wb") as f:
                        f.write(file_bytes)
                    
                    result_data = process_image_to_dict(temp_img_path)
                    
                    if result_data:
                        st.session_state.multi_results.append({
                            "page_num": start_idx + i + 1,
                            "filename": file.name,
                            "data": result_data,
                            "image_bytes": file_bytes,
                            "sig": file_sig # 把身份证号也存进去，方便删除时找回
                        })
                        # 解析成功，加入黑名单！
                        st.session_state.processed_sigs.add(file_sig)
                    
                    if os.path.exists(temp_img_path):
                        os.remove(temp_img_path)
            
            st.success("✅ 追加解析与持久化完成！")
            st.rerun()

        # ---------------- 核心逻辑：页面管理与展示 ----------------
        if st.session_state.multi_results:
            with st.expander("🎛️ 页面排序与删除 (点击展开)", expanded=False):
                st.write("调整这里的顺序，PDF 的顺序也会随之改变：")
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
                        # 👑 如果用户删除了某一页，我们要把它从黑名单里放出来！
                        deleted_item = st.session_state.multi_results.pop(i)
                        if deleted_item["sig"] in st.session_state.processed_sigs:
                            st.session_state.processed_sigs.remove(deleted_item["sig"])
                        st.rerun()

            st.markdown("---")
            
            tab_names = [f"第 {res['page_num']} 页" for res in st.session_state.multi_results]
            tabs = st.tabs(tab_names)
            
            for i, tab in enumerate(tabs):
                with tab:
                    res = st.session_state.multi_results[i]
                    data = res["data"]
                    
                    st.caption(f"文件名: {res['filename']}")
                    with st.expander("🔍 识别原文与 AI 智能纠错", expanded=True):
                        st.markdown(data.get("recognition", "未提取到原文信息"))
                    with st.expander("💡 核心知识点与易错解析", expanded=True):
                        st.markdown(data.get("analysis", "解析提取失败"))
                    with st.expander("🎯 举一反三：同类变式题", expanded=True):
                        st.info(data.get("exercise", "变式题提取失败"))
                    with st.expander("🧠 解题逻辑流向 (Mermaid代码)", expanded=False):
                        st.code(data.get("mindmap", ""), language="mermaid")
                    with st.expander("📝 标准化 LaTeX 源码", expanded=False):
                        st.code(data.get("latex", ""), language="latex")
            
            # ---------------- 核心逻辑：PDF 按需定制 ----------------
            st.markdown("---")
            st.markdown("### 🖨️ 课程专属资料按需定制")
            st.write("请为**每一页**独立勾选需要包含在最终 PDF 中的模块：")
            
            export_selections = {}
            for i, res in enumerate(st.session_state.multi_results):
                page_num = res["page_num"]
                st.markdown(f"**📄 第 {page_num} 页 : {res['filename']}**")
                
                c1, c2, c3, c4 = st.columns(4)
                with c1: inc_rec = st.checkbox("🔍 原文与纠错", value=True, key=f"rec_{i}")
                with c2: inc_note = st.checkbox("📝 标准化笔记", value=True, key=f"note_{i}")
                with c3: inc_ana = st.checkbox("💡 考点解析", value=True, key=f"ana_{i}")
                with c4: inc_exe = st.checkbox("🎯 变式题", value=False, key=f"exe_{i}")
                
                export_selections[page_num] = {
                    "res_data": res, "inc_rec": inc_rec, "inc_note": inc_note, "inc_ana": inc_ana, "inc_exe": inc_exe
                }
                st.divider()
                
            if st.button("✨ 组装并编译为全课 PDF 讲义", type="primary"):
                with st.spinner("正在为您定制全课专属 PDF 讲义，请稍候..."):
                    final_latex_code = r"""
    \documentclass[UTF8, a4paper, 12pt]{ctexart}
    \usepackage{amsmath, amssymb, amsthm}
    \usepackage{geometry}
    \geometry{left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm}
    \title{新生引导课：课堂智能讲义}
    \author{AI-Lecture-Assistant 自动纠错与重构}
    \date{}
    \begin{document}
    \maketitle
    \tableofcontents
    \newpage
    """
                    pages_added = 0
                    for page_num, config in export_selections.items():
                        if not any([config["inc_rec"], config["inc_note"], config["inc_ana"], config["inc_exe"]]):
                            continue
                            
                        pages_added += 1
                        final_latex_code += f"\\section{{课堂笔记 - 第 {page_num} 页}}\n"
                        data = config["res_data"]["data"]
                        
                        if config["inc_rec"]:
                            final_latex_code += r"\subsection*{零、 原文识别与智能纠错}" + "\n" + data.get("recognition", "") + "\n\n"
                        if config["inc_note"]:
                            final_latex_code += r"\subsection*{一、 标准化笔记}" + "\n" + data.get("latex", "") + "\n\n"
                        if config["inc_ana"]:
                            final_latex_code += r"\subsection*{二、 核心考点与易错解析}" + "\n" + data.get("analysis", "") + "\n\n"
                        if config["inc_exe"]:
                            final_latex_code += r"\subsection*{三、 举一反三：变式练习题}" + "\n" + data.get("exercise", "") + "\n\n"
                            
                        final_latex_code += r"\newpage" + "\n"
                        
                    final_latex_code += r"\end{document}"
                    
                    if pages_added == 0:
                        st.error("您没有勾选任何内容！")
                    else:
                        pdf_result = compile_latex_to_pdf(final_latex_code, filename="full_course_notes")
                        if pdf_result == "ERROR_NO_COMPILER":
                            st.error("⚠️ 编译失败：找不到 `xelatex` 命令。")
                        elif pdf_result == "ERROR_COMPILE":
                            st.error("⚠️ 编译失败：公式可能存在语法冲突。")
                            with st.expander("查看出问题的完整 LaTeX 源码"):
                                st.code(final_latex_code, language="latex")
                        else:
                            st.success("🎉 定制讲义 PDF 编译成功！")
                            with open(pdf_result, "rb") as f:
                                st.download_button("📥 点击下载全课讲义", data=f, file_name="AI_Lecture_Notes.pdf", mime="application/pdf")

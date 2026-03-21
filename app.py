import streamlit as st
import os
# 关键：从你的 main.py 中导入刚刚写好的核心函数
from main import process_image_to_dict

import subprocess
import base64

def compile_latex_to_pdf(latex_code, filename="generated_notes"):
    """将 LaTeX 源码编译为 PDF"""
    tex_file = f"{filename}.tex"
    pdf_file = f"{filename}.pdf"
    
    # 1. 将代码写入 .tex 文件
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(latex_code)
        
    # 2. 调用本地 xelatex 进行编译 (隐藏终端输出)
    try:
        # 运行两遍 xelatex 以确保目录和引用正确生成
        subprocess.run(["xelatex", "-interaction=nonstopmode", tex_file], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(pdf_file):
            return pdf_file
        else:
            return "ERROR_COMPILE"
    except FileNotFoundError:
        # 如果系统里找不到 xelatex 命令，就会触发这个错误
        return "ERROR_NO_COMPILER"

st.set_page_config(layout="wide", page_title="AI 智能笔记助教")

st.title("📚 智能交互式学习平台 (MVP 版)")
st.markdown("上传手写笔记，一键生成 **LaTeX 源码、核心解析、思维导图与同类练习题**！")

with st.sidebar:
    st.header("📥 步骤一：上传笔记")
    uploaded_file = st.file_uploader("请选择一张高数笔记图片", type=["jpg", "png", "jpeg"])
    
    st.markdown("---")
    analyze_btn = st.button("🚀 开始 AI 分析", type="primary", use_container_width=True)

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("🖼️ 原始笔记")
    if uploaded_file is not None:
        st.image(uploaded_file, caption="待分析笔记", use_container_width=True)
    else:
        st.info("👈 请先在左侧侧边栏上传图片。")

with col2:
    st.subheader("✨ AI 整理与解析面板")
    
    # 初始化记忆盒子
    if "result_data" not in st.session_state:
        st.session_state.result_data = None

    # 第一步：点击分析按钮，调用大模型并存入记忆盒子
    if analyze_btn:
        if uploaded_file is None:
            st.warning("组长提醒：请先上传图片再点击分析哦！")
        else:
            with st.spinner("AI 正在深度解析数学逻辑，请稍候..."):
                # 保存临时图片
                temp_img_path = "temp_upload.jpg"
                with open(temp_img_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                
                # 调用核心引擎，把结果放进 session_state 这个记忆盒子里！
                st.session_state.result_data = process_image_to_dict(temp_img_path)
                
                if os.path.exists(temp_img_path):
                    os.remove(temp_img_path)

    # 第二步：只要记忆盒子里有数据，就一直展示它们
    if st.session_state.result_data is not None:
        data = st.session_state.result_data # 拿出来方便用
        
        st.success("✅ 解析完成！")
        
        # 折叠面板设计
        with st.expander("💡 核心知识点与易错解析", expanded=True):
            st.markdown(data["analysis"])
            
        with st.expander("🎯 举一反三：同类变式题", expanded=True):
            st.info(data["exercise"])

        with st.expander("🧠 解题逻辑流向 (Mermaid代码)", expanded=False):
            st.code(data["mindmap"], language="mermaid")
            
        with st.expander("📝 标准化 LaTeX 源码 (纯数学推导)", expanded=False):
            st.code(data["latex"], language="latex")
        
        st.markdown("---")
        st.markdown("### 🖨️ 专属学习资料定制与导出")
        
        # 1. 渲染三个并排的勾选框
        st.write("请选择需要包含在最终 PDF 中的模块：")
        col_chk1, col_chk2, col_chk3 = st.columns(3)
        with col_chk1:
            inc_note = st.checkbox("📝 原始推导笔记", value=True)
        with col_chk2:
            inc_analysis = st.checkbox("💡 考点与错因解析", value=True)
        with col_chk3:
            inc_exercise = st.checkbox("🎯 变式练习题", value=True)
            
        # 2. 纯文本源码下载 (无论如何都提供一个后路)
        st.download_button(
            label="📥 仅下载原始 LaTeX 源码段 (.tex)",
            data=data["latex"],
            file_name="raw_notes.tex",
            mime="text/plain"
        )
        
        # 3. 动态组装并编译 PDF 按钮逻辑
        if st.button("✨ 组装并编译为高清中文 PDF", type="primary"):
            with st.spinner("正在为您定制专属 PDF，这可能需要几秒钟..."):
                
                # 【防乱码神器】：在 Python 里写死最完美的中文 LaTeX 框架
                final_latex_code = r"""
\documentclass[UTF8, a4paper, 12pt]{ctexart}
\usepackage{amsmath, amssymb, amsthm}
\usepackage{geometry}
\geometry{left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm}
\begin{document}
"""
                # 根据用户的勾选，动态往框架里塞内容
                if inc_note:
                    final_latex_code += r"\section*{一、 标准化笔记}" + "\n" + data["latex"] + "\n\n"
                if inc_analysis:
                    final_latex_code += r"\section*{二、 核心考点与易错解析}" + "\n" + data["analysis"] + "\n\n"
                if inc_exercise:
                    final_latex_code += r"\section*{三、 举一反三：变式练习题}" + "\n" + data["exercise"] + "\n\n"
                
                # 封口
                final_latex_code += r"\end{document}"
                
                # 将组装好的终极代码送去编译
                pdf_result = compile_latex_to_pdf(final_latex_code)
                
                if pdf_result == "ERROR_NO_COMPILER":
                    st.error("⚠️ 编译失败：找不到 `xelatex` 命令。请确保已经安装 TeX Live 并配置环境变量！")
                elif pdf_result == "ERROR_COMPILE":
                    st.error("⚠️ 编译失败：模型生成的文本中可能包含了 LaTeX 无法识别的非法字符。")
                    # 如果失败，把拼接好的源码显示出来方便 Debug
                    with st.expander("查看出问题的完整 LaTeX 源码"):
                        st.code(final_latex_code, language="latex")
                else:
                    st.success("🎉 专属定制 PDF 编译成功！")
                    with open(pdf_result, "rb") as f:
                        st.download_button(
                            label="📥 点击下载您的定制 PDF",
                            data=f,
                            file_name="custom_math_notes.pdf",
                            mime="application/pdf"
                        )
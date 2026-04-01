# 📚 智能交互式学习平台 (AI-Lecture-Assistant)

本项目为中国人民大学高瓴人工智能学院“新生导读”课程作业/项目原型 (MVP)。
核心理念：打破传统手写笔记的局限，打造“解析-重构-拓展-输出”的交互式学习闭环。

## 🌟 项目架构大升级 (v2.0)

本项目目前包含两套架构，推荐使用最新的前后端分离 Web 架构：

* **V1 版本 (Streamlit 纯 Python 架构):** 运行 app.py
* **V2 版本 (FastAPI + HTML 原生 Web 架构) [⭐ 当前主推]:** 拥有 Notion 级别的排版、MathJax 数学公式渲染、以及全局沉浸式 AI 悬浮助教。

---

## 🚀 组员快速上手指南 (如何运行 V2 版本)

请小组成员按照以下步骤在本地启动最新版的工作台：

### 1. 安装项目依赖
打开终端，确保你所在的目录是项目根目录，运行以下命令安装必备的第三方库：
> pip install -r requirements.txt

### 2. 配置本地环境变量 (⚠️ 极其重要)
由于安全原因，项目的密钥文件 .env 不会上传到 GitHub。请在你的本地项目根目录下手动新建一个文件，命名为 .env，并填入以下内容（请向组长索要具体的 Key）：
> DASHSCOPE_API_KEY=你的通义千问API_KEY
> SUPABASE_KEY=你的Supabase密钥 (根据实际情况填写)

### 3. 启动 FastAPI 后端服务器
在终端中输入以下命令启动后端引擎：
> uvicorn api:app --reload

看到 Application startup complete 提示后，说明后端已成功运行在 http://127.0.0.1:8000。注意：运行期间请勿关闭此终端窗口！

### 4. 打开前端网页
后端启动后，无需任何命令，直接在文件管理器中双击打开 index.html，即可进入高瓴 AI 学习 OS！
* **工作台 (workspace.html):** 支持多图拖拽上传、大模型核心考点提取与公式排版。
* **复习空间 (review.html):** 支持树状目录检索、卡片管理、专属注记折叠，以及右下角的沉浸式全局 AI 助教。

---

## 🛠️ 技术栈
* **前端:** HTML5, Tailwind CSS, Vanilla JavaScript, MathJax
* **后端:** Python, FastAPI, Uvicorn
* **数据库:** Supabase (PostgreSQL)
* **多模态大模型:** 阿里通义千问 (qwen-vl-plus)

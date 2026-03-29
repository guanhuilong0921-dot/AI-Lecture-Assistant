import dashscope
from dashscope import MultiModalConversation
import os
from dotenv import load_dotenv

# ================= 配置区 =================
load_dotenv()
dashscope.api_key = os.getenv("QWEN_API_KEY") 
# ==========================================

def parse_qwen_response(raw_text):
    """把大模型返回的长文本切分成字典"""
    parsed_data = {
        "tags": "未生成标签", # ✨ 新增：默认标签
        "recognition": "原文识别与纠错生成失败。",
        "latex": "",
        "analysis": "解析生成失败，请重试。",
        "mindmap": "graph TD;\n A[生成失败] --> B[请重试]",
        "exercise": "练习题生成失败，请重试。"
    }
 
    try:
        # ✨ 新增：提取 知识点标签
        if "[START_TAGS]" in raw_text and "[END_TAGS]" in raw_text:
            parsed_data["tags"] = raw_text.split("[START_TAGS]")[1].split("[END_TAGS]")[0].strip()

        # 提取 原文识别与纠错
        if "[START_RECOGNITION]" in raw_text and "[END_RECOGNITION]" in raw_text:
            parsed_data["recognition"] = raw_text.split("[START_RECOGNITION]")[1].split("[END_RECOGNITION]")[0].strip()

        # 提取 LaTeX
        if "[START_LATEX]" in raw_text and "[END_LATEX]" in raw_text:
            latex_part = raw_text.split("[START_LATEX]")[1].split("[END_LATEX]")[0].strip()
            parsed_data["latex"] = latex_part.replace("`latex", "").replace("`", "").strip()
 
        # 提取 解析
        if "[START_ANALYSIS]" in raw_text and "[END_ANALYSIS]" in raw_text:
            parsed_data["analysis"] = raw_text.split("[START_ANALYSIS]")[1].split("[END_ANALYSIS]")[0].strip()
 
        # 提取 思维导图
        if "[START_MINDMAP]" in raw_text and "[END_MINDMAP]" in raw_text:
            mindmap_part = raw_text.split("[START_MINDMAP]")[1].split("[END_MINDMAP]")[0].strip()
            parsed_data["mindmap"] = mindmap_part.replace("`mermaid", "").replace("`", "").strip()
 
        # 提取 练习题
        if "[START_EXERCISE]" in raw_text and "[END_EXERCISE]" in raw_text:
            parsed_data["exercise"] = raw_text.split("[START_EXERCISE]")[1].split("[END_EXERCISE]")[0].strip()
 
    except Exception as e:
        print(f"解析报错了: {e}")
 
    return parsed_data
 
def process_image_to_dict(img_path):
    """
    提供给前端调用的终极接口。
    """
    print(f"--- 正在通过通义千问视觉模型分析: {img_path} ---")
 
    prompt_text = r"""
    你是一位精通 LaTeX 且极具启发性的大学助教。请仔细分析图片中的手写笔记或题目，并严格按照以下六大模块输出，模块之间使用特定的标记符隔开：
    【最高指令】：在所有模块中，只能使用纯文本和 LaTeX 数学公式（用 $ 或 $$ 包裹）。绝对禁止使用任何 Markdown 特殊符号！

    [START_TAGS]
    请提取这张笔记或题目中的 3-5 个核心知识点标签，用逗号分隔（例如：极限运算, 洛必达法则, 泰勒公式）。
    [END_TAGS]

    [START_RECOGNITION]
    完整识别并转录图片中的手写原文。诊断是否存在错误或书写不规范并给出建议。
    [END_RECOGNITION]

    [START_LATEX]
    仅仅输出图片中手写笔记的核心 LaTeX 数学代码。只输出公式和正文推导！
    [END_LATEX]

    [START_ANALYSIS]
    输出极其详细的知识点解析：1. 核心考点剖析 2. 步步为营推演 3. 易错点指南。
    【严重警告】：所有数学公式必须用 $ 包裹！
    [END_ANALYSIS]

    [START_MINDMAP]
    只输出 Mermaid 语法的代码，画出解题逻辑流向图，不要包含 ```mermaid 标记。
    [END_MINDMAP]

    [START_EXERCISE]
    出一道同类型的变式练习题，并附带简短的答案提示。
    【严重警告】：所有数学公式必须用 $ 包裹！
    [END_EXERCISE]
    """
 
    messages = [
        {
            "role": "user",
            "content": [
                {"image": f"file://{os.path.abspath(img_path)}"},
                {"text": prompt_text}
            ]
        }
    ]
 
    # 为了保证演示速度，这里换成 qwen-vl-plus 版本
    response = MultiModalConversation.call(model='qwen-vl-plus', messages=messages)
 
    if response.status_code == 200:
        raw_text = response.output.choices[0].message.content[0]['text']
        return parse_qwen_response(raw_text)
    else:
        print(f"API错误:{response.code} - {response.message}")
        return None

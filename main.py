import dashscope
from dashscope import MultiModalConversation
import os
from dotenv import load_dotenv  # 新增这一行

# ================= 配置区 =================
load_dotenv()  # 激活保险箱
# 从 .env 文件中安全读取密钥
dashscope.api_key = os.getenv("QWEN_API_KEY") 
# ==========================================

def parse_qwen_response(raw_text):
    # 字典里增加 recognition 字段
    parsed_data = {
        "recognition": "原文识别与纠错生成失败。",
        "latex": "% LaTeX 生成失败",
        "analysis": "解析生成失败，请检查网络或重试。",
        "mindmap": "graph TD;\n A[生成失败] --> B[请重试]",
        "exercise": "练习题生成失败。"
    }
    
    try:
        # 新增提取逻辑
        if "[START_RECOGNITION]" in raw_text and "[END_RECOGNITION]" in raw_text:
            rec_part = raw_text.split("[START_RECOGNITION]")[1].split("[END_RECOGNITION]")[0].strip()
            parsed_data["recognition"] = rec_part
                       
        # 提取 LaTeX
        if "[START_LATEX]" in raw_text and "[END_LATEX]" in raw_text:
            latex_part = raw_text.split("[START_LATEX]")[1].split("[END_LATEX]")[0].strip()
            # 自动清洗模型可能带有的 markdown 代码块标记
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
    你是一位精通 LaTeX 且极具启发性的大学数学助教。请按以下五大模块输出，模块间用指定的标签隔开。
    【最高指令】：在所有模块中，只能使用纯文本和 LaTeX 数学公式（用 $ 或 $$ 包裹）。**绝对禁止**使用任何 Markdown 特殊符号（如 **加粗**, # 标题，- 列表），以防止后续编译 PDF 时报错！

    [START_RECOGNITION]
    首先完整识别并转录图片中的手写原文。然后，诊断原文中是否存在计算错误、逻辑漏洞或书写不规范。如果有，请明确指出并给出纠错建议；如果没有，请回复“原文逻辑严密，未发现明显错误”。
    [END_RECOGNITION]

    [START_LATEX]
    仅仅输出图片中手写笔记的核心 LaTeX 数学代码。
    注意：只输出公式和正文推导！**绝对不要**包含 \documentclass, \usepackage, 以及 \begin{document} 等结构代码！
    [END_LATEX]

    [START_ANALYSIS]
    深入解释核心考点、推导逻辑和易错点。请分段落书写，逻辑清晰，绝不能用 Markdown 标记。
    [END_ANALYSIS]

    [START_MINDMAP]
    只输出 Mermaid 语法的代码，画出解题逻辑流向图，不要包含 ```mermaid 标记。
    [END_MINDMAP]

    [START_EXERCISE]
    出一道同类型的变式练习题，并附带简短的答案提示。绝不能用 Markdown 标记。
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
 
    response = MultiModalConversation.call(model='qwen-vl-max', messages=messages)
 
    if response.status_code == 200:
        raw_text = response.output.choices[0].message.content[0]['text']
        return parse_qwen_response(raw_text)
    else:
        print(f"API错误:{response.code} - {response.message}")
        return None

# 测试代码：如果你直接运行 main.py，它会执行这里
if __name__ == "__main__":
    TEST_IMAGE = "test.jpg"
    if not os.path.exists(TEST_IMAGE):
        print(f"找不到测试图片 {TEST_IMAGE}，请在同级目录放一张手写笔记图片。")
    else:
        result_dict = process_image_to_dict(TEST_IMAGE)
        if result_dict:
            print("\n✅ 测试成功！成功提取到 4 个模块的数据：")
            print("【分析预览】:", result_dict["analysis"][:50], "...")

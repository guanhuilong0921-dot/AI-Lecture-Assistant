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
    """把大模型返回的长文本切分成字典"""
    parsed_data = {
        "latex": "",
        "analysis": "解析生成失败，请重试。",
        "mindmap": "",
        "exercise": "练习题生成失败，请重试。"
    }
 
    try:
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
    你是一位精通 LaTeX 且极具启发性的大学助教。请仔细分析图片中的手写题目和解题步骤，并严格按照以下四大模块输出，模块之间使用特定的标记符隔开：
    【最高指令】：在所有模块中，只能使用纯文本和 LaTeX 数学公式（用 $ 或 $$ 包裹）。**绝对禁止**使用任何 Markdown 特殊符号（如 **加粗**, # 标题，- 列表），以防止后续编译 PDF 时报错！
    [START_LATEX]
    仅仅输出图片中手写笔记的核心 LaTeX 数学代码。
    注意：只输出公式和正文推导！绝对不要包含 \documentclass, \usepackage, 以及 \begin{document} 等结构代码！
    [END_LATEX]

    [START_ANALYSIS]
    在这里输出极其详细的知识点解析。千万不要简略！请你扮演一位极其耐心、注重逻辑推导的大学数学教授，必须包含以下三个层次：
    1. **核心考点剖析**：深入解释本题考察的理论基础。
    2. **步步为营推演**：对照图片中的笔记，一步一步拆解黑板上的推导过程。不仅要说明“是什么”，更要解释“为什么”（例如：为什么这一步能推到下一步？这里用到了什么微积分定理或公式？）。
    3. **易错点与避坑指南**：一针见血地指出学生在做这类高数题时，最常犯的计算陷阱或逻辑误区。
    [END_ANALYSIS]

    [START_MINDMAP]
    在这里只输出 Mermaid 语法的代码，画出这道题的解题逻辑流向图，不要包含 markdown 的 ```mermaid 标记。
    [END_MINDMAP]

    [START_EXERCISE]
    在这里出一道同类型的变式练习题，并附带简短的答案提示。
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
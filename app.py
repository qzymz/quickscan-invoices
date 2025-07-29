# -*- coding: utf-8 -*-
"""
发票OCR专用识别系统
基于RapidOCR的智能发票识别与字段提取平台
"""

import gradio as gr
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple
from rapidocr import RapidOCR
from invoice_config import (
    INVOICE_TYPES, 
    COMMON_FIELD_PATTERNS, 
    AMOUNT_PATTERNS, 
    TAX_PATTERNS, 
    DATE_PATTERNS,
    get_invoice_type_config,
    get_all_field_patterns,
    get_invoice_types_list,
    validate_invoice_data
)

# 读取外部样式文件
def load_custom_css():
    """加载自定义CSS样式"""
    try:
        with open('styles.css', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # 如果样式文件不存在，返回基础样式
        return """
        body { font-family: 'Segoe UI', sans-serif; }
        .gr-button { background: linear-gradient(45deg, #667eea, #764ba2) !important; color: white !important; }
        """
    except Exception as e:
        print(f"加载样式文件时出错: {e}")
        return ""

# 发票COR处理器类
class InvoiceCORProcessor:
    """发票COR专用处理器"""
    
    def __init__(self):
        """初始化OCR引擎和配置"""
        self.ocr_engine = RapidOCR()
        self.invoice_types = INVOICE_TYPES
        self.common_patterns = COMMON_FIELD_PATTERNS
        self.amount_patterns = AMOUNT_PATTERNS
        self.tax_patterns = TAX_PATTERNS
        self.date_patterns = DATE_PATTERNS
    
    def detect_invoice_type(self, text_list: List[str]) -> str:
        """检测发票类型"""
        if not text_list:
            return "未知类型"
        
        # 合并所有文本进行关键词匹配
        combined_text = " ".join(text_list).lower()
        
        for invoice_type, config in self.invoice_types.items():
            keywords = config.get("keywords", [])
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    return invoice_type
        
        return "通用发票"
    
    def extract_fields(self, text_list: List[str], detected_type: str = None) -> Dict[str, Any]:
        """提取发票字段"""
        if not text_list:
            return {}
        
        extracted_fields = {}
        combined_text = " ".join(text_list)
        
        # 添加调试信息
        print(f"Debug - 检测到的发票类型: {detected_type}")
        print(f"Debug - 合并文本长度: {len(combined_text)}")
        print(f"Debug - 前100个字符: {combined_text[:100]}")
        
        # 获取特定发票类型的字段模式
        type_config = get_invoice_type_config(detected_type) if detected_type else None
        type_patterns = type_config.get("fields", {}) if type_config else {}
        
        # 合并通用模式和类型特定模式
        all_patterns = {**self.common_patterns, **type_patterns}
        
        print(f"Debug - 可用字段模式数量: {len(all_patterns)}")
        
        # 提取字段
        for field_name, pattern in all_patterns.items():
            import re
            match = re.search(pattern, combined_text)
            if match:
                extracted_fields[field_name] = match.group(1).strip()
                print(f"Debug - 成功提取字段 '{field_name}': {match.group(1).strip()}")
        
        # 提取金额信息
        for pattern in self.amount_patterns:
            match = re.search(pattern, combined_text)
            if match and "金额" not in extracted_fields:
                extracted_fields["金额"] = match.group(1).strip()
                print(f"Debug - 成功提取金额: {match.group(1).strip()}")
        
        # 提取税额信息
        for pattern in self.tax_patterns:
            match = re.search(pattern, combined_text)
            if match and "税额" not in extracted_fields:
                extracted_fields["税额"] = match.group(1).strip()
                print(f"Debug - 成功提取税额: {match.group(1).strip()}")
        
        # 提取日期信息
        for pattern in self.date_patterns:
            match = re.search(pattern, combined_text)
            if match and "开票日期" not in extracted_fields:
                extracted_fields["开票日期"] = match.group(1).strip()
                print(f"Debug - 成功提取开票日期: {match.group(1).strip()}")
        
        print(f"Debug - 总共提取到 {len(extracted_fields)} 个字段")
        print(f"Debug - 提取的字段: {list(extracted_fields.keys())}")
        
        return extracted_fields
    
    def process_invoice(self, img_input, confidence_threshold: float = 0.5) -> Tuple[Dict[str, Any], str, List[List[Any]]]:
        """处理发票图像，返回结构化数据和原始OCR数据"""
        # OCR识别
        ocr_result = self.ocr_engine(
            img_input,
            use_det=True,
            use_cls=True,
            use_rec=True,
            text_score=confidence_threshold,
            box_thresh=0.5,
            unclip_ratio=1.6,
            return_word_box=False,
        )

        # 获取识别文本
        if ocr_result.txts:
            text_list = ocr_result.txts
        else:
            text_list = []

        # 检测发票类型
        invoice_type = self.detect_invoice_type(text_list)

        # 提取字段
        extracted_fields = self.extract_fields(text_list, invoice_type)

        # 验证数据
        validation_result = validate_invoice_data(extracted_fields)

        # 构建原始OCR识别数据
        raw_ocr_results = []
        # 兼容不同RapidOCR版本的属性
        boxes = getattr(ocr_result, 'boxes', None)
        scores = getattr(ocr_result, 'scores', None)
        txts = getattr(ocr_result, 'txts', None)
        if boxes is not None and txts is not None and scores is not None:
            for text, box, score in zip(txts, boxes, scores):
                # 将numpy数组转换为Python列表
                box_list = box.tolist() if hasattr(box, 'tolist') else box
                raw_ocr_results.append({
                    "text": text,
                    "box": box_list,
                    "score": float(score)
                })
        elif txts is not None and scores is not None:
            for text, score in zip(txts, scores):
                raw_ocr_results.append({
                    "text": text,
                    "box": None,
                    "score": float(score)
                })
        else:
            raw_ocr_results = []

        # 构建结果数据
        result_data = {
            "invoice_type": invoice_type,
            "confidence": float(np.mean(scores)) if scores is not None and len(scores) > 0 else 0.0,
            "processing_time": float(ocr_result.elapse),  # 确保是float类型
            "timestamp": datetime.now().isoformat(),
            "raw_ocr_results": raw_ocr_results,  # 原始OCR识别数据
            "extracted_fields": extracted_fields, # 整理后的结构化字段
            "validation": validation_result,
            "raw_text": text_list
        }

        # 生成可视化文本
        vis_text = f"发票类型: {invoice_type}\n"
        vis_text += f"置信度: {result_data['confidence']:.3f}\n"
        vis_text += f"处理时间: {result_data['processing_time']:.3f}秒\n"
        vis_text += f"数据有效性: {'✅ 有效' if validation_result['is_valid'] else '❌ 无效'}\n\n"

        if validation_result['missing_fields']:
            vis_text += f"缺失字段: {', '.join(validation_result['missing_fields'])}\n"

        if validation_result['warnings']:
            vis_text += f"警告信息: {', '.join(validation_result['warnings'])}\n"

        vis_text += "\n提取字段:\n"
        for field, value in extracted_fields.items():
            vis_text += f"{field}: {value}\n"

        # 构建表格数据
        table_data = []
        if text_list and scores is not None and len(scores) > 0:
            for i, (text, score) in enumerate(zip(text_list, scores)):
                table_data.append([i, text, f"{score:.3f}"])
        else:
            table_data = [[0, "未识别到文本", "0.000"]]

        return result_data, vis_text, table_data

# 全局处理器实例
invoice_processor = InvoiceCORProcessor()

def get_invoice_result(img_input, confidence_threshold):
    """获取发票识别结果"""
    if img_input is None:
        return "请先上传发票图片", "", []
    
    try:
        result_data, vis_text, table_data = invoice_processor.process_invoice(
            img_input, confidence_threshold
        )
        
        # 默认返回JSON格式
        return json.dumps(result_data, ensure_ascii=False, indent=2), vis_text, table_data
    except Exception as e:
        error_msg = f"处理失败: {str(e)}"
        return error_msg, error_msg, [[0, "处理失败", "0.000"]]

def create_invoice_examples():
    """创建发票示例"""
    return [
        ["images/fp1.jpg", 0.5],
        ["images/fp2.jpg", 0.5],
        ["images/fp3.jpg", 0.5],
        ["images/fp4.jpg", 0.5],
        ["images/fp5.jpg", 0.5]
    ]

def export_invoice_config(confidence_threshold):
    """导出发票配置"""
    config_data = {
        "supported_invoice_types": get_invoice_types_list(),
        "confidence_threshold": confidence_threshold,
        "return_format": "JSON格式",
        "field_patterns": get_all_field_patterns(),
        "export_time": datetime.now().isoformat()
    }
    
    config_json = json.dumps(config_data, ensure_ascii=False, indent=2)
    return config_json

# 加载自定义CSS样式
custom_css = load_custom_css()

# 创建Gradio界面
with gr.Blocks(
    title="🧾 发票OCR专用识别系统", 
    css=custom_css, 
    theme=gr.themes.Soft()
) as demo:
    
    # 页面标题区域
    with gr.Row():
        gr.HTML(
            """
            <div class="header-section fade-in-up">
                <h1 class="header-title">🧾 发票OCR专用识别系统</h1>
                <p class="header-subtitle">基于AI的智能发票识别与字段提取平台</p>
                <div class="header-features">
                    <span class="feature-tag">🚀 高性能OCR</span>
                    <span class="feature-tag">🎯 多发票类型</span>
                    <span class="feature-tag">📊 结构化输出</span>
                    <span class="feature-tag">✅ 数据验证</span>
                    <span class="feature-tag">🔍 智能识别</span>
                </div>
            </div>
            """
        )
    
    # 主要内容区域
    with gr.Row():
        # 左侧输入区域
        with gr.Column(scale=1):
            with gr.Group(elem_classes="input-section fade-in-up"):
                gr.HTML('<div class="input-title">📄 上传发票图片</div>')
                img_input = gr.Image(
                    label="",
                    sources="upload",
                    type="pil",
                    elem_classes="image-upload",
                    height=300,
                    width=None,
                    show_download_button=False
                )
                
                with gr.Accordion("⚙️ 参数设置", open=False, elem_classes="accordion"):
                    confidence_threshold = gr.Slider(
                        label="🎯 置信度阈值",
                        minimum=0.1,
                        maximum=1.0,
                        value=0.5,
                        step=0.1,
                        info="文本识别置信度阈值，值越大识别越严格"
                    )
                
                with gr.Row():
                    run_btn = gr.Button("🚀 开始识别", variant="primary", size="lg")
                    export_btn = gr.Button("📋 导出配置", size="lg")
                    download_btn_hidden = gr.DownloadButton(
                        visible=False, 
                        elem_id="download_btn_hidden"
                    )
        
        # 右侧输出区域
        with gr.Column(scale=1):
            with gr.Group(elem_classes="output-section fade-in-up"):
                gr.HTML('<div class="input-title">📊 识别结果</div>')
                
                with gr.Tabs(elem_classes="tabs"):
                    with gr.TabItem("🎯 JSON格式", elem_classes="tab-nav"):
                        result_output = gr.Textbox(
                            label="",
                            lines=12,
                            max_lines=15,
                            show_copy_button=True,
                            elem_classes="gr-textbox"
                        )
                    
                    with gr.TabItem("📋 字段详情", elem_classes="tab-nav"):
                        field_output = gr.Textbox(
                            label="",
                            lines=12,
                            max_lines=15,
                            show_copy_button=True,
                            elem_classes="gr-textbox"
                        )
                    
                    with gr.TabItem("📝 原始文本", elem_classes="tab-nav"):
                        table_output = gr.Dataframe(
                            label="",
                            headers=["序号", "文本内容", "置信度"],
                            datatype=["number", "str", "number"],
                            show_copy_button=True,
                            elem_classes="gr-dataframe"
                        )
    
    # 示例区域
    with gr.Row():
        gr.HTML(
            """
            <div class="examples fade-in-up">
                <h3 style="text-align: center; margin-bottom: 20px; color: #333;">
                    💡 快速示例 - 点击下方示例图片开始体验
                </h3>
            </div>
            """
        )
    
    # 处理函数绑定
    def process_with_fields(img_input, confidence_threshold):
        """处理发票并返回多个输出"""
        result_data, vis_text, table_data = get_invoice_result(
            img_input, confidence_threshold
        )
        
        # 添加调试信息
        print(f"Debug - table_data: {table_data}")
        print(f"Debug - table_data length: {len(table_data)}")
        if table_data:
            print(f"Debug - first row: {table_data[0]}")
        
        # 提取字段信息用于显示
        if not result_data.startswith("处理失败"):
            try:
                data = json.loads(result_data)
                field_text = "📋 提取的字段信息:\n"
                if "extracted_fields" in data:
                    for field, value in data["extracted_fields"].items():
                        field_text += f"• {field}: {value}\n"
                    
                    # 添加验证信息
                    if "validation" in data:
                        validation = data["validation"]
                        field_text += f"\n🔍 数据验证:\n"
                        status_icon = "✅" if validation['is_valid'] else "❌"
                        field_text += f"{status_icon} 有效性: {'有效' if validation['is_valid'] else '无效'}\n"
                        if validation['missing_fields']:
                            field_text += f"⚠️ 缺失字段: {', '.join(validation['missing_fields'])}\n"
                        if validation['warnings']:
                            field_text += f"⚠️ 警告: {', '.join(validation['warnings'])}\n"
                else:
                    field_text = "❌ 未提取到字段信息"
            except Exception as e:
                print(f"Debug - JSON解析错误: {e}")
                field_text = vis_text
        else:
            field_text = vis_text
        
        return result_data, field_text, table_data
    
    run_btn.click(
        process_with_fields,
        inputs=[img_input, confidence_threshold],
        outputs=[result_output, field_output, table_output]
    )
    
    # 导出配置
    export_btn.click(
        fn=export_invoice_config,
        inputs=[confidence_threshold],
        outputs=[download_btn_hidden]
    ).then(
        fn=None,
        inputs=None,
        outputs=None,
        js="() => document.querySelector('#download_btn_hidden').click()",
    )
    
    # 示例
    examples = gr.Examples(
        examples=create_invoice_examples(),
        examples_per_page=5,
        inputs=[img_input, confidence_threshold],
        fn=process_with_fields,
        outputs=[result_output, field_output, table_output],
        cache_examples=False
    )

if __name__ == "__main__":
    demo.launch()

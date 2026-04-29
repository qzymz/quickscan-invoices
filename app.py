# -*- coding: utf-8 -*-
"""
发票OCR专用识别系统
基于RapidOCR的智能发票识别与字段提取平台
"""

import gradio as gr
import json
import numpy as np
import argparse
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple, Union
from rapidocr import RapidOCR
from PIL import Image
import fitz  # PyMuPDF

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
        body { 
            font-family: 'Segoe UI', sans-serif; 
            background-color: #e6f2ff; /* 淡蓝色背景 */
        }
        .gr-button { background: linear-gradient(45deg, #667eea, #764ba2) !important; color: white !important; }
        .gr-container { background-color: #e6f2ff !important; }
        """
    except Exception as e:
        print(f"加载样式文件时出错: {e}")
        return ""

# PDF处理函数（PyMuPDF方式，无需poppler）
def pdf_first_page_to_image(pdf_file) -> Image.Image:
    """将PDF第一页渲染为PIL.Image对象，兼容gradio NamedString/BytesIO/真实文件"""
    try:
        if hasattr(pdf_file, "seek") and hasattr(pdf_file, "read"):
            pdf_file.seek(0)
            pdf_bytes = pdf_file.read()
        else:
            with open(pdf_file.name, "rb") as f:
                pdf_bytes = f.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img
    except Exception as e:
        raise Exception(f"PDF转图片失败: {e}")

def process_pdf_invoice(pdf_files, confidence_threshold: float = 0.5, progress=gr.Progress()):
    try:
        all_results = []
        result_table_data = []
        all_table_data = []
        
        # 处理多个PDF文件
        for i, pdf_file in enumerate(pdf_files):
            # 提取文件名（去掉路径）
            file_basename = os.path.basename(pdf_file.name)
            # 更新进度条
            progress((i, len(pdf_files)), f"处理第 {i+1} 个PDF文件: {file_basename}")
            
            try:
                # 将PDF转换为图片
                img = pdf_first_page_to_image(pdf_file)
                # 处理发票
                result_data, vis_text, table_data = invoice_processor.process_invoice(img, confidence_threshold)
                result_data["source_type"] = "PDF"
                result_data["processed_page"] = 1
                result_data["file_name"] = file_basename
                
                # 添加到结果列表
                all_results.append(result_data)
                
                # 为原始文本表格添加文件标识
                for row in table_data:
                    all_table_data.append([len(all_table_data) + 1, f"{file_basename}: {row[1]}", row[2]])
                
                # 提取结构化表格数据
                invoice_date = result_data["extracted_fields"].get("开票日期", "未识别")
                total_amount = result_data["extracted_fields"].get("价税合计小写", "未识别")
                result_table_data.append([file_basename, invoice_date, total_amount])
                    
            except Exception as e:
                error_msg = f"PDF处理失败: {str(e)}"
                all_results.append({
                    "error": error_msg,
                    "file_name": file_basename,
                    "source_type": "PDF"
                })
                all_table_data.append([len(all_table_data) + 1, f"{file_basename}: PDF处理失败", "0.000"])
                # 添加错误信息到结构化表格
                result_table_data.append([file_basename, "处理失败", f"错误: {str(e)}"])
        
        # 更新进度为完成
        progress(1, "处理完成")
        
        # 返回JSON结果、结构化表格数据和原始文本表格数据
        return json.dumps(all_results, ensure_ascii=False, indent=2), result_table_data, all_table_data
    except Exception as e:
        error_msg = f"批量PDF处理失败: {str(e)}"
        return json.dumps([{"error": error_msg}]), [["", "批量处理失败", f"错误: {str(e)}"]], [[0, "批量PDF处理失败", "0.000"]]

def detect_file_type(file_path: str) -> str:
    if not file_path:
        return "unknown"
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
        return "image"
    elif file_extension == '.pdf':
        return "pdf"
    else:
        return "unknown"

def process_mixed_input(file_input, confidence_threshold: float = 0.5):
    if file_input is None:
        return {"error": "请先上传文件"}, "请先上传文件", []
    file_type = detect_file_type(file_input.name)
    if file_type == "image":
        return get_invoice_result(file_input, confidence_threshold)
    elif file_type == "pdf":
        return process_pdf_invoice(file_input, confidence_threshold)
    else:
        error_msg = "不支持的文件格式，请上传图像或PDF文件"
        return {"error": error_msg}, error_msg, [[0, "不支持的文件格式", "0.000"]]

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
        """提取发票字段，只提取必要字段"""
        import re  # 将re模块导入放在函数顶部，确保全局可用
        
        if not text_list:
            return {}
        
        # 重置提取字段，只保留需要的字段
        extracted_fields = {}
        combined_text = " ".join(text_list)
        
        # 添加调试信息
        print(f"Debug - 检测到的发票类型: {detected_type}")
        print(f"Debug - 合并文本长度: {len(combined_text)}")
        print(f"Debug - 前100个字符: {combined_text[:100]}")
        
        # 1. 提取开票日期
        print("Debug - 开始提取开票日期")
        for pattern in self.date_patterns:
            match = re.search(pattern, combined_text)
            if match and "开票日期" not in extracted_fields:
                extracted_fields["开票日期"] = match.group(1).strip()
                print(f"Debug - 成功提取开票日期: {extracted_fields['开票日期']}")
        
        # 获取所有识别的文本行
        lines = text_list
        
        # 3. 提取价税合计小写
        print("Debug - 开始提取价税合计小写")
        for line in lines:
            if "小写" in line and ("￥" in line or "¥" in line):
                # 匹配如 "（小写）¥3568.00" 或 "小写: ￥3568.00" 格式
                price_match = re.search(r"[￥¥]\s*([\d,]+\.?\d*)", line)
                if price_match:
                    extracted_fields["价税合计小写"] = price_match.group(1).strip()
                    print(f"Debug - 提取到价税合计小写: {extracted_fields['价税合计小写']}")
                    break
        
        # 如果没找到，尝试直接匹配带货币符号的价格
        if "价税合计小写" not in extracted_fields:
            for line in lines:
                if "￥" in line or "¥" in line:
                    price_match = re.search(r"[￥¥]\s*([\d,]+\.?\d*)", line)
                    if price_match:
                        extracted_fields["价税合计小写"] = price_match.group(1).strip()
                        print(f"Debug - 提取到价税合计小写: {extracted_fields['价税合计小写']}")
                        break
        
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

def process_with_fields_image(img_path, confidence_threshold: float = 0.5):
    """处理图像发票，返回结构化数据、结构化表格和原始文本表格"""
    if img_path is None:
        return {"error": "请先上传图片"}, [["", "请先上传图片", ""]], []
    try:
        img_input = Image.open(img_path)
        result_data, vis_text, table_data = invoice_processor.process_invoice(img_input, confidence_threshold)
        result_data["source_type"] = "Image"
        result_data["file_name"] = os.path.basename(img_path) if isinstance(img_path, str) else "未知图片"
        
        # 提取结构化表格数据
        file_name = result_data["file_name"]
        invoice_date = result_data["extracted_fields"].get("开票日期", "未识别")
        total_amount = result_data["extracted_fields"].get("价税合计小写", "未识别")
        result_table_data = [[file_name, invoice_date, total_amount]]
        
        return json.dumps(result_data, ensure_ascii=False, indent=2), result_table_data, table_data
    except Exception as e:
        error_msg = f"图片处理失败: {str(e)}"
        return {"error": error_msg}, [["", "处理失败", error_msg]], [[0, "图片处理失败", "0.000"]]

def create_invoice_examples():
    # 只返回图片样例
    examples = [
        ["images/fp1.jpg", 0.5],
        ["images/fp2.jpg", 0.5],
        ["images/fp3.jpg", 0.5],
        ["images/fp4.jpg", 0.5],
        ["images/fp5.jpg", 0.5]
    ]
    return examples

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

# 导出结果函数
def export_table_data(table_data):
    """将表格数据导出为Excel格式并保存到临时文件"""
    import pandas as pd
    import io
    import datetime
    import tempfile
    import os
    
    # 检查是否为pandas DataFrame或列表
    if isinstance(table_data, pd.DataFrame):
        # 使用empty属性检查DataFrame是否为空
        if table_data.empty:
            return None
        df = table_data
    elif isinstance(table_data, list):
        # 兼容旧格式（列表格式）
        if not table_data:
            return None
        # 创建pandas DataFrame
        df = pd.DataFrame(table_data, columns=["文件名", "开票日期", "价税合计小写"])
    else:
        return None
    
    # 生成文件名，包含时间戳
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"invoice_results_{timestamp}.xlsx"
    
    # 计算金额总计
    try:
        # 将"价税合计小写"列转换为数值类型
        df['价税合计小写'] = pd.to_numeric(df['价税合计小写'], errors='coerce')
        # 计算总和
        total_amount = df['价税合计小写'].sum()
        # 创建总计行
        total_row = pd.DataFrame([{'文件名': '总计', '开票日期': '', '价税合计小写': total_amount}])
        # 将总计行添加到DataFrame末尾
        df = pd.concat([df, total_row], ignore_index=True)
    except Exception as e:
        print(f"计算金额总计失败: {e}")
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
        # 保存Excel文件到临时位置
        with pd.ExcelWriter(tmp_file.name, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='发票识别结果')
        
        # 返回临时文件路径
        return tmp_file.name

# 加载自定义CSS样式
custom_css = load_custom_css()

# 创建Gradio界面
with gr.Blocks(
    title="🧾 发票OCR专用识别系统"
) as demo:
    # 添加自定义CSS
    gr.HTML(f'<style>{custom_css}</style>')
    
    # 页面标题区域
    with gr.Row():
        gr.HTML(
            """
            <div class="header-section fade-in-up">
                <h1 class="header-title">🧾 发票OCR专用识别系统</h1>
                <p class="header-subtitle">基于AI的智能发票识别与字段提取平台</p>
            </div>
            """
        )
    
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group(elem_classes="input-section fade-in-up"):
                gr.HTML('<div class="input-title">📄 上传发票文件</div>')
                with gr.Tabs():
                    with gr.Tab("PDF发票"):
                        pdf_input = gr.File(label="上传PDF发票", file_types=[".pdf"], file_count="multiple", elem_classes="image-upload")
                        confidence_pdf = gr.Slider(label="🎯 置信度阈值", minimum=0.1, maximum=1.0, value=0.5, step=0.1)
                        with gr.Row():
                            run_btn_pdf = gr.Button("🚀 开始识别", variant="primary", size="lg", elem_classes="gr-button")
                    with gr.Tab("图片发票"):
                        img_input = gr.Image(label="上传发票图片", type="filepath", elem_classes="image-upload")
                        confidence_img = gr.Slider(label="🎯 置信度阈值", minimum=0.1, maximum=1.0, value=0.5, step=0.1)
                        with gr.Row():
                            run_btn_img = gr.Button("🚀 开始识别", variant="primary", size="lg", elem_classes="gr-button")


        with gr.Column(scale=1):
            with gr.Group(elem_classes="output-section fade-in-up"):
                gr.HTML('<div class="input-title">📊 识别结果</div>')
                # 进度条
                progress_bar = gr.Progress()
                
                # 结果表格（默认显示）
                result_table = gr.Dataframe(
                    label="发票识别结果",
                    headers=["文件名", "开票日期", "价税合计小写"],
                    datatype=["str", "str", "str"],
                    elem_classes="gr-databox"
                )
                
                # 合并的导出下载按钮
                download_output = gr.DownloadButton("📥 导出并下载结果", variant="primary")
                
                # 详细结果标签页
                with gr.Tabs():
                    with gr.TabItem("🎯 JSON格式"):
                        result_output = gr.Textbox(label="", lines=12, max_lines=15, elem_classes="gr-textbox")
                    with gr.TabItem("📝 原始文本"):
                        table_output = gr.Dataframe(label="", headers=["序号", "文本内容", "置信度"], datatype=["number", "str", "number"], elem_classes="gr-databox")

    # 绑定PDF发票按钮事件
    run_btn_pdf.click(
        fn=process_pdf_invoice,
        inputs=[pdf_input, confidence_pdf],
        outputs=[result_output, result_table, table_output]
    )

    # 绑定图片发票按钮事件（暂时保留，后续可以优化）
    run_btn_img.click(
        fn=process_with_fields_image,
        inputs=[img_input, confidence_img],
        outputs=[result_output, result_table, table_output]
    )

    # 绑定导出下载按钮事件
    download_output.click(
        fn=export_table_data,
        inputs=[result_table],
        outputs=[download_output]
    )

if __name__ == "__main__":
    # demo.launch()
    demo.launch(mcp_server=True)

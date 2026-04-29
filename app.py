# -*- coding: utf-8 -*-
"""
发票OCR专用识别系统
基于RapidOCR的智能发票识别与字段提取平台
"""

import gradio as gr
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple
from PIL import Image

from ocr_engine import InvoiceImageProcessor, pdf_first_page_to_image, detect_file_type
from invoice_config import (
    get_invoice_types_list,
    get_all_field_patterns,
    validate_invoice_data,
)
from export import export_table_data


# 读取外部样式文件
def load_custom_css():
    """加载自定义CSS样式，兼容Gradio 6.0+"""
    try:
        with open('styles.css', 'r', encoding='utf-8') as f:
            css_content = f.read()
            updated_css = css_content + """
            .gradio-container {
                background: linear-gradient(135deg, #e3f2fd 0%, #f5f9ff 50%, #e8f5fd 100%) !important;
                background-attachment: fixed !important;
                background-size: cover !important;
            }
            body {
                background: transparent !important;
            }
            """
            return updated_css
    except FileNotFoundError:
        return """
        body {
            font-family: 'Segoe UI', sans-serif;
            background: transparent !important;
        }
        .gradio-container {
            background: linear-gradient(135deg, #e3f2fd 0%, #f5f9ff 50%, #e8f5fd 100%) !important;
            background-attachment: fixed !important;
            background-size: cover !important;
        }
        .gr-container {
            background: linear-gradient(135deg, #e3f2fd 0%, #f5f9ff 50%, #e8f5fd 100%) !important;
            background-attachment: fixed !important;
            background-size: cover !important;
        }
        .gr-button {
            background: linear-gradient(45deg, #667eea, #764ba2) !important;
            color: white !important;
        }
        .gr-group {
            background: rgba(255, 255, 255, 0.95) !important;
            border-radius: 15px !important;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08) !important;
        }
        .gr-databox {
            background: white !important;
            border: 2px solid #e2e8f0 !important;
        }
        .gr-textbox {
            background: white !important;
            border: 2px solid #e2e8f0 !important;
        }
        """
    except Exception as e:
        print(f"加载样式文件时出错: {e}")
        return ""


# 全局处理器实例
invoice_processor = InvoiceImageProcessor()


def process_pdf_invoice(pdf_files, confidence_threshold: float = 0.5, progress=gr.Progress()):
    try:
        all_results = []
        result_table_data = []
        all_table_data = []

        for i, pdf_file in enumerate(pdf_files):
            file_basename = os.path.basename(pdf_file.name)
            progress((i, len(pdf_files)), f"处理第 {i+1} 个PDF文件: {file_basename}")

            try:
                img = pdf_first_page_to_image(pdf_file)
                result_data, vis_text, table_data = invoice_processor.process_invoice(img, confidence_threshold)
                result_data["source_type"] = "PDF"
                result_data["processed_page"] = 1
                result_data["file_name"] = file_basename

                all_results.append(result_data)

                for row in table_data:
                    all_table_data.append([len(all_table_data) + 1, f"{file_basename}: {row[1]}", row[2]])

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
                result_table_data.append([file_basename, "处理失败", f"错误: {str(e)}"])

        progress(1, "处理完成")
        return json.dumps(all_results, ensure_ascii=False, indent=2), result_table_data, all_table_data
    except Exception as e:
        error_msg = f"批量PDF处理失败: {str(e)}"
        return json.dumps([{"error": error_msg}]), [["", "批量处理失败", f"错误: {str(e)}"]], [[0, "批量PDF处理失败", "0.000"]]


def process_mixed_input(file_input, confidence_threshold: float = 0.5):
    if file_input is None:
        return {"error": "请先上传文件"}, "请先上传文件", []
    file_type = detect_file_type(file_input.name)
    if file_type == "image":
        return process_with_fields_image(file_input, confidence_threshold)
    elif file_type == "pdf":
        return process_pdf_invoice(file_input, confidence_threshold)
    else:
        error_msg = "不支持的文件格式，请上传图像或PDF文件"
        return {"error": error_msg}, error_msg, [[0, "不支持的文件格式", "0.000"]]


def process_with_fields_image(img_path, confidence_threshold: float = 0.5):
    """处理图像发票，返回结构化数据、结构化表格和原始文本表格"""
    if img_path is None:
        return {"error": "请先上传图片"}, [["", "请先上传图片", ""]], []
    try:
        img_input = Image.open(img_path)
        result_data, vis_text, table_data = invoice_processor.process_invoice(img_input, confidence_threshold)
        result_data["source_type"] = "Image"
        result_data["file_name"] = os.path.basename(img_path) if isinstance(img_path, str) else "未知图片"

        file_name = result_data["file_name"]
        invoice_date = result_data["extracted_fields"].get("开票日期", "未识别")
        total_amount = result_data["extracted_fields"].get("价税合计小写", "未识别")
        result_table_data = [[file_name, invoice_date, total_amount]]

        return json.dumps(result_data, ensure_ascii=False, indent=2), result_table_data, table_data
    except Exception as e:
        error_msg = f"图片处理失败: {str(e)}"
        return {"error": error_msg}, [["", "处理失败", error_msg]], [[0, "图片处理失败", "0.000"]]


def export_invoice_config(confidence_threshold):
    """导出发票配置"""
    config_data = {
        "supported_invoice_types": get_invoice_types_list(),
        "confidence_threshold": confidence_threshold,
        "return_format": "JSON格式",
        "field_patterns": get_all_field_patterns(),
        "export_time": datetime.now().isoformat()
    }
    return json.dumps(config_data, ensure_ascii=False, indent=2)


# 加载自定义CSS样式
custom_css = load_custom_css()

# 创建Gradio界面
with gr.Blocks(
    title="🧾 发票OCR专用识别系统"
) as demo:
    gr.HTML(f'<style>{custom_css}</style>')

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
                progress_bar = gr.Progress()

                result_table = gr.Dataframe(
                    label="发票识别结果",
                    headers=["文件名", "开票日期", "价税合计小写"],
                    datatype=["str", "str", "str"],
                    elem_classes="gr-databox"
                )

                download_output = gr.DownloadButton("📥 导出并下载结果", variant="primary")

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

    # 绑定图片发票按钮事件
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
    demo.launch(mcp_server=True, server_name="0.0.0.0")

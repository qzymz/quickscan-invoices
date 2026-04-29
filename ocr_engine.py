# -*- coding: utf-8 -*-
"""OCR 图像处理模块 — PDF 转图片 + RapidOCR 调用"""

import os
from typing import Dict, List, Any, Tuple
from rapidocr import RapidOCR
from PIL import Image
import fitz  # PyMuPDF
import numpy as np
from datetime import datetime

from field_extractor import InvoiceFieldExtractor


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
        raise Exception(f"PDF转图片失败: {e}") from e


def detect_file_type(file_path: str) -> str:
    """检测文件类型"""
    if not file_path:
        return "unknown"
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
        return "image"
    elif file_extension == '.pdf':
        return "pdf"
    else:
        return "unknown"


class InvoiceImageProcessor:
    """发票图像处理引擎（门面类，委托给 InvoiceFieldExtractor）"""

    def __init__(self):
        self.ocr_engine = RapidOCR()
        self.field_extractor = InvoiceFieldExtractor()

    def process_invoice(self, img_input, confidence_threshold: float = 0.5) -> Tuple[Dict[str, Any], str, List[List[Any]]]:
        """处理发票图像，返回结构化数据和原始OCR数据"""
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

        text_list = ocr_result.txts if ocr_result.txts else []
        invoice_type = self.field_extractor.detect_invoice_type(text_list)
        extracted_fields = self.field_extractor.extract_fields(text_list, invoice_type)
        validation_result = self.field_extractor.validate(extracted_fields)

        # 构建原始OCR识别数据
        raw_ocr_results = []
        boxes = getattr(ocr_result, 'boxes', None)
        scores = getattr(ocr_result, 'scores', None)
        txts = getattr(ocr_result, 'txts', None)
        if boxes is not None and txts is not None and scores is not None:
            for text, box, score in zip(txts, boxes, scores):
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

        result_data = {
            "invoice_type": invoice_type,
            "confidence": float(np.mean(scores)) if scores is not None and len(scores) > 0 else 0.0,
            "processing_time": float(ocr_result.elapse),
            "timestamp": datetime.now().isoformat(),
            "raw_ocr_results": raw_ocr_results,
            "extracted_fields": extracted_fields,
            "validation": validation_result,
            "raw_text": text_list
        }

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

        table_data = []
        if text_list and scores is not None and len(scores) > 0:
            for i, (text, score) in enumerate(zip(text_list, scores)):
                table_data.append([i, text, f"{score:.3f}"])
        else:
            table_data = [[0, "未识别到文本", "0.000"]]

        return result_data, vis_text, table_data

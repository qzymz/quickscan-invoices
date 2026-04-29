# -*- coding: utf-8 -*-
"""发票字段提取模块 — 从 OCR 文本中检测发票类型并提取关键字段"""

import re
from typing import Dict, List, Any
from invoice_config import (
    INVOICE_TYPES,
    DATE_PATTERNS,
    validate_invoice_data,
)


class InvoiceFieldExtractor:
    """发票字段提取器"""

    def __init__(self):
        self.invoice_types = INVOICE_TYPES
        self.date_patterns = DATE_PATTERNS

    def detect_invoice_type(self, text_list: List[str]) -> str:
        """检测发票类型"""
        if not text_list:
            return "未知类型"

        combined_text = " ".join(text_list).lower()

        for invoice_type, config in self.invoice_types.items():
            keywords = config.get("keywords", [])
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    return invoice_type

        return "通用发票"

    def _extract_date(self, combined_text: str) -> str:
        """提取开票日期"""
        for pattern in self.date_patterns:
            match = re.search(pattern, combined_text)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_total_amount(self, lines: List[str]) -> str:
        """提取价税合计小写"""

        # 模式1: 价税合计 + 小写 + 货币符号
        for line in lines:
            if "价税合计" in line and ("小写" in line or "（小写）" in line) and ("￥" in line or "¥" in line):
                price_match = re.search(r"[￥¥]\s*([\d,]+\.?\d*)", line)
                if price_match:
                    return price_match.group(1).strip()

        # 模式2: 包含"价税合计"的行中查找金额
        for line in lines:
            if "价税合计" in line:
                price_match = re.search(r"[￥¥]\s*([\d,]+\.?\d*)", line)
                if price_match:
                    return price_match.group(1).strip()

        # 模式3: "（小写）" + 货币符号
        for line in lines:
            if "（小写）" in line and ("￥" in line or "¥" in line):
                price_match = re.search(r"[￥¥]\s*([\d,]+\.?\d*)", line)
                if price_match:
                    return price_match.group(1).strip()

        # 模式4: 所有带货币符号的行中选最大金额
        all_amounts = []
        for line in lines:
            if "￥" in line or "¥" in line:
                for match in re.finditer(r"[￥¥]\s*([\d,]+\.?\d*)", line):
                    amount_str = match.group(1).strip()
                    try:
                        amount = float(amount_str.replace(",", ""))
                        all_amounts.append((amount, amount_str))
                    except ValueError:
                        continue

        if all_amounts:
            all_amounts.sort(reverse=True)
            return all_amounts[0][1]

        return ""

    def extract_fields(self, text_list: List[str], detected_type: str = None) -> Dict[str, Any]:
        """提取发票字段（开票日期、价税合计小写）"""
        if not text_list:
            return {}

        extracted_fields = {}
        combined_text = " ".join(text_list)

        date_str = self._extract_date(combined_text)
        if date_str:
            extracted_fields["开票日期"] = date_str

        total_amount = self._extract_total_amount(text_list)
        if total_amount:
            extracted_fields["价税合计小写"] = total_amount

        return extracted_fields

    def validate(self, extracted_fields: Dict[str, Any]) -> Dict[str, Any]:
        """验证提取的字段"""
        return validate_invoice_data(extracted_fields)

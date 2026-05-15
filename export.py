# -*- coding: utf-8 -*-
"""Excel 导出模块"""

import tempfile
import pandas as pd


def export_table_data(table_data):
    """将表格数据导出为Excel格式并保存到临时文件"""
    if isinstance(table_data, pd.DataFrame):
        if table_data.empty:
            return None
        df = table_data
    elif isinstance(table_data, list):
        if not table_data:
            return None
        df = pd.DataFrame(table_data, columns=["文件名", "开票日期", "价税合计小写"])
    else:
        return None

    # 计算金额总计（NaN 值不计入总和，保留原文本显示）
    if "价税合计小写" in df.columns:
        numeric = pd.to_numeric(df["价税合计小写"], errors="coerce")
        total_amount = numeric.sum()
        # Replace numeric column back with original text, add total row
        df = df.copy()
        total_row = pd.DataFrame([{"文件名": "总计", "开票日期": "", "价税合计小写": f"¥{total_amount:,.2f}"}])
        df = pd.concat([df, total_row], ignore_index=True)

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
        with pd.ExcelWriter(tmp_file.name, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="发票识别结果")
        return tmp_file.name

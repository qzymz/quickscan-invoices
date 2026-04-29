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

    # 计算金额总计
    try:
        df['价税合计小写'] = pd.to_numeric(df['价税合计小写'], errors='coerce')
        total_amount = df['价税合计小写'].sum()
        total_row = pd.DataFrame([{'文件名': '总计', '开票日期': '', '价税合计小写': total_amount}])
        df = pd.concat([df, total_row], ignore_index=True)
    except Exception as e:
        print(f"计算金额总计失败: {e}")

    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
        with pd.ExcelWriter(tmp_file.name, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='发票识别结果')
        return tmp_file.name

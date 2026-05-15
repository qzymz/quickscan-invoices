# -*- coding: utf-8 -*-
"""测试 Excel 导出逻辑"""

import os
import pandas as pd
import pytest
from export import export_table_data


class TestExportTableData:
    """测试导出表格数据"""

    def test_export_list_data(self):
        table_data = [
            ["fp1.jpg", "2024年3月15日", "100.00"],
            ["fp2.jpg", "2024-03-20", "200.50"],
        ]
        result = export_table_data(table_data)
        assert result is not None
        assert os.path.exists(result)
        assert result.endswith('.xlsx')

        # 验证内容
        df = pd.read_excel(result, sheet_name='发票识别结果')
        assert len(df) == 3  # 2行数据 + 1行总计
        assert df.iloc[-1]['文件名'] == '总计'
        # 清理
        os.unlink(result)

    def test_export_dataframe(self):
        df = pd.DataFrame({
            "文件名": ["fp1.jpg"],
            "开票日期": ["2024-01-01"],
            "价税合计小写": ["50.00"]
        })
        result = export_table_data(df)
        assert result is not None
        assert os.path.exists(result)
        # 清理
        os.unlink(result)

    def test_export_empty_list_returns_none(self):
        assert export_table_data([]) is None

    def test_export_empty_dataframe_returns_none(self):
        df = pd.DataFrame()
        assert export_table_data(df) is None

    def test_export_invalid_type_returns_none(self):
        assert export_table_data("not a list or dataframe") is None

    def test_export_total_row_calculated_correctly(self):
        table_data = [
            ["a.jpg", "2024-01-01", "100.00"],
            ["b.jpg", "2024-01-02", "50.00"],
        ]
        result = export_table_data(table_data)
        df = pd.read_excel(result, sheet_name='发票识别结果')
        total_row = df[df['文件名'] == '总计']
        assert "150.00" in str(total_row.iloc[0]['价税合计小写'])
        # 清理
        os.unlink(result)

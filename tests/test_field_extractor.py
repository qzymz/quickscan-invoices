# -*- coding: utf-8 -*-
"""测试字段提取逻辑"""

import pytest
from field_extractor import InvoiceFieldExtractor


@pytest.fixture
def extractor():
    return InvoiceFieldExtractor()


class TestDetectInvoiceType:
    """测试发票类型检测"""

    def test_vat_special_invoice(self, extractor):
        text = ["增值税专用发票", "发票代码：12345678", "价税合计（小写）¥190.90"]
        assert extractor.detect_invoice_type(text) == "增值税专用发票"

    def test_vat_ordinary_invoice(self, extractor):
        text = ["增值税普通发票", "发票号码：87654321"]
        assert extractor.detect_invoice_type(text) == "增值税普通发票"

    def test_electronic_invoice(self, extractor):
        text = ["电子发票", "发票号码：99999999"]
        assert extractor.detect_invoice_type(text) == "电子发票"

    def test_machine_printed_invoice(self, extractor):
        text = ["通用机打发票", "商品名称：办公用品"]
        assert extractor.detect_invoice_type(text) == "通用机打发票"

    def test_handwritten_invoice(self, extractor):
        text = ["手写发票", "手写"]
        assert extractor.detect_invoice_type(text) == "手写发票"

    def test_unknown_type(self, extractor):
        text = ["这是一张普通的纸"]
        assert extractor.detect_invoice_type(text) == "通用发票"

    def test_empty_text(self, extractor):
        assert extractor.detect_invoice_type([]) == "未知类型"


class TestExtractFields:
    """测试字段提取"""

    def test_extract_date_chinese_format(self, extractor):
        text = ["开票日期：2024年3月15日", "价税合计（小写）¥100.00"]
        result = extractor.extract_fields(text)
        assert result["开票日期"] == "2024年3月15日"

    def test_extract_date_dash_format(self, extractor):
        text = ["开票日期: 2024-03-15", "价税合计（小写）¥100.00"]
        result = extractor.extract_fields(text)
        assert result["开票日期"] == "2024-03-15"

    def test_extract_total_amount_with_label(self, extractor):
        text = ["价税合计（小写）¥190.90"]
        result = extractor.extract_fields(text)
        assert result["价税合计小写"] == "190.90"

    def test_extract_total_amount_with_comma(self, extractor):
        text = ["价税合计（小写）¥1,234.56"]
        result = extractor.extract_fields(text)
        assert result["价税合计小写"] == "1,234.56"

    def test_extract_fallback_to_largest_amount(self, extractor):
        text = ["税额 ¥10.00", "价税合计 ¥500.00"]
        result = extractor.extract_fields(text)
        assert result["价税合计小写"] == "500.00"

    def test_empty_text_returns_empty_dict(self, extractor):
        assert extractor.extract_fields([]) == {}

    def test_no_matching_fields_returns_empty(self, extractor):
        text = ["一些无关的文本"]
        result = extractor.extract_fields(text)
        assert result == {}

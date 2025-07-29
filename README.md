---
# 详细文档见https://modelscope.cn/docs/%E5%88%9B%E7%A9%BA%E9%97%B4%E5%8D%A1%E7%89%87
domain: #领域：cv/nlp/audio/multi-modal/AutoML
# - cv
tags: #自定义标签
-
datasets: #关联数据集
  evaluation:
  #- iic/ICDAR13_HCTR_Dataset
  test:
  #- iic/MTWI
  train:
  #- iic/SIBR
models: #关联模型
#- iic/ofa_ocr-recognition_general_base_zh

## 启动文件(若SDK为Gradio/Streamlit，默认为app.py, 若为Static HTML, 默认为index.html)
# deployspec:
#   entry_file: app.py
license: Apache License 2.0
---
# 🧾 发票OCR识别系统

基于RapidOCR的智能发票识别系统，支持多种发票类型的自动识别和字段提取。

## ✨ 主要功能

- **多类型发票识别** - 支持增值税专用发票、普通发票、电子发票等
- **智能字段提取** - 自动提取发票号码、开票日期、金额、税额等关键信息
- **Web界面** - 基于Gradio的现代化用户界面
- **多格式输出** - 支持JSON和结构化文本输出

## 🚀 快速开始

### 环境要求
- Python 3.7+
- Windows/Linux/MacOS

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动系统
```bash
python app.py
```

启动后访问 `http://localhost:7860` 即可使用系统。

## 📋 使用方法

1. **上传发票图片** - 点击上传区域选择发票图片
2. **调整参数** - 设置置信度阈值（可选）
3. **开始识别** - 点击"开始识别"按钮
4. **查看结果** - 在结果区域查看识别结果

## 📁 项目结构

```
invoice_ocr/
├── app.py                 # 主程序文件
├── invoice_config.py      # 发票配置文件
├── invoice_config.json    # 配置文件
├── requirements.txt       # 依赖文件
├── styles.css            # 样式文件
├── README.md             # 项目说明
└── images/               # 示例图片
    ├── fp1.jpg
    ├── fp2.jpg
    ├── fp3.jpg
    ├── fp4.jpg
    └── fp5.jpg
```

## 🔧 技术栈

- **RapidOCR** - 高性能OCR引擎
- **Gradio** - 现代化Web界面
- **正则表达式** - 智能字段提取
- **Python** - 后端处理逻辑

## 📊 支持的发票类型

- 增值税专用发票
- 增值税普通发票
- 电子发票
- 通用机打发票
- 手写发票

## 🔍 识别字段

### 通用字段
- 发票号码、发票代码
- 开票日期
- 购买方/销售方名称
- 金额、税额、价税合计

### 专用发票字段
- 纳税人识别号
- 地址、电话
- 开户行及账号
- 商品名称、规格型号
- 数量、单价、税率
- 收款人、复核、开票人

## 📄 许可证

本项目采用 Apache License 2.0 许可证。

---

**注意**：本系统仅用于学习和研究目的，实际使用时请确保符合相关法律法规。
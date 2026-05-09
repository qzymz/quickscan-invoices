// 发票OCR识别系统 - 前端交互逻辑

(function () {
    "use strict";

    // 全局状态
    let tableData = [];
    let isProcessing = false;

    // DOM 元素
    const els = {
        pdfFiles: document.getElementById("pdf-files"),
        pdfConfidence: document.getElementById("pdf-confidence"),
        pdfConfValue: document.getElementById("pdf-confidence-value"),
        btnPdfRecognize: document.getElementById("btn-pdf-recognize"),
        imgFiles: document.getElementById("image-files"),
        imgConfidence: document.getElementById("image-confidence"),
        imgConfValue: document.getElementById("image-confidence-value"),
        btnImgRecognize: document.getElementById("btn-image-recognize"),
        resultTbody: document.getElementById("result-tbody"),
        btnExport: document.getElementById("btn-export"),
        jsonOutput: document.getElementById("json-output"),
        rawTbody: document.getElementById("raw-tbody"),
        progressContainer: document.getElementById("progress-container"),
        progressBar: document.getElementById("progress-bar"),
        progressText: document.getElementById("progress-text"),
    };

    // Tab 切换
    document.querySelectorAll(".tab-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
        });
    });

    // 详情标签页切换
    document.querySelectorAll(".detail-tab-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".detail-tab-btn").forEach((b) => b.classList.remove("active"));
            document.querySelectorAll(".detail-content").forEach((c) => c.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById("detail-" + btn.dataset.detail).classList.add("active");
        });
    });

    // 置信度滑块更新
    els.pdfConfidence.addEventListener("input", () => {
        els.pdfConfValue.textContent = els.pdfConfidence.value;
    });
    els.imgConfidence.addEventListener("input", () => {
        els.imgConfValue.textContent = els.imgConfidence.value;
    });

    // 更新结果表格
    function updateResultTable(rows) {
        tableData = rows;
        els.resultTbody.innerHTML = "";
        if (rows.length === 0) {
            els.resultTbody.innerHTML = '<tr><td colspan="3" class="empty-msg">无数据</td></tr>';
            els.btnExport.disabled = true;
            return;
        }
        rows.forEach((row) => {
            const tr = document.createElement("tr");
            row.forEach((cell) => {
                const td = document.createElement("td");
                td.textContent = cell;
                tr.appendChild(td);
            });
            els.resultTbody.appendChild(tr);
        });
        els.btnExport.disabled = false;
    }

    // 显示 JSON 结果
    function showJsonResult(results) {
        els.jsonOutput.textContent = JSON.stringify(results, null, 2);
    }

    // 显示原始文本
    function showRawTable(rawOcrResults) {
        els.rawTbody.innerHTML = "";
        if (!rawOcrResults || rawOcrResults.length === 0) {
            els.rawTbody.innerHTML = '<tr><td colspan="3">无数据</td></tr>';
            return;
        }
        rawOcrResults.forEach((item, i) => {
            const tr = document.createElement("tr");
            const tdIdx = document.createElement("td");
            tdIdx.textContent = i;
            const tdText = document.createElement("td");
            tdText.textContent = item.text || "";
            const tdScore = document.createElement("td");
            tdScore.textContent = (item.score || 0).toFixed(3);
            tr.appendChild(tdIdx);
            tr.appendChild(tdText);
            tr.appendChild(tdScore);
            els.rawTbody.appendChild(tr);
        });
    }

    // 显示/隐藏进度条
    function showProgress(progress, total) {
        els.progressContainer.style.display = "flex";
        els.progressBar.style.setProperty("--progress", ((progress / total) * 100) + "%");
        els.progressText.textContent = `处理中 ${progress}/${total}...`;
    }

    function hideProgress() {
        els.progressContainer.style.display = "none";
    }

    function setButtonLoading(loading) {
        isProcessing = loading;
        document.querySelectorAll(".btn-primary").forEach((btn) => {
            btn.disabled = loading;
        });
    }

    // 单文件识别（图片）
    els.btnImgRecognize.addEventListener("click", async () => {
        const files = els.imgFiles.files;
        if (files.length === 0) {
            alert("请先选择图片文件");
            return;
        }
        setButtonLoading(true);
        hideProgress();
        const confidence = parseFloat(els.imgConfidence.value);

        try {
            const results = [];
            const rows = [];
            const formData = new FormData();

            for (let i = 0; i < files.length; i++) {
                formData.append("file", files[i]);
                formData.append("confidence", confidence);

                const resp = await fetch("/api/recognize", {
                    method: "POST",
                    body: formData,
                });

                if (!resp.ok) {
                    const err = await resp.json();
                    results.push({ error: err.detail, file_name: files[i].name });
                    rows.push([files[i].name, "处理失败", `错误: ${err.detail}`]);
                    continue;
                }

                const data = await resp.json();
                results.push(data.result);
                rows.push(data.table_row);

                showProgress(i + 1, files.length);
                updateResultTable(rows);
                showJsonResult(results);

                // 显示第一个结果的原始文本
                if (data.result.raw_ocr_results) {
                    showRawTable(data.result.raw_ocr_results);
                }

                // 清空 FormData
                formData.delete("file");
            }
        } catch (e) {
            alert("请求失败: " + e.message);
        } finally {
            setButtonLoading(false);
            setTimeout(hideProgress, 2000);
        }
    });

    // 批量识别（PDF）
    els.btnPdfRecognize.addEventListener("click", async () => {
        const files = els.pdfFiles.files;
        if (files.length === 0) {
            alert("请先选择PDF文件");
            return;
        }
        setButtonLoading(true);
        hideProgress();
        const confidence = parseFloat(els.pdfConfidence.value);

        try {
            const formData = new FormData();
            for (const file of files) {
                formData.append("files", file);
            }
            formData.append("confidence", confidence);

            // 提交批量任务
            const resp = await fetch("/api/batch-recognize", {
                method: "POST",
                body: formData,
            });

            if (!resp.ok) {
                const err = await resp.json();
                alert("提交失败: " + err.detail);
                setButtonLoading(false);
                return;
            }

            const { task_id, total } = await resp.json();

            // 轮询进度
            const pollInterval = setInterval(async () => {
                const statusResp = await fetch("/api/status/" + task_id);
                const status = await statusResp.json();

                showProgress(status.progress, status.total);

                if (status.table_data) {
                    updateResultTable(status.table_data);
                    showJsonResult(status.results);

                    // 显示第一个结果的原始文本
                    if (status.results.length > 0 && status.results[0].raw_ocr_results) {
                        showRawTable(status.results[0].raw_ocr_results);
                    }
                }

                if (status.status === "done" || status.status === "error") {
                    clearInterval(pollInterval);
                    setTimeout(hideProgress, 2000);
                    setButtonLoading(false);
                }
            }, 500);
        } catch (e) {
            alert("请求失败: " + e.message);
            setButtonLoading(false);
        }
    });

    // 导出 Excel
    els.btnExport.addEventListener("click", async () => {
        if (tableData.length === 0) {
            alert("无数据可导出");
            return;
        }

        try {
            const resp = await fetch("/api/export", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(tableData),
            });

            if (!resp.ok) {
                const err = await resp.json();
                alert("导出失败: " + err.detail);
                return;
            }

            // 触发下载
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "invoice_results.xlsx";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (e) {
            alert("导出失败: " + e.message);
        }
    });
})();

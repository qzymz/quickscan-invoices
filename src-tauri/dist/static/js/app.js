// QuickScan Invoices — 前端交互逻辑

(function () {
    "use strict";

    // ========== 主题切换 ==========
    function initTheme() {
        const saved = localStorage.getItem("qs-theme") || "light";
        document.documentElement.dataset.theme = saved;
        updateThemeIcon(saved);
    }

    function updateThemeIcon(theme) {
        const lightIcon = document.querySelector(".theme-icon-light");
        const darkIcon = document.querySelector(".theme-icon-dark");
        if (lightIcon && darkIcon) {
            lightIcon.style.display = theme === "light" ? "none" : "block";
            darkIcon.style.display = theme === "light" ? "block" : "none";
        }
    }

    function toggleTheme() {
        const current = document.documentElement.dataset.theme || "light";
        const next = current === "light" ? "dark" : "light";
        document.documentElement.dataset.theme = next;
        localStorage.setItem("qs-theme", next);
        updateThemeIcon(next);
    }

    initTheme();
    const themeToggle = document.getElementById("theme-toggle");
    if (themeToggle) themeToggle.addEventListener("click", toggleTheme);

    // ========== 状态 ==========
    let tableData = [];
    let uploadedFiles = { image: [], pdf: [] };

    // ========== DOM 元素 ==========
    const els = {
        pdfFiles: document.getElementById("pdf-files"),
        pdfConfidence: document.getElementById("pdf-confidence"),
        pdfConfValue: document.getElementById("pdf-confidence-value"),
        btnPdfRecognize: null, // PDF tab uses same button as image
        imgFiles: document.getElementById("image-files"),
        imgConfidence: document.getElementById("image-confidence"),
        imgConfValue: document.getElementById("image-confidence-value"),
        btnImgRecognize: document.getElementById("btn-image-recognize"),
        resultTbody: document.getElementById("result-tbody"),
        btnExport: document.getElementById("btn-export"),
        jsonOutput: document.getElementById("json-output"),
        rawTbody: document.getElementById("raw-tbody"),
        progressSection: document.getElementById("progress-section"),
        progressFill: document.getElementById("progress-fill"),
        progressPct: document.getElementById("progress-pct"),
        fileCount: document.getElementById("file-count"),
        statusIndicator: document.getElementById("status-indicator"),
        statCount: document.getElementById("stat-count"),
        statTotal: document.getElementById("stat-total"),
        statRate: document.getElementById("stat-rate"),
        imageFileList: document.getElementById("image-file-list"),
        pdfFileList: document.getElementById("pdf-file-list"),
        imageDrop: document.getElementById("image-drop"),
        pdfDrop: document.getElementById("pdf-drop"),
        toastContainer: document.getElementById("toast-container"),
        bottomTime: document.getElementById("bottom-time"),
    };

    // ========== 时钟 ==========
    function updateTime() {
        const now = new Date();
        els.bottomTime.textContent = now.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    }
    updateTime();
    setInterval(updateTime, 1000);

    // ========== Toast 通知 ==========
    function showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        els.toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.classList.add("toast-out");
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ========== API error detection ==========
    async function checkApiConnection() {
        try {
            const resp = await fetch(window.API_BASE + "/", { method: "GET" });
            return resp.ok;
        } catch (e) {
            return false;
        }
    }

    // Check API connection on load (only in Tauri)
    setTimeout(async () => {
        if (window.API_BASE && window.API_BASE.includes('localhost')) {
            const connected = await checkApiConnection();
            if (!connected) {
                showToast("无法连接到 OCR 服务，请重启应用", "error");
                const indicator = document.getElementById("status-indicator");
                if (indicator) {
                    indicator.className = "status-indicator error";
                    const label = indicator.querySelector(".status-label");
                    if (label) label.textContent = "离线";
                }
            }
        }
    }, 3000);

    // ========== Tab 切换 ==========
    document.querySelectorAll(".seg-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("active"));
            document.querySelectorAll(".panel .tab-content").forEach((c) => c.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
        });
    });

    document.querySelectorAll(".detail-tab").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".detail-tab").forEach((b) => b.classList.remove("active"));
            document.querySelectorAll(".detail-panel").forEach((c) => c.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById("detail-" + btn.dataset.detail).classList.add("active");
        });
    });

    // ========== 置信度滑块 ==========
    els.imgConfidence.addEventListener("input", () => {
        els.imgConfValue.textContent = els.imgConfidence.value;
    });
    els.pdfConfidence.addEventListener("input", () => {
        els.pdfConfValue.textContent = els.pdfConfidence.value;
    });

    // ========== 拖拽上传 ==========
    function setupDrop(dropZone, inputEl, type) {
        ["dragenter", "dragover"].forEach((evt) => {
            dropZone.addEventListener(evt, (e) => {
                e.preventDefault();
                dropZone.classList.add("drag-over");
            });
        });
        ["dragleave", "drop"].forEach((evt) => {
            dropZone.addEventListener(evt, (e) => {
                e.preventDefault();
                dropZone.classList.remove("drag-over");
            });
        });
        dropZone.addEventListener("drop", (e) => {
            const files = Array.from(e.dataTransfer.files);
            addFiles(type, files);
        });
        inputEl.addEventListener("change", () => {
            addFiles(type, Array.from(inputEl.files));
        });
    }

    function addFiles(type, files) {
        uploadedFiles[type] = [...uploadedFiles[type], ...files];
        renderFileList(type);
        updateFileCount();
    }

    function removeFile(type, index) {
        uploadedFiles[type].splice(index, 1);
        renderFileList(type);
        updateFileCount();
    }

    function renderFileList(type) {
        const listEl = type === "image" ? els.imageFileList : els.pdfFileList;
        listEl.innerHTML = "";
        uploadedFiles[type].forEach((file, i) => {
            const item = document.createElement("div");
            item.className = "file-item";
            item.innerHTML = `
                <svg class="file-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    ${type === "pdf"
                        ? '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/>'
                        : '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>'}
                </svg>
                <span class="file-item-name">${file.name}</span>
                <button class="file-item-remove" data-type="${type}" data-index="${i}">×</button>
            `;
            listEl.appendChild(item);
        });
        listEl.querySelectorAll(".file-item-remove").forEach((btn) => {
            btn.addEventListener("click", () => {
                removeFile(btn.dataset.type, parseInt(btn.dataset.index));
            });
        });
    }

    function updateFileCount() {
        const activeTab = document.querySelector(".seg-btn.active").dataset.tab;
        const files = uploadedFiles[activeTab];
        els.fileCount.textContent = `${files.length} 个文件`;
    }

    // 监听 tab 切换更新计数
    document.querySelectorAll(".seg-btn").forEach((btn) => {
        btn.addEventListener("click", updateFileCount);
    });

    setupDrop(els.imageDrop, els.imgFiles, "image");
    setupDrop(els.pdfDrop, els.pdfFiles, "pdf");

    // ========== 状态更新 ==========
    function setStatus(status) {
        els.statusIndicator.className = "status-indicator";
        const label = els.statusIndicator.querySelector(".status-label");
        switch (status) {
            case "processing":
                els.statusIndicator.classList.add("processing");
                label.textContent = "处理中";
                break;
            case "error":
                els.statusIndicator.classList.add("error");
                label.textContent = "出错";
                break;
            case "done":
                els.statusIndicator.classList.add("done");
                label.textContent = "完成";
                break;
            default:
                label.textContent = "就绪";
        }
    }

    // ========== 统计卡片 ==========
    function updateStats(rows, results) {
        const count = rows.length;
        els.statCount.textContent = count;

        let total = 0;
        let successCount = 0;
        rows.forEach((row) => {
            const val = row[2];
            if (val && typeof val === "string" && val !== "未识别" && !val.startsWith("错误")) {
                total += parseFloat(val.replace(/,/g, "")) || 0;
                successCount++;
            }
        });
        els.statTotal.textContent = `¥ ${total.toFixed(2)}`;
        els.statRate.textContent = count > 0 ? `${((successCount / count) * 100).toFixed(0)}%` : "--";
    }

    // ========== 结果表格 ==========
    function updateResultTable(rows, results) {
        tableData = rows;
        els.resultTbody.innerHTML = "";

        if (rows.length === 0) {
            els.resultTbody.innerHTML = `<tr class="empty-row">
                <td colspan="3"><div class="empty-state">
                    <div class="empty-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg></div>
                    <p>等待上传发票</p><span>上传PDF或图片发票开始识别</span>
                </div></td></tr>`;
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

    // ========== JSON / Raw ==========
    function showJsonResult(results) {
        els.jsonOutput.textContent = JSON.stringify(results, null, 2);
    }

    function showRawTable(rawOcrResults) {
        els.rawTbody.innerHTML = "";
        if (!rawOcrResults || rawOcrResults.length === 0) {
            return;
        }
        rawOcrResults.forEach((item, i) => {
            const tr = document.createElement("tr");
            const tdIdx = document.createElement("td");
            tdIdx.textContent = i + 1;
            const tdText = document.createElement("td");
            tdText.textContent = item.text || "";
            const tdScore = document.createElement("td");
            tdScore.textContent = ((item.score || 0) * 100).toFixed(0) + "%";
            tr.appendChild(tdIdx);
            tr.appendChild(tdText);
            tr.appendChild(tdScore);
            els.rawTbody.appendChild(tr);
        });
    }

    // ========== 进度 ==========
    function showProgress(progress, total) {
        els.progressSection.classList.add("visible");
        const pct = Math.round((progress / total) * 100);
        els.progressFill.style.width = pct + "%";
        els.progressPct.textContent = pct + "%";
    }

    function hideProgress() {
        els.progressSection.classList.remove("visible");
        els.progressFill.style.width = "0%";
    }

    function setButtonsLoading(loading) {
        document.querySelectorAll(".btn-accent").forEach((btn) => {
            btn.disabled = loading;
        });
    }

    // ========== 统一识别入口 ==========
    const oldBtn = els.btnImgRecognize;
    const newBtn = oldBtn.cloneNode(true);
    oldBtn.parentNode.replaceChild(newBtn, oldBtn);

    newBtn.addEventListener("click", async () => {
        const activeTab = document.querySelector(".seg-btn.active").dataset.tab;
        if (activeTab === "pdf") {
            await processBatch("pdf");
        } else {
            await processBatch("image");
        }
    });

    async function processBatch(fileType) {
        const files = fileType === "pdf" ? uploadedFiles.pdf : uploadedFiles.image;
        if (files.length === 0) {
            showToast(fileType === "pdf" ? "请先选择或拖拽PDF文件" : "请先选择或拖拽图片文件", "warning");
            return;
        }

        setButtonsLoading(true);
        setStatus("processing");
        hideProgress();
        const confidence = fileType === "pdf"
            ? parseFloat(els.pdfConfidence.value)
            : parseFloat(els.imgConfidence.value);

        try {
            const formData = new FormData();
            for (const file of files) {
                formData.append("files", file);
            }
            formData.append("confidence", confidence);

            const resp = await fetch(window.API_BASE + "/api/batch-recognize", { method: "POST", body: formData });

            if (!resp.ok) {
                let detail = "未知错误";
                try { const err = await resp.json(); detail = err.detail || detail; } catch (_) {}
                showToast("提交失败: " + detail, "error");
                setStatus("error");
                setButtonsLoading(false);
                return;
            }

            const { task_id, total } = await resp.json();
            const pollInterval = setInterval(async () => {
                try {
                    const statusResp = await fetch(window.API_BASE + "/api/status/" + task_id);
                    if (!statusResp.ok) { clearInterval(pollInterval); return; }
                    const status = await statusResp.json();

                    showProgress(status.progress, status.total);

                    if (status.table_data) {
                        updateResultTable(status.table_data, status.results);
                        showJsonResult(status.results);
                        updateStats(status.table_data, status.results);
                        if (status.results.length > 0 && status.results[0].raw_ocr_results) {
                            showRawTable(status.results[0].raw_ocr_results);
                        }
                    }

                    if (status.status === "done" || status.status === "error") {
                        clearInterval(pollInterval);
                        if (status.status === "done") {
                            showToast(`批量识别完成，共 ${status.total} 个文件`, "success");
                        } else {
                            showToast("批量识别出错", "error");
                        }
                        setStatus("done");
                        setTimeout(() => { hideProgress(); setStatus(""); }, 3000);
                        setButtonsLoading(false);
                    }
                } catch (e) {
                    clearInterval(pollInterval);
                    showToast("请求失败: " + e.message, "error");
                    setStatus("error");
                    setButtonsLoading(false);
                }
            }, 500);
        } catch (e) {
            showToast("请求失败: " + e.message, "error");
            setStatus("error");
            setButtonsLoading(false);
        }
    }

    // ========== 导出 Excel ==========
    els.btnExport.addEventListener("click", async () => {
        if (tableData.length === 0) {
            showToast("无数据可导出", "warning");
            return;
        }

        try {
            const resp = await fetch(window.API_BASE + "/api/export", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(tableData),
            });

            if (!resp.ok) {
                let detail = "导出失败";
                try { const err = await resp.json(); detail = err.detail || detail; } catch (_) {}
                showToast("导出失败: " + detail, "error");
                return;
            }

            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "invoice_results.xlsx";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast("导出成功", "success");
        } catch (e) {
            showToast("导出失败: " + e.message, "error");
        }
    });
})();

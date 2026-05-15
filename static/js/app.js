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
    let uploadedFiles = [];  // Unified file list
    const PDF_EXTS = new Set([".pdf"]);
    const IMAGE_EXTS = new Set([".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".webp"]);

    function detectFileType(filename) {
        const ext = "." + filename.split(".").pop().toLowerCase();
        if (PDF_EXTS.has(ext)) return "pdf";
        if (IMAGE_EXTS.has(ext)) return "image";
        return "unknown";
    }

    // ========== DOM 元素 ==========
    const els = {
        filesInput: document.getElementById("files-input"),
        confidence: document.getElementById("confidence"),
        confValue: document.getElementById("confidence-value"),
        btnRecognize: document.getElementById("btn-recognize"),
        resultTbody: document.getElementById("result-tbody"),
        btnExport: document.getElementById("btn-export"),
        jsonOutput: document.getElementById("json-output"),
        rawTbody: document.getElementById("raw-tbody"),
        rawFileSelect: document.getElementById("raw-file-select"),
        progressSection: document.getElementById("progress-section"),
        progressFill: document.getElementById("progress-fill"),
        progressPct: document.getElementById("progress-pct"),
        fileCount: document.getElementById("file-count"),
        statusIndicator: document.getElementById("status-indicator"),
        statCount: document.getElementById("stat-count"),
        statTotal: document.getElementById("stat-total"),
        statRate: document.getElementById("stat-rate"),
        fileList: document.getElementById("file-list"),
        dropZone: document.getElementById("drop-zone"),
        toastContainer: document.getElementById("toast-container"),
        bottomTime: document.getElementById("bottom-time"),
    };

    // ========== 时钟 ==========
    function updateTime() {
        const now = new Date();
        els.bottomTime.textContent = now.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "second" });
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

    // ========== 置信度滑块 ==========
    els.confidence.addEventListener("input", () => {
        els.confValue.textContent = els.confidence.value;
    });

    // ========== 拖拽上传 ==========
    function setupDrop(dropZone, inputEl) {
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
            e.preventDefault();
            const files = Array.from(e.dataTransfer.files);
            addFiles(files);
        });
        inputEl.addEventListener("change", () => {
            addFiles(Array.from(inputEl.files));
            inputEl.value = "";
        });
    }

    function addFiles(files) {
        const valid = files.filter(f => detectFileType(f.name) !== "unknown");
        const invalid = files.length - valid.length;
        uploadedFiles = [...uploadedFiles, ...valid];
        renderFileList();
        updateFileCount();
        if (invalid > 0) showToast(`${invalid} 个文件格式不支持`, "warning");
    }

    function removeFile(index) {
        uploadedFiles.splice(index, 1);
        renderFileList();
        updateFileCount();
    }

    function renderFileList() {
        els.fileList.innerHTML = "";
        if (uploadedFiles.length === 0) {
            els.fileList.innerHTML = '<div class="empty-hint">拖拽文件或点击上传</div>';
            return;
        }
        uploadedFiles.forEach((file, i) => {
            const type = detectFileType(file.name);
            const item = document.createElement("div");
            item.className = "file-item";

            const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            svg.setAttribute("class", "file-item-icon");
            svg.setAttribute("viewBox", "0 0 24 24");
            svg.setAttribute("fill", "none");
            svg.setAttribute("stroke", "currentColor");
            svg.setAttribute("stroke-width", "1.5");
            svg.innerHTML = type === "pdf"
                ? '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/>'
                : '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>';
            item.appendChild(svg);

            const nameSpan = document.createElement("span");
            nameSpan.className = "file-item-name";
            nameSpan.textContent = file.name;
            item.appendChild(nameSpan);

            const removeBtn = document.createElement("button");
            removeBtn.className = "file-item-remove";
            removeBtn.textContent = "×";
            removeBtn.addEventListener("click", () => {
                removeFile(i);
            });
            item.appendChild(removeBtn);

            els.fileList.appendChild(item);
        });
    }

    function updateFileCount() {
        els.fileCount.textContent = `${uploadedFiles.length} 个文件`;
    }

    setupDrop(els.dropZone, els.filesInput);
    renderFileList();

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
        tableData = [...tableData, ...rows];  // Accumulate
        els.resultTbody.innerHTML = "";

        if (tableData.length === 0) {
            els.resultTbody.innerHTML = `<tr class="empty-row">
                <td colspan="3"><div class="empty-state">
                    <div class="empty-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg></div>
                    <p>等待上传发票</p><span>上传PDF或图片发票开始识别</span>
                </div></td></tr>`;
            els.btnExport.disabled = true;
            return;
        }

        tableData.forEach((row) => {
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
    let lastResults = [];

    function showJsonResult(results) {
        lastResults = results;
        els.jsonOutput.textContent = JSON.stringify(results, null, 2);
        updateRawFileSelect(results);
    }

    function updateRawFileSelect(results) {
        if (!els.rawFileSelect) return;
        els.rawFileSelect.innerHTML = '<option value="all">全部文件</option>';
        results.forEach((r, i) => {
            const opt = document.createElement("option");
            opt.value = String(i);
            opt.textContent = r.file_name || `文件 ${i + 1}`;
            els.rawFileSelect.appendChild(opt);
        });
        if (els.rawFileSelect) els.rawFileSelect.onchange = () => showRawForSelection(results);
    }

    function showRawForSelection(results) {
        const val = els.rawFileSelect ? els.rawFileSelect.value : "all";
        if (val === "all") {
            const all = [];
            results.forEach(r => {
                if (r.raw_ocr_results) {
                    all.push(...r.raw_ocr_results.map(t => ({ ...t, _file: r.file_name })));
                }
            });
            showRawTable(all);
        } else {
            const idx = parseInt(val);
            if (results[idx] && results[idx].raw_ocr_results) {
                showRawTable(results[idx].raw_ocr_results);
            }
        }
    }

    function showRawTable(rawOcrResults) {
        els.rawTbody.innerHTML = "";
        if (!rawOcrResults || rawOcrResults.length === 0) {
            return;
        }
        rawOcrResults.forEach((item, i) => {
            const tr = document.createElement("tr");
            if (item._file) {
                const tdFile = document.createElement("td");
                tdFile.textContent = item._file;
                tr.appendChild(tdFile);
            }
            const tdIdx = document.createElement("td");
            tdIdx.textContent = i + 1;
            const tdText = document.createElement("td");
            tdText.textContent = item.text || "";
            const tdScore = document.createElement("td");
            tdScore.textContent = ((item.score || 0) * 100).toFixed(0) + "%";
            if (item._file) tr.appendChild(tdFile || tdIdx);
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
    const oldBtn = els.btnRecognize;
    const newBtn = oldBtn.cloneNode(true);
    oldBtn.parentNode.replaceChild(newBtn, oldBtn);

    newBtn.addEventListener("click", async () => {
        if (uploadedFiles.length === 0) {
            showToast("请先选择或拖拽文件", "warning");
            return;
        }
        await processBatch();
    });

    async function processBatch() {
        setButtonsLoading(true);
        setStatus("processing");
        hideProgress();
        const confidence = parseFloat(els.confidence.value);

        try {
            const formData = new FormData();
            for (const file of uploadedFiles) {
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

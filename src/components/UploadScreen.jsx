import { useState, useRef, useEffect } from "react";
import "./CasesScreen.css";


function UploadScreen({ authToken, toPersianDigits, onUploadSuccess }) {
  const [activeView, setActiveView] = useState("upload"); // upload | analysis
  const documentInputRef = useRef(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [allDone, setAllDone] = useState(false);
  const [hasFailure, setHasFailure] = useState(false);
  const [newStoryId, setNewStoryId] = useState(null);

  const handleDocumentsSelect = (event) => {
    const files = Array.from(event.target.files || []);
    if (files.length === 0) return;
    const allowedExtensions = /\.(jpg|jpeg|png|webp|pdf)$/i;
    const validFiles = [];
    files.forEach((file) => {
      if (!allowedExtensions.test(file.name)) return;
      if (file.size === 0 || file.size > 10 * 1024 * 1024) return;
      validFiles.push({
        id: `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2, 8)}`,
        file, status: "ready", taskId: null, ocrText: "", extractedData: null, error: "", fileHash: "", paperlessId: null, // ⬅️ paperlessId اینجا اضافه شد
      });
    });
    setSelectedFiles((prev) => [...prev, ...validFiles]);
    if (documentInputRef.current) documentInputRef.current.value = "";
  };

  const updateFileById = (id, patch) => {
    setSelectedFiles((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  };

  const computeFileHash = async (file) => {
    const buffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  };

  const checkFileDuplicate = async (fileHash) => {
    try {
      const response = await fetch("http://127.0.0.1:8001/api/check-file-duplicate/", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({ file_hash: fileHash }),
      });
      if (response.status === 409) {
        const data = await response.json();
        return { isDuplicate: true, message: data.message };
      }
      return { isDuplicate: false };
    } catch (err) {
      return { isDuplicate: false };
    }
  };

  const pollTask = async (fileItem) => {
    const maxAttempts = 400;
    const interval = 3000;
    await new Promise((resolve) => setTimeout(resolve, 3000));
    
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, interval));
      try {
        const response = await fetch(
          `http://127.0.0.1:8001/api/paperless/task/${fileItem.taskId}/`,
          { headers: { Authorization: `Bearer ${authToken}` } }
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          if (response.status === 404) continue;
          updateFileById(fileItem.id, { status: "error", error: data.message || "ارتباط با سرویس تحلیل برقرار نشد." });
          return;
        }
        const tasks = Array.isArray(data) ? data : Array.isArray(data?.results) ? data.results : data && typeof data === "object" ? [data] : [];
        const task = tasks.find((item) => String(item.task_id ?? "") === String(fileItem.taskId)) ?? tasks[0];
        if (!task) continue;
        const taskStatus = String(task.status ?? "").toLowerCase();
        
        if (taskStatus === "success") {
          const docId = task.related_document_ids?.[0] ?? task.related_document;
          if (docId) {
            const docResponse = await fetch(
              `http://127.0.0.1:8001/api/paperless/document/${docId}/`,
              { headers: { Authorization: `Bearer ${authToken}` } }
            );
            if (docResponse.ok) {
              const docData = await docResponse.json();
              const ocrText = docData.content || "";
              try {
                const aiResponse = await fetch("http://127.0.0.1:8001/api/ai/analyze/", {
                  method: "POST",
                  headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
                  body: JSON.stringify({ text: ocrText, file_hash: fileItem.fileHash, filename: fileItem.file.name, paperless_id: String(docId) }),
                });
                if (aiResponse.ok) {
                  const aiData = await aiResponse.json();
                  // ⬇️ اینجا paperlessId رو هم ذخیره می‌کنیم تا در مرحله بعد داشته باشیمش ⬇️
                  updateFileById(fileItem.id, { status: "done", ocrText, extractedData: aiData, paperlessId: docId });
                  if (aiData.story_id) setNewStoryId(aiData.story_id);
                  return;
                } else if (aiResponse.status === 409) {
                  const errorData = await aiResponse.json();
                  updateFileById(fileItem.id, { status: "error", error: errorData.message || "این پرونده قبلاً آپلود شده است." });
                  return;
                } else {
                  const errorData = await aiResponse.json().catch(() => ({}));
                  updateFileById(fileItem.id, { status: "error", error: errorData.message || "خطا در تحلیل هوش مصنوعی." });
                  return;
                }
              } catch (aiError) {
                updateFileById(fileItem.id, { status: "error", error: "ارتباط با هوش مصنوعی برقرار نشد." });
                return;
              }
            }
          }
          updateFileById(fileItem.id, { status: "done", ocrText: "پردازش انجام شد ولی متنی استخراج نشد." });
          return;
        }
        if (taskStatus === "failure") {
          updateFileById(fileItem.id, { status: "error", error: "پردازش سند در Paperless شکست خورد." });
          return;
        }
      } catch (err) {
        console.error(err);
      }
    }
    updateFileById(fileItem.id, { status: "error", error: "زمان پردازش به پایان رسید." });
  };

  const handleAnalyze = async () => {
    if (!authToken || uploadingFiles) return;
    const filesToProcess = selectedFiles.filter((item) => item.status === "ready");
    if (filesToProcess.length === 0) return;

    setUploadingFiles(true);
    setActiveView("analysis");

    try {
      await Promise.all(
        filesToProcess.map(async (item) => {
          updateFileById(item.id, { status: "uploading", error: "" });
          let fileHash = "";
          try {
            fileHash = await computeFileHash(item.file);
            updateFileById(item.id, { fileHash });
          } catch {
            updateFileById(item.id, { status: "error", error: "خطا در پردازش فایل." });
            return;
          }
          const dup = await checkFileDuplicate(fileHash);
          if (dup.isDuplicate) {
            updateFileById(item.id, { status: "error", error: dup.message });
            return;
          }
          const formData = new FormData();
          formData.append("document", item.file);
          formData.append("title", item.file.name);
          try {
            const response = await fetch("http://127.0.0.1:8001/api/paperless/upload/", {
              method: "POST", headers: { Authorization: `Bearer ${authToken}` }, body: formData,
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
              updateFileById(item.id, { status: "error", error: data.message || "آپلود انجام نشد." });
              return;
            }
            updateFileById(item.id, { status: "processing", taskId: data.task_id });
            await pollTask({ ...item, taskId: data.task_id, fileHash });
          } catch {
            updateFileById(item.id, { status: "error", error: "ارتباط با سرور برقرار نشد." });
          }
        })
      );
    } finally {
      setUploadingFiles(false);
    }
  };

  useEffect(() => {
    const allFilesDone = selectedFiles.length > 0 && selectedFiles.every(f => f.status === "done");
    const anyFailure = selectedFiles.some(f => f.status === "error");
    
    if (allFilesDone) {
      setAllDone(true);
      const timer = setTimeout(() => {
        const results = selectedFiles
          .filter(f => f.status === "done" && f.extractedData)
          .map(f => ({
            filename: f.file.name,
            main_topic: f.extractedData.main_topic || "نامشخص",
            case_title: f.extractedData?.case_title || "نامشخص",
            case_number: f.extractedData?.case_number || "نامشخص",
            court: f.extractedData.court || "نامشخص",
            date: f.extractedData?.document_date || "نامشخص",
            paperless_id: f.paperlessId, // حالا این مقدار درست پر میشه
            story_id: f.extractedData.story_id,
            case_id: f.extractedData.case_id,
            document_type: f.extractedData.case_type || "سند", // ⬅️ ویرگول اینجا اضافه شد
            story_summary: f.extractedData.story_summary || "", // ⬅️ از اینجا به بعد اصلاح شد
            case_summary: f.extractedData.case_summary || ""
          }));
        onUploadSuccess(results);
      }, 2000);
      return () => clearTimeout(timer);
    }
    if (anyFailure) setHasFailure(true);
  }, [selectedFiles, newStoryId, onUploadSuccess]);

  // =========================
  // صفحه تحلیل (دایره چرخان)
  // =========================
  if (activeView === "analysis") {
    const isUploading = selectedFiles.some(f => f.status === "uploading");
    const isProcessing = selectedFiles.some(f => f.status === "processing");
    const progress = allDone ? 100 : isProcessing ? 66 : isUploading ? 30 : 0;
    
    const steps = [
      { label: "شناسایی نوع اسناد", state: isUploading ? "active" : isProcessing || allDone ? "complete" : "pending" },
      { label: "استخراج اطلاعات کلیدی", state: isProcessing ? "active" : allDone ? "complete" : "pending" },
      { label: "تطبیق با داستان حقوقی", state: allDone ? "complete" : "pending" },
    ];

    return (
      <div className="analysis-card" aria-live="polite">
        <h1 className="analysis-title">تحلیل اسناد</h1>
        <div className={`analysis-progress ${allDone ? "complete" : ""}`} style={{ "--analysis-progress": `${progress}%` }}>
          <svg className="analysis-sparkle" xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-2-5.8L4 11l6-2.2L12 3Z" /><path d="M19 2v5m-2.5-2.5h5" /><circle cx="5" cy="18" r="1.5" /></svg>
        </div>
        <h2 className="analysis-status">
          {hasFailure ? "تحلیل اسناد انجام نشد" : allDone ? "تحلیل اسناد شما کامل شد" : "در حال تحلیل اسناد شما"}
        </h2>
        <p className="analysis-description">هوش مصنوعی در حال بررسی کلمات کلیدی</p>
        <div className="analysis-steps" aria-label="مراحل تحلیل">
          {steps.map((step) => (
            <div className={`analysis-step ${step.state}`} key={step.label}>
              <span>{step.label}</span>
              <span className="analysis-step-indicator" aria-hidden="true">{step.state === "complete" ? "✓" : <span />}</span>
            </div>
          ))}
        </div>
        {hasFailure && <div className="analysis-error" role="alert">پردازش سند انجام نشد. برای تلاش دوباره صفحه را رفرش کنید.</div>}
        {allDone && (
          <div className="analysis-redirect-loader">
            <span>در حال رفتن به صفحه داستان...</span>
            <div className="loader-dots"><span></span><span></span><span></span></div>
          </div>
        )}
      </div>
    );
  }

  // =========================
  // صفحه آپلود
  // =========================
  return (
    <div className="auth-card upload-card">
      <h2 className="upload-page-title">بارگذاری سند جدید</h2>
      <div className="upload-dropzone" onClick={() => documentInputRef.current?.click()} role="button" tabIndex={0}>
        <svg className="upload-dropzone-icon" xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="16 16 12 12 8 16" /><line x1="12" y1="12" x2="12" y2="21" /><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" /></svg>
        <p className="upload-dropzone-text">اسناد خود را اینجا بکشید یا انتخاب کنید</p>
        <p className="upload-dropzone-hint">پسوندهای مجاز: PDF، تصویر، عکس از سند</p>
      </div>
      <input ref={documentInputRef} type="file" className="dashboard-file-input" accept=".jpg,.jpeg,.png,.webp,.pdf" multiple onChange={handleDocumentsSelect} />

      {selectedFiles.length > 0 && (
        <>
          <h3 className="upload-files-title">فایل‌های انتخاب‌شده</h3>
          <div className="upload-files-list">
            {selectedFiles.map((item) => (
              <div className="upload-file-item" key={item.id}>
                <div className="upload-file-row">
                  <span className="upload-file-check"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg></span>
                  <div className="upload-file-details">
                    <span className="upload-file-name" dir="auto">{item.file.name}</span>
                    <span className="upload-file-size">{toPersianDigits((item.file.size / (1024 * 1024)).toFixed(1))} مگابایت</span>
                  </div>
                </div>
                {item.error && <p className="upload-file-error-text">{item.error}</p>}
              </div>
            ))}
          </div>
        </>
      )}
      <button type="button" className="upload-analyze-button" onClick={handleAnalyze} disabled={selectedFiles.length === 0 || uploadingFiles}>
        {uploadingFiles ? "در حال پردازش..." : "شروع تحلیل هوشمند"}
      </button>
    </div>
  );
}

export default UploadScreen;
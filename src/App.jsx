import { useEffect, useRef, useState } from "react";
import "./app.css";

import HomeScreen from "./components/HomeScreen";
import CasesScreen from "./components/CasesScreen";
import NoticesScreen from "./components/NoticesScreen";
import AccountScreen from "./components/AccountScreen";

import userRoundKey from "./assets/user-round-key.svg";

import BottomNav from "./components/BottomNav";
import DocumentDetails from "./components/DocumentDetails";

// =========================
// توابع کمکی
// =========================
const readStored = (key, fallback) => {
  try {
    const raw = window.sessionStorage.getItem(key);
    if (raw === null) return fallback;
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
};

const toEnglishDigits = (value) =>
  value.replace(/[۰-۹]/g, (digit) =>
    String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit))
  ).replace(/[٠-٩]/g, (digit) =>
    String("٠١٢٣٤٥٦٧٨٩".indexOf(digit))
  );

const toPersianDigits = (value) =>
  value.replace(/\d/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);

const isValidIranianNationalId = (nationalId) => {
  if (!/^\d{10}$/.test(nationalId) || /^(\d)\1{9}$/.test(nationalId)) {
    return false;
  }
  const digits = nationalId.split("").map(Number);
  const checksum = digits
    .slice(0, 9)
    .reduce((sum, digit, index) => sum + digit * (10 - index), 0) % 11;
  const expectedCheckDigit = checksum < 2 ? checksum : 11 - checksum;
  return digits[9] === expectedCheckDigit;
};

const getCurrentPersianYear = () =>
  Number(
    toEnglishDigits(
      new Intl.DateTimeFormat("fa-IR-u-ca-persian", { year: "numeric" }).format(new Date())
    )
  );

const getCurrentPersianDate = () => {
  const parts = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).formatToParts(new Date());
  const get = (type) => parts.find((p) => p.type === type)?.value || "";
  return `${get("weekday")}، ${get("day")} ${get("month")} ${get("year")}`;
};

const getCurrentTimePersian = () => {
  const now = new Date();
  const hours = String(now.getHours()).padStart(2, "0");
  const minutes = String(now.getMinutes()).padStart(2, "0");
  return toPersianDigits(`${hours}:${minutes}`);
};

// =========================
// کامپوننت‌های کوچک
// =========================
function LockIcon({ className = "" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="4" y="10" width="16" height="11" rx="2.5" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function SecurityFooter() {
  return (
    <footer className="security-footer">
      <LockIcon />
      <span>اتصال امن و حفاظت‌شده</span>
    </footer>
  );
}

function JudiciaryMark() {
  return (
    <span className="judiciary-mark" aria-hidden="true">
      <svg viewBox="0 0 40 40" fill="none">
        <circle cx="20" cy="7" r="2" />
        <path d="M20 9v23m-12-18h24M11 14 5 26m6-12 6 12M29 14l-6 12m6-12 6 12" />
        <path d="M2 26h15c-.8 4.2-3.2 6.2-7.5 6.2S2.8 30.2 2 26Zm21 0h15c-.8 4.2-3.2 6.2-7.5 6.2S23.8 30.2 23 26ZM14 35h12m-6-3v3" />
      </svg>
    </span>
  );
}

// کامپوننت AppFrame با فوتر سراسری
function AppFrame({ progress, canGoBack, onBack, children, showFooter, dashboardTab, setDashboardTab }) {
  return (
    <div className="app-frame" style={{ paddingBottom: showFooter ? "70px" : "0" }}>
      <header className="app-header">
        <div className="brand">
          <JudiciaryMark />
          <span>همراه حقوقی</span>
        </div>
        {canGoBack ? (
          <button className="back-button" type="button" onClick={onBack} aria-label="بازگشت">
            <span aria-hidden="true">›</span>
          </button>
        ) : <span className="header-spacer" />}
      </header>
      <div className="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(progress * 100)}>
        <span className="progress-fill" style={{ width: `${progress * 100}%` }} />
      </div>
      {children}
      {showFooter && <BottomNav active={dashboardTab} onChange={setDashboardTab} />}
    </div>
  );
}

// =========================
// کامپوننت اصلی
// =========================
function App() {
  const [authScreen, setAuthScreen] = useState(() => readStored("authScreen", "welcome"));
  const [screenHistory, setScreenHistory] = useState(() => readStored("screenHistory", []));
  const [dashboardTab, setDashboardTab] = useState(() => readStored("dashboardTab", "home"));

  const [authMode, setAuthMode] = useState("signup");
  const [birthYear, setBirthYear] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");

  // آپلود اسناد
  const documentInputRef = useRef(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadingFiles, setUploadingFiles] = useState(false);

  // یادداشت‌ها
  const [notes, setNotes] = useState([]);
  const [isNoteModalOpen, setIsNoteModalOpen] = useState(false);
  const [noteTitle, setNoteTitle] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [editingNoteId, setEditingNoteId] = useState(null);
  const [selectedNote, setSelectedNote] = useState(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);

  // احراز هویت
  const [resendSeconds, setResendSeconds] = useState(0);
  const verificationInputs = useRef([]);
  const [verificationCode, setVerificationCode] = useState("");
  const [error, setError] = useState("");
  const [phoneErrorKind, setPhoneErrorKind] = useState("");
  const [nationalIdError, setNationalIdError] = useState(false);
  const [firstName, setFirstName] = useState(() => readStored("firstName", ""));
  const [lastName, setLastName] = useState(() => readStored("lastName", ""));
  const [mobile, setMobile] = useState(() => readStored("mobile", ""));
  const [authToken, setAuthToken] = useState(() => readStored("authToken", ""));

  const [patient, setPatient] = useState(() =>
    readStored("patient", { name: "", nationalId: "", age: "", yearOfBirth: "", gender: "" })
  );

  // ذخیره‌سازی در sessionStorage
  useEffect(() => { window.sessionStorage.setItem("authScreen", JSON.stringify(authScreen)); }, [authScreen]);
  useEffect(() => { window.sessionStorage.setItem("screenHistory", JSON.stringify(screenHistory)); }, [screenHistory]);
  useEffect(() => { window.sessionStorage.setItem("dashboardTab", JSON.stringify(dashboardTab)); }, [dashboardTab]);
  useEffect(() => { window.sessionStorage.setItem("firstName", JSON.stringify(firstName)); }, [firstName]);
  useEffect(() => { window.sessionStorage.setItem("lastName", JSON.stringify(lastName)); }, [lastName]);
  useEffect(() => { window.sessionStorage.setItem("mobile", JSON.stringify(mobile)); }, [mobile]);
  useEffect(() => { window.sessionStorage.setItem("authToken", JSON.stringify(authToken)); }, [authToken]);
  useEffect(() => { window.sessionStorage.setItem("patient", JSON.stringify(patient)); }, [patient]);

  const navigateTo = (screen, replace = false) => {
    if (replace) setScreenHistory((history) => history.slice(0, -1));
    else setScreenHistory((history) => [...history, authScreen]);
    setAuthScreen(screen);
  };

  const goBack = () => {
    const previousScreen = screenHistory[screenHistory.length - 1];
    if (!previousScreen) return;
    setScreenHistory((history) => history.slice(0, -1));
    setAuthScreen(previousScreen);
    setError("");
  };

  const getProgress = () => {
    if (authScreen === "dashboard" || authScreen === "complete") return 1;
    if (authScreen === "identity") return 0.78;
    if (authScreen === "verify") return 0.57;
    if (authScreen === "phone" || authScreen === "password") return 0.32;
    return 0.08;
  };

  useEffect(() => {
    if (resendSeconds <= 0) return undefined;
    const timer = window.setTimeout(() => {
      setResendSeconds((seconds) => Math.max(0, seconds - 1));
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [authScreen, resendSeconds]);

  const formatResendTime = () =>
    `${Math.floor(resendSeconds / 60).toString().padStart(2, "0")}:${(resendSeconds % 60).toString().padStart(2, "0")}`;

  const maskedMobile = mobile.length === 11
    ? toPersianDigits(`${mobile.slice(0, 4)}***${mobile.slice(-4)}`)
    : mobile;
  const codeExpired = authScreen === "verify" && resendSeconds === 0;

  // =========================
  // یادداشت‌ها (متصل به بک‌اند)
  // =========================
  const fetchNotes = async () => {
    if (!authToken) return;
    try {
      const response = await fetch("http://127.0.0.1:8001/api/notes/", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        const data = await response.json();
        setNotes(Array.isArray(data) ? data : data.results || []);
      }
    } catch (error) {
      console.error("خطا در دریافت یادداشت‌ها:", error);
    }
  };

  useEffect(() => {
    if (authScreen === "dashboard" && authToken) fetchNotes();
  }, [authScreen, authToken]);

  const handleSaveNote = async () => {
    const trimmedTitle = noteTitle.trim();
    const trimmedBody = noteBody.trim();
    if (!trimmedTitle && !trimmedBody) return;

    try {
      const url = editingNoteId
        ? `http://127.0.0.1:8001/api/notes/${editingNoteId}/`
        : "http://127.0.0.1:8001/api/notes/";
      const method = editingNoteId ? "PUT" : "POST";

      const response = await fetch(url, {
        method: method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ title: trimmedTitle || "بدون موضوع", body: trimmedBody }),
      });

      if (response.ok) {
        await fetchNotes();
        setNoteTitle("");
        setNoteBody("");
        setEditingNoteId(null);
        setIsNoteModalOpen(false);
        setIsDetailModalOpen(false);
      }
    } catch (error) {
      console.error("خطا در ذخیره یادداشت:", error);
    }
  };

  const handleCancelNote = () => {
    setNoteTitle("");
    setNoteBody("");
    setEditingNoteId(null);
    setIsNoteModalOpen(false);
    setIsDetailModalOpen(false);
    setIsDeleteConfirmOpen(false);
  };

  const handleNoteClick = (note) => {
    setSelectedNote(note);
    setNoteTitle(note.title);
    setNoteBody(note.body || "");
    setEditingNoteId(note.id);
    setIsNoteModalOpen(true);
  };

  const handleDeleteNote = () => {
    if (!selectedNote) return;
    setIsDetailModalOpen(false);
    setIsDeleteConfirmOpen(true);
  };

  const cancelDeleteNote = () => {
    setIsDeleteConfirmOpen(false);
    setIsNoteModalOpen(true);
  };

  const confirmDeleteNote = async () => {
    if (!selectedNote) return;
    try {
      const response = await fetch(`http://127.0.0.1:8001/api/notes/${selectedNote.id}/`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        await fetchNotes();
        setIsDeleteConfirmOpen(false);
        setSelectedNote(null);
        setEditingNoteId(null);
        setNoteTitle("");
        setNoteBody("");
      }
    } catch (error) {
      console.error("خطا در حذف یادداشت:", error);
    }
  };

  // =========================
  // احراز هویت (موبایل و کد)
  // =========================
  const handleMobileChange = (e) => {
    const value = toEnglishDigits(e.target.value);
    if (!/^\d*$/.test(value) || value.length > 11) return;
    setMobile(value);
    setError("");
    setPhoneErrorKind("");
  };

  const handleMobileSubmit = async (e) => {
    e.preventDefault();
    if (!/^09\d{9}$/.test(mobile)) {
      setPhoneErrorKind("invalid");
      setError("شماره موبایل معتبر نیست؛ با ۰۹ شروع کنید.");
      return;
    }
    try {
      const response = await fetch("http://127.0.0.1:8001/api/send-code/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mobile, mode: authMode }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 429) {
          setResendSeconds(data.retryAfter || 180);
          setPhoneErrorKind("send");
          setError("پیامک ارسال نشد، چند لحظه دیگر دوباره تلاش کنید.");
          return;
        }
        if (response.status === 400) {
          setPhoneErrorKind("invalid");
          setError("شماره موبایل معتبر نیست؛ با ۰۹ شروع کنید.");
          return;
        }
        setPhoneErrorKind("send");
        setError(response.status >= 500 ? "پیامک ارسال نشد." : data.message || "خطا در ارسال پیامک.");
        return;
      }
      setError("");
      setPhoneErrorKind("");
      setVerificationCode("");
      setResendSeconds(180);
      navigateTo("verify");
    } catch (error) {
      setPhoneErrorKind("send");
      setError("پیامک ارسال نشد، چند لحظه دیگر دوباره تلاش کنید.");
    }
  };

  const handleResendCode = async () => {
    try {
      const response = await fetch("http://127.0.0.1:8001/api/send-code/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mobile, mode: authMode }),
      });
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 429) {
          setResendSeconds(data.retryAfter || 180);
          setError("ارسال دوباره ممکن نیست؛ لطفاً کمی صبر کنید.");
          return;
        }
        setError(data.message || "ارسال دوباره کد انجام نشد.");
        return;
      }
      setVerificationCode("");
      setResendSeconds(180);
      setError("");
      verificationInputs.current[0]?.focus();
    } catch (requestError) {
      setError("ارتباط با سرور برقرار نشد.");
    }
  };

  const handleVerificationCodeChange = (index, event) => {
    const value = toEnglishDigits(event.target.value).replace(/\D/g, "");
    if (!value) {
      setVerificationCode((code) => `${code.slice(0, index)}${code.slice(index + 1)}`);
      setError("");
      return;
    }
    const pastedCode = value.slice(0, 6);
    if (pastedCode.length > 1) {
      setVerificationCode(pastedCode);
      verificationInputs.current[Math.min(pastedCode.length, 5)]?.focus();
    } else {
      setVerificationCode((code) => {
        const digits = code.padEnd(6, " ").split("");
        digits[index] = value[0];
        return digits.join("").trimEnd();
      });
      if (index < 5) verificationInputs.current[index + 1]?.focus();
    }
    setError("");
  };

  const handleVerificationKeyDown = (index, event) => {
    if (event.key === "Backspace" && !verificationCode[index] && index > 0) {
      verificationInputs.current[index - 1]?.focus();
    }
    if (event.key === "ArrowLeft" && index < 5) {
      verificationInputs.current[index + 1]?.focus();
    }
    if (event.key === "ArrowRight" && index > 0) {
      verificationInputs.current[index - 1]?.focus();
    }
  };

  const handleVerificationSubmit = async () => {
    if (!/^\d{6}$/.test(verificationCode)) {
      setError("کد تأیید باید 6 رقمی باشد.");
      return;
    }
    try {
      const response = await fetch("http://127.0.0.1:8001/api/verify-code/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mobile, code: verificationCode, mode: authMode }),
      });
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 410) {
          setResendSeconds(0);
          setVerificationCode("");
          setError("کد منقضی شده؛ یک کد تازه دریافت کنید.");
          return;
        }
        setError(data.message || "کد تأیید اشتباه است.");
        return;
      }

      if (authMode === "signup") {
        setAuthToken(data.token);
        navigateTo("identity");
        setError("");
        return;
      }
      setAuthToken(data.token);
      const patientResponse = await fetch(`http://127.0.0.1:8001/api/patients/${mobile}`, {
        headers: { Authorization: `Bearer ${data.token}` },
      });
      if (patientResponse.ok) {
        const patientData = await patientResponse.json();
        setPatient({
          name: patientData.name || "",
          nationalId: patientData.nationalId || "",
          age: patientData.age || "",
          yearOfBirth: patientData.age ? String(getCurrentPersianYear() - Number(patientData.age)) : "",
          gender: patientData.gender || "",
        });
        const [savedLastName = "", ...savedFirstNames] = (patientData.name || "").split(/\s+/);
        setLastName(savedLastName);
        setFirstName(savedFirstNames.join(" "));
        setBirthYear(patientData.age ? String(getCurrentPersianYear() - Number(patientData.age)) : "");
      } else if (patientResponse.status === 404) {
        setBirthYear("");
      } else {
        const patientError = await patientResponse.json();
        setError(patientError.message || "دریافت اطلاعات حساب انجام نشد.");
        return;
      }
      setError("");
      navigateTo("dashboard", true);
    } catch (error) {
      setError("ارتباط با سرور برقرار نشد. مطمئن شوید Backend روشن است.");
    }
  };

  const handlePasswordLogin = async (e) => {
    e.preventDefault();
    if (!/^09\d{9}$/.test(mobile)) {
      setError("لطفاً شماره موبایل معتبر ۱۱ رقمی وارد کنید.");
      return;
    }
    if (!password) {
      setError("رمز عبور را وارد کنید.");
      return;
    }
    try {
      const response = await fetch("http://127.0.0.1:8001/api/login/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mobile, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.message || "ورود انجام نشد.");
        return;
      }
      setPatient({
        name: data.name || "",
        nationalId: data.nationalId || "",
        age: data.age || "",
        yearOfBirth: data.age ? String(getCurrentPersianYear() - Number(data.age)) : "",
        gender: data.gender || "",
      });
      const [savedLastName = "", ...savedFirstNames] = (data.name || "").split(/\s+/);
      setLastName(savedLastName);
      setFirstName(savedFirstNames.join(" "));
      setAuthToken(data.token);
      setBirthYear(data.age ? String(getCurrentPersianYear() - Number(data.age)) : "");
      setAuthMode("login");
      navigateTo("dashboard");
      setError("");
    } catch (requestError) {
      setError("ارتباط با سرور برقرار نشد. مطمئن شوید Backend روشن است.");
    }
  };

  const handleIdentityContinue = async (e) => {
    e.preventDefault();
    const currentYear = getCurrentPersianYear();
    const year = Number(birthYear);
    const fullName = `${lastName.trim()} ${firstName.trim()}`.trim();

    if (!isValidIranianNationalId(patient.nationalId)) {
      setNationalIdError(true);
      setError("");
      return;
    }
    setNationalIdError(false);

    if (!lastName.trim() || !firstName.trim() || !patient.gender) {
      setError("نام، نام خانوادگی، کد ملی و جنسیت را تکمیل کنید.");
      return;
    }
    if (!/^\d{4}$/.test(birthYear) || year < 1300 || year > currentYear) {
      setError("سال تولد را به‌صورت معتبر وارد کنید.");
      return;
    }
    if (authMode === "signup") {
      if (password.length < 8) {
        setError("رمز عبور باید حداقل ۸ نویسه باشد.");
        return;
      }
      if (password !== passwordConfirmation) {
        setError("رمز عبور و تکرار آن یکسان نیستند.");
        return;
      }
    }

    const nextPatient = {
      ...patient,
      name: fullName,
      age: String(currentYear - year),
      yearOfBirth: birthYear,
    };
    const formData = new FormData();
    formData.append("mobile", mobile);
    formData.append("name", nextPatient.name);
    formData.append("nationalId", nextPatient.nationalId);
    formData.append("age", nextPatient.age);
    formData.append("gender", nextPatient.gender);
    if (authMode === "signup") formData.append("password", password);

    try {
      const response = await fetch("http://127.0.0.1:8001/api/patients/", {
        method: "POST",
        headers: { Authorization: `Bearer ${authToken}` },
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.message || "ذخیره اطلاعات هویتی انجام نشد.");
        return;
      }
      setPatient(nextPatient);
      setPassword("");
      setPasswordConfirmation("");
      setAuthMode("login");
      setError("");
      navigateTo("complete");
    } catch (requestError) {
      setError("ارتباط با سرور برقرار نشد. تکمیل ثبت‌نام ممکن نیست.");
    }
  };

  // =========================
  // آپلود و تحلیل اسناد (Paperless + Ollama)
  // =========================
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
        file,
        status: "ready",
        taskId: null,
        ocrText: "",
        extractedData: null,
        error: "",
      });
    });
    setSelectedFiles((prev) => [...prev, ...validFiles]);
    if (documentInputRef.current) documentInputRef.current.value = "";
  };

  const updateFileById = (id, patch) => {
    setSelectedFiles((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  };

  const pollTask = async (fileItem) => {
    const maxAttempts = 60;
    const interval = 3000;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, interval));

      try {
        const response = await fetch(
          `http://127.0.0.1:8001/api/paperless/task/${fileItem.taskId}/`,
          { headers: { Authorization: `Bearer ${authToken}` } }
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          updateFileById(fileItem.id, {
            status: "error",
            error: data.message || "ارتباط با سرویس تحلیل برقرار نشد.",
          });
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
              
              // --- شروع ارسال به هوش مصنوعی ---
              try {
                const aiResponse = await fetch("http://127.0.0.1:8001/api/ai/analyze/", {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${authToken}`,
                  },
                  body: JSON.stringify({ text: ocrText }),
                });
                
                if (aiResponse.ok) {
                 const aiData = await aiResponse.json();
                 console.log("AI Response:", aiData); // ← این خط را اضافه کنید
                 updateFileById(fileItem.id, {
                 status: "done",
                 ocrText: ocrText,
                 extractedData: aiData,
                 });
                 return;
                }
              } catch (aiError) {
                console.error("AI analysis failed:", aiError);
              }
              
              updateFileById(fileItem.id, {
                status: "done",
                ocrText: ocrText,
              });
              return;
              // --- پایان ارسال به هوش مصنوعی ---
            }
          }
          updateFileById(fileItem.id, {
            status: "done",
            ocrText: "پردازش انجام شد ولی متنی استخراج نشد.",
          });
          return;
        }

        if (taskStatus === "failure") {
          updateFileById(fileItem.id, {
            status: "error",
            error: "پردازش سند در Paperless شکست خورد.",
          });
          return;
        }
      } catch (err) {
        console.error(err);
      }
    }

    updateFileById(fileItem.id, {
      status: "error",
      error: "زمان پردازش به پایان رسید.",
    });
  };

  const handleAnalyze = async () => {
    if (!authToken) return;
    if (selectedFiles.length === 0) return;
    if (uploadingFiles) return;

    setUploadingFiles(true);
    navigateTo("analysis");

    try {
      await Promise.all(
        selectedFiles.map(async (item) => {
          if (item.status !== "ready") return;

          updateFileById(item.id, { status: "uploading", error: "" });

          const formData = new FormData();
          formData.append("document", item.file);
          formData.append("title", item.file.name);

          try {
            const response = await fetch("http://127.0.0.1:8001/api/paperless/upload/", {
              method: "POST",
              headers: { Authorization: `Bearer ${authToken}` },
              body: formData,
            });
            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
              updateFileById(item.id, {
                status: "error",
                error: data.message || data.error || "آپلود انجام نشد.",
              });
              return;
            }

            updateFileById(item.id, { status: "processing", taskId: data.task_id });
            await pollTask({ ...item, taskId: data.task_id });

          } catch (err) {
            console.error(err);
            updateFileById(item.id, {
              status: "error",
              error: "ارتباط با سرور برقرار نشد.",
            });
          }
        })
      );
    } finally {
      setUploadingFiles(false);
    }
  };

  // =========================
  // رندر صفحات
  // =========================
  if (
    authScreen !== "complete" &&
    authScreen !== "dashboard" &&
    authScreen !== "upload" &&
    authScreen !== "analysis" &&
    authScreen !== "document-details"
  ) {
    return (
      <AppFrame progress={getProgress()} canGoBack={screenHistory.length > 0} onBack={goBack}>
        <main className="auth-shell">
          <section className="auth-card welcome-card">
            {authScreen === "welcome" && (
              <>
                <div className="auth-logo"><img src={userRoundKey} alt="ورود امن" /></div>
                <h1 className="auth-title">ورود امن به همراه حقوقی شما</h1>
                <p className="auth-description">برای پیگیری پرونده‌ها و خدمات قضایی وارد حساب خود شوید یا حساب تازه‌ای بسازید.</p>
                <div className="privacy-notice">
                  <LockIcon className="privacy-lock" />
                  <p>ورود شما امن است و اطلاعات بدون اجازه شما به اشتراک گذاشته نمی‌شود.</p>
                </div>
                <div className="auth-actions">
                  <button type="button" className="auth-button auth-button-primary" onClick={() => { setAuthMode("login"); navigateTo("phone"); setError(""); setPhoneErrorKind(""); }}>ورود</button>
                  <button type="button" className="auth-button auth-button-primary" onClick={() => { setAuthMode("signup"); navigateTo("phone"); setError(""); setPhoneErrorKind(""); }}>ثبت‌ نام</button>
                </div>
              </>
            )}

            {authScreen === "phone" && (
              <>
                <h1 className="auth-title auth-page-title">{authMode === "signup" ? "ثبت‌نام" : "ورود با پیامک"}</h1>
                <p className="auth-description">{authMode === "signup" ? "شماره موبایلی که به نام خودتان است وارد کنید." : "شماره موبایل ثبت‌شده در حساب را وارد کنید."}</p>
                <form className="auth-form" onSubmit={handleMobileSubmit}>
                  <div className={`phone-input-panel ${phoneErrorKind === "invalid" ? "has-error" : ""}`}>
                    <label htmlFor="mobile-number">شماره موبایل</label>
                    <input id="mobile-number" className={phoneErrorKind === "invalid" || phoneErrorKind === "send" ? "input-error" : ""} type="tel" value={mobile} onChange={handleMobileChange} placeholder="مثال :147***0912" maxLength="11" inputMode="numeric" autoComplete="tel" aria-invalid={phoneErrorKind !== ""} dir="ltr" />
                  </div>
                  {error && <div className="phone-error-message" role="alert">{phoneErrorKind === "invalid" ? "شماره موبایل معتبر نیست؛ با ۰۹ شروع کنید." : error}</div>}
                  <button className="auth-button auth-button-primary" type="submit">{phoneErrorKind === "send" ? "تلاش دوباره برای ارسال" : "دریافت کد تأیید"}</button>
                </form>
                {authMode === "login" ? (
                  <button className="auth-text-button" type="button" onClick={() => { navigateTo("password"); setError(""); }}>ورود با رمز عبور</button>
                ) : (
                  <p className="auth-switch">حساب دارید؟ <button type="button" onClick={() => { setAuthMode("login"); setError(""); setPhoneErrorKind(""); }}>ورود</button></p>
                )}
              </>
            )}

            {authScreen === "password" && (
              <>
                <h1 className="auth-title auth-page-title">ورود با رمز عبور</h1>
                <p className="auth-description">شماره موبایل و رمز عبور حساب خود را وارد کنید.</p>
                <form className="auth-form" onSubmit={handlePasswordLogin}>
                  <div className="phone-input-panel">
                    <label htmlFor="password-mobile">شماره موبایل</label>
                    <input id="password-mobile" type="tel" value={mobile} onChange={handleMobileChange} placeholder="مثال :147***0912" maxLength="11" inputMode="numeric" autoComplete="tel" dir="ltr" />
                  </div>
                  <label htmlFor="account-password">رمز عبور</label>
                  <input id="account-password" type="password" value={password} onChange={(event) => { setPassword(event.target.value); setError(""); }} autoComplete="current-password" />
                  {error && <div className="error-message" role="alert">{error}</div>}
                  <button className="auth-button auth-button-primary" type="submit">ورود</button>
                </form>
                <button className="auth-text-button" type="button" onClick={() => { navigateTo("phone", true); setError(""); }}>ورود با پیامک</button>
              </>
            )}

            {authScreen === "verify" && (
              <>
                <h1 className="auth-title auth-page-title">{authMode === "signup" ? "تأیید شماره موبایل" : "تأیید ورود"}</h1>
                {codeExpired && <p className="expired-heading" role="alert">مهلت استفاده از کد به پایان رسیده است.</p>}
                <p className="auth-description">کد شش‌رقمی ارسال‌شده به شماره <bdi className="verified-mobile" dir="ltr">{maskedMobile}</bdi> را وارد کنید.</p>
                <form className="auth-form verification-form" onSubmit={(event) => { event.preventDefault(); handleVerificationSubmit(); }}>
                  <div className="verification-panel">
                    <div className="verification-inputs" dir="ltr">
                      {Array.from({ length: 6 }, (_, index) => (
                        <input key={index} ref={(element) => { verificationInputs.current[index] = element; }} id={index === 0 ? "verification-code-1" : undefined} aria-label={`رقم ${index + 1} کد تأیید`} type="text" value={verificationCode[index] === " " ? "" : verificationCode[index] || ""} onChange={(event) => handleVerificationCodeChange(index, event)} onKeyDown={(event) => handleVerificationKeyDown(index, event)} onPaste={(event) => { event.preventDefault(); handleVerificationCodeChange(index, { target: { value: event.clipboardData.getData("text") } }); }} maxLength="6" inputMode="numeric" autoComplete={index === 0 ? "one-time-code" : "off"} />
                      ))}
                    </div>
                    <p className={`verification-countdown ${codeExpired ? "expired" : ""}`}>{codeExpired ? "زمان کد: 00:00" : (<>ارسال دوباره تا <bdi dir="ltr">{formatResendTime()}</bdi></>)}</p>
                    {!codeExpired && <button className="resend-button" type="button" onClick={handleResendCode} disabled={resendSeconds > 0}>ارسال دوباره کد</button>}
                  </div>
                  {error && !codeExpired && <div className="error-message" role="alert">{error}</div>}
                  {codeExpired && (<><p className="expired-message" role="alert">کد منقضی شده؛ یک کد تازه دریافت کنید.</p><button className="resend-button resend-button-expired" type="button" onClick={handleResendCode}>ارسال دوباره کد</button></>)}
                  <button className="auth-button auth-button-primary" type="submit" disabled={!/^\d{6}$/.test(verificationCode) || codeExpired}>{authMode === "signup" ? "تأیید و ادامه" : "ورود"}</button>
                </form>
                <button className="auth-text-button" type="button" onClick={() => { navigateTo("phone", true); setVerificationCode(""); setError(""); }}>تغییر شماره موبایل</button>
              </>
            )}

            {authScreen === "identity" && (
              <>
                <h1 className="auth-title auth-page-title">تکمیل اطلاعات</h1>
                <p className="auth-description">اطلاعات هویتی را مطابق مدارک رسمی وارد کنید.</p>
                <form className="auth-form" onSubmit={handleIdentityContinue}>
                  <div className="identity-name-grid">
                    <div className="identity-field">
                      <label htmlFor="identity-last-name"><span className="required-star">*</span> نام خانوادگی </label>
                      <input id="identity-last-name" type="text" value={lastName} onChange={(event) => setLastName(event.target.value)} autoComplete="family-name" required />
                    </div>
                    <div className="identity-field">
                      <label htmlFor="identity-first-name"> <span className="required-star">*</span>نام </label>
                      <input id="identity-first-name" type="text" value={firstName} onChange={(event) => setFirstName(event.target.value)} autoComplete="given-name" required />
                    </div>
                  </div>
                  <label htmlFor="identity-national-id"><span className="required-star">*</span>کد ملی </label>
                  <input id="identity-national-id" type="text" className={nationalIdError ? "national-id-error" : ""} value={patient.nationalId} onChange={(event) => { const nationalId = toEnglishDigits(event.target.value).replace(/\D/g, "").slice(0, 10); setPatient({ ...patient, nationalId }); if (isValidIranianNationalId(nationalId)) { setNationalIdError(false); } }} maxLength="10" inputMode="numeric" dir="ltr" required aria-invalid={nationalIdError} />
                  {nationalIdError && <div className="national-id-error-message" role="alert">کد ملی ایرانی واردشده معتبر نیست.</div>}
                  <label><span className="required-star">*</span>جنسیت </label>
                  <div className="gender-options">
                    <label className={`gender-option ${patient.gender === "male" ? "selected" : ""}`}><input type="radio" name="identity-gender" value="male" checked={patient.gender === "male"} onChange={(event) => setPatient({ ...patient, gender: event.target.value })} />مرد</label>
                    <label className={`gender-option ${patient.gender === "female" ? "selected" : ""}`}><input type="radio" name="identity-gender" value="female" checked={patient.gender === "female"} onChange={(event) => setPatient({ ...patient, gender: event.target.value })} />زن</label>
                  </div>
                  <label htmlFor="identity-birth-year"><span className="required-star">*</span>سال تولد </label>
                  <input id="identity-birth-year" type="text" value={birthYear} onChange={(event) => setBirthYear(toEnglishDigits(event.target.value).replace(/\D/g, "").slice(0, 4))} maxLength="4" inputMode="numeric" placeholder="انتخاب سال شمسی" dir="ltr" required />
                  {authMode === "signup" && (
                    <>
                      <label htmlFor="new-password">ایجاد رمز عبور</label>
                      <input id="new-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" minLength="8" />
                      <small>رمز عبور باید حداقل ۸ نویسه باشد.</small>
                      <label htmlFor="confirm-password">تکرار رمز عبور</label>
                      <input id="confirm-password" type="password" value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} autoComplete="new-password" />
                    </>
                  )}
                  {error && <div className="error-message" role="alert">{error}</div>}
                  <button className="auth-button auth-button-primary" type="submit">تکمیل ثبت‌ نام</button>
                </form>
              </>
            )}
            <SecurityFooter />
          </section>
        </main>
      </AppFrame>
    );
  }

  if (authScreen === "complete") {
    return (
      <AppFrame progress={getProgress()} canGoBack={screenHistory.length > 0} onBack={goBack}>
        <main className="auth-shell">
          <section className="auth-card completion-card" aria-live="polite">
            <div className="completion-icon" aria-hidden="true">✓</div>
            <h1 className="auth-title auth-page-title">اطلاعات با موفقیت ثبت شد</h1>
            <p className="auth-description">اطلاعات هویتی شما با موفقیت ذخیره شد.</p>
            <button className="auth-button auth-button-primary" type="button" onClick={() => navigateTo("dashboard", true)}>ورود به حساب</button>
            <SecurityFooter />
          </section>
        </main>
      </AppFrame>
    );
  }

  // =========================
  // صفحه داشبورد (با تب‌های مختلف)
  // =========================
  if (authScreen === "dashboard") {
    return (
      <AppFrame progress={getProgress()} canGoBack={false} onBack={() => {}} showFooter={true} dashboardTab={dashboardTab} setDashboardTab={setDashboardTab}>
        <main className="auth-shell">
          <section className="auth-card dashboard-card" aria-live="polite">
            
            {dashboardTab === "home" && (
              <HomeScreen 
                firstName={firstName} 
                getCurrentPersianDate={getCurrentPersianDate} 
                onNavigate={navigateTo} 
                onAddNote={() => { setEditingNoteId(null); setNoteTitle(""); setNoteBody(""); setIsNoteModalOpen(true); }}
                notes={notes}
                onNoteClick={handleNoteClick}
              />
            )}
            
            {dashboardTab === "cases" && <CasesScreen />}
            {dashboardTab === "notices" && <NoticesScreen />}
            {dashboardTab === "account" && (
              <AccountScreen firstName={firstName} lastName={lastName} mobile={mobile} />
            )}
          </section>
        </main>

        {/* مودال‌های یادداشت */}
       {isNoteModalOpen && (
  <div className="note-modal-backdrop" onClick={handleCancelNote} role="presentation">
    <div className="note-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="note-modal-title">
      <div className="note-modal-header">
        <h2 id="note-modal-title" className="note-modal-title">
          {editingNoteId ? "ویرایش یادداشت" : "افزودن یادداشت"}
        </h2>
        <button type="button" className="note-modal-close" onClick={handleCancelNote} aria-label="بستن">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
        </button>
      </div>

      <label className="note-modal-label" htmlFor="note-title">موضوع یادداشت</label>
      <input id="note-title" type="text" className="note-modal-input" value={noteTitle} onChange={(e) => setNoteTitle(e.target.value)} placeholder="موضوع یادداشت..." />

      <label className="note-modal-label" htmlFor="note-body">متن یادداشت</label>
      <textarea id="note-body" className="note-modal-textarea" value={noteBody} onChange={(e) => setNoteBody(e.target.value)} placeholder="یادداشت خود را اینجا بنویسید..." rows={5} />

      {/* دکمه‌ها */}
      <div className="note-modal-actions">
        <button type="button" className="note-modal-save" onClick={handleSaveNote}>
          {editingNoteId ? "ذخیره تغییرات" : "ذخیره یادداشت"}
        </button>
        <button type="button" className="note-modal-cancel" onClick={handleCancelNote}>انصراف</button>
      </div>

      {/* سطل قرمز فقط در حالت ویرایش */}
      {editingNoteId && (
        <button type="button" className="note-delete-trigger" onClick={() => {
          setIsNoteModalOpen(false);
          setIsDeleteConfirmOpen(true);
        }}>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
            <path d="M10 11v6M14 11v6" />
            <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
          </svg>
          حذف یادداشت
        </button>
      )}
    </div>
  </div>
)}
        
        {isDeleteConfirmOpen && selectedNote && (
          <div className="note-modal-backdrop note-delete-backdrop" onClick={cancelDeleteNote} role="presentation">
            <section className="note-modal note-delete-modal" onClick={(event) => event.stopPropagation()} role="alertdialog" aria-modal="true">
              <div className="note-delete-header">
                <div>
                  <h2 className="note-modal-title">آیا این یادداشت حذف شود؟</h2>
                  <p className="note-delete-description">پس از حذف، امکان بازگرداندن آن وجود ندارد.</p>
                </div>
                <span className="note-delete-warning" aria-hidden="true">!</span>
              </div>
              <div className="note-delete-preview">
                <strong>{selectedNote.title}</strong>
                {selectedNote.body && <p>{selectedNote.body}</p>}
              </div>
              <div className="note-modal-actions note-delete-actions">
                <button type="button" className="note-modal-cancel" onClick={cancelDeleteNote}>انصراف</button>
                <button type="button" className="note-delete-confirm" onClick={confirmDeleteNote}>حذف یادداشت</button>
              </div>
            </section>
          </div>
        )}
      </AppFrame>
    );
  }

  // =========================
  // صفحه بارگذاری سند جدید
  // =========================
  if (authScreen === "upload") {
    return (
      <AppFrame progress={getProgress()} canGoBack={true} onBack={() => navigateTo("dashboard", true)} showFooter={true} dashboardTab={dashboardTab} setDashboardTab={setDashboardTab}>
        <main className="auth-shell upload-shell">
          <section className="auth-card upload-card">
            <h2 className="upload-page-title">بارگذاری سند جدید</h2>
            <div className="upload-dropzone" onClick={() => documentInputRef.current?.click()} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { documentInputRef.current?.click(); } }}>
              <svg className="upload-dropzone-icon" xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="16 16 12 12 8 16" /><line x1="12" y1="12" x2="12" y2="21" /><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" /></svg>
              <p className="upload-dropzone-text">اسناد خود را اینجا بکشید یا انتخاب کنید</p>
              <p className="upload-dropzone-hint">پسوندهای مجاز: PDF، تصویر، عکس از سند</p>
            </div>
            <input ref={documentInputRef} type="file" className="dashboard-file-input" accept=".jpg,.jpeg,.png,.webp,.pdf,image/jpeg,image/png,image/webp,application/pdf" multiple onChange={handleDocumentsSelect} />
            {selectedFiles.length > 0 && (
              <>
                <h3 className="upload-files-title">فایل‌های انتخاب‌شده</h3>
                <div className="upload-files-list">
                  {selectedFiles.map((item) => (
                    <div className="upload-file-item" key={item.id}>
                      <div className="upload-file-row">
                        <span className="upload-file-check" aria-label="فایل آماده است"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12" /></svg></span>
                        <div className="upload-file-details">
                          <span className="upload-file-name" dir="auto">{item.file.name}</span>
                          <span className="upload-file-size">{toPersianDigits((item.file.size / (1024 * 1024)).toFixed(1))} مگابایت</span>
                        </div>
                        <div className="upload-file-icon-box" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="8" y1="13" x2="16" y2="13" /><line x1="8" y1="17" x2="14" y2="17" /></svg></div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
            <button type="button" className="upload-analyze-button" onClick={() => void handleAnalyze()} disabled={selectedFiles.length === 0 || uploadingFiles || selectedFiles.every((item) => item.status !== "ready")}>
              {uploadingFiles ? "در حال پردازش..." : "شروع تحلیل هوشمند"}
            </button>
          </section>
        </main>
      </AppFrame>
    );
  }

  // =========================
  // صفحه تحلیل
  // =========================
  if (authScreen === "analysis") {
    const allFilesDone = selectedFiles.length > 0 && selectedFiles.every((item) => item.status === "done");
    const hasFailure = selectedFiles.some((item) => item.status === "error");
    const isUploading = selectedFiles.some((item) => item.status === "uploading");
    const isProcessing = selectedFiles.some((item) => item.status === "processing");
    const progress = allFilesDone ? 100 : isProcessing ? 66 : isUploading ? 30 : 0;
    const steps = [
      { label: "شناسایی نوع اسناد", state: isUploading ? "active" : isProcessing || allFilesDone ? "complete" : "pending" },
      { label: "استخراج اطلاعات کلیدی", state: isProcessing ? "active" : allFilesDone ? "complete" : "pending" },
      { label: "تطبیق با داستان حقوقی", state: allFilesDone ? "complete" : "pending" },
    ];

    return (
      <AppFrame progress={getProgress()} canGoBack={!uploadingFiles} onBack={() => navigateTo("upload", true)} showFooter={true} dashboardTab={dashboardTab} setDashboardTab={setDashboardTab}>
        <main className="auth-shell analysis-shell">
          <section className="auth-card analysis-card" aria-live="polite">
            <h1 className="analysis-title">تحلیل اسناد</h1>
            <div className={`analysis-progress ${allFilesDone ? "complete" : ""}`} style={{ "--analysis-progress": `${progress}%` }} role="progressbar" aria-label="پیشرفت تحلیل اسناد" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress}>
              <svg className="analysis-sparkle" xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-2-5.8L4 11l6-2.2L12 3Z" /><path d="M19 2v5m-2.5-2.5h5" /><circle cx="5" cy="18" r="1.5" /></svg>
            </div>
            <h2 className="analysis-status">
              {hasFailure ? "تحلیل اسناد انجام نشد" : allFilesDone ? "تحلیل اسناد شما کامل شد" : "در حال تحلیل اسناد شما"}
              {!allFilesDone && !hasFailure && <span className="analysis-ellipsis" aria-hidden="true">...</span>}
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
            {hasFailure && <div className="analysis-error" role="alert">پردازش یکی از اسناد انجام نشد. برای تلاش دوباره به صفحهٔ بارگذاری برگردید.</div>}
            {allFilesDone && (
             <div className="analysis-redirect-loader">
             <span>در حال آماده‌سازی خلاصه...</span>
              <div className="loader-dots"><span></span><span></span><span></span></div>
               {setTimeout(() => navigateTo("document-details"), 2000) && null}
              </div>
            )}
          </section>
          <p className="analysis-footnote"><svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg><span>این فرآیند معمولاً کمتر از یک دقیقه طول می‌کشد</span></p>
        </main>
      </AppFrame>
    );
  }

  // =========================
  // صفحه جزئیات سند
  // =========================
  if (authScreen === "document-details") {
  return (
    <AppFrame progress={getProgress()} canGoBack onBack={() => navigateTo("analysis", true)} showFooter={true} dashboardTab={dashboardTab} setDashboardTab={setDashboardTab}>
      <main className="auth-shell document-details-shell">
        <section className="auth-card document-details-page">
          {/* کادر سفید خالی (بدون متن) */}
          <DocumentDetails documents={selectedFiles.filter((item) => item.status === "done")} />
        </section>
      </main>
    </AppFrame>
  );
}

  return null;
}

export default App;
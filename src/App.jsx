import { useEffect, useRef, useState, useCallback } from "react";
import "./app.css";

import HomeScreen from "./components/HomeScreen";
import CasesScreen from "./components/CasesScreen";
import NoticesScreen from "./components/NoticesScreen";
import AccountScreen from "./components/AccountScreen";
import UploadScreen from "./components/UploadScreen";

import userRoundKey from "./assets/user-round-key.svg";

import BottomNav from "./components/BottomNav";
import ConfirmCategorizationScreen from "./components/ConfirmCategorizationScreen";
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

function AppFrame({ progress, onBack, children, showFooter, dashboardTab, setDashboardTab, activeNoticesCount }) {
  return (
    <div className="app-frame" style={{ paddingBottom: showFooter ? "70px" : "0" }}>
      <header className="app-header">
        <div className="brand">
          <JudiciaryMark />
          <span>همراه حقوقی</span>
        </div>
        {onBack ? (
          <button className="back-button" type="button" onClick={onBack} aria-label="بازگشت">
            <span aria-hidden="true">›</span>
          </button>
        ) : <span className="header-spacer" />}
      </header>
      <div className="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(progress * 100)}>
        <span className="progress-fill" style={{ width: `${progress * 100}%` }} />
      </div>
      {children}
      {showFooter && <BottomNav 
       active={dashboardTab}
       onChange={setDashboardTab}
       activeNoticesCount={activeNoticesCount}
     />}
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
    
  const [hasActiveNotices, setHasActiveNotices] = useState(true); 
  const [casesGoBack, setCasesGoBack] = useState(null);
  const [pendingStoryId, setPendingStoryId] = useState(null);
  const [uploadResults, setUploadResults] = useState([]);

  const registerGoBack = useCallback((fn) => {
    setCasesGoBack(() => fn);
  }, []);

  // یادداشت‌ها
  const [notes, setNotes] = useState([]);
  const [isNoteModalOpen, setIsNoteModalOpen] = useState(false);
  const [noteTitle, setNoteTitle] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [editingNoteId, setEditingNoteId] = useState(null);
  const [selectedNote, setSelectedNote] = useState(null);
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
  const [notices, setNotices] = useState([]);
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

    

  //  تابعی برای گرفتن ابلاغیه‌ها از بک‌اند
  const fetchNotices = async () => {
    if (!authToken) return;
    try {
      // ⚠️ آدرس زیر باید با آدرس API بک‌اند شما هماهنگ باشه
      const res = await fetch("http://127.0.0.1:8001/api/notices/", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setNotices(data); // داده‌های دریافتی رو توی استیت می‌ریزیم
      }
    } catch (error) {
      console.error("خطا در دریافت ابلاغیه‌ها:", error);
    }
  };

  // ۳. هر وقت کاربر وارد داشبورد شد، ابلاغیه‌ها رو بگیر
  useEffect(() => {
    if (authScreen === "dashboard" && authToken) {
      fetchNotices();
    }
  }, [authScreen, authToken]);

    const handleChangePassword = async ({ oldPassword, newPassword }) => {
    try {
      const response = await fetch("http://127.0.0.1:8001/api/change-password/", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}` 
        },
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
      });
      return response.ok;
    } catch (error) {
      console.error("خطا در تغییر رمز:", error);
      return false;
    }
  };

  // ۴. تعداد ابلاغیه‌های فعال رو خودکار حساب می‌کنه
  const activeNoticesCount = notices.filter((n) => n.is_active).length;

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
  // یادداشت‌ها
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

    const handleUpdateProfile = async (updatedData) => {
    try {
      const formData = new FormData();
      formData.append("mobile", updatedData.mobile);
      formData.append("name", updatedData.name);
      formData.append("nationalId", updatedData.nationalId);
      formData.append("gender", updatedData.gender);

      const response = await fetch("http://127.0.0.1:8001/api/patients/", {
        method: "POST",
        headers: { Authorization: `Bearer ${authToken}` },
        body: formData,
      });

      if (response.ok) {
        const [savedLastName = "", ...savedFirstNames] = (updatedData.name || "").split(/\s+/);
        setLastName(savedLastName);
        setFirstName(savedFirstNames.join(" "));
        setPatient(prev => ({ ...prev, name: updatedData.name, nationalId: updatedData.nationalId, gender: updatedData.gender }));
        return true;
      }
      return false;
    } catch (error) {
      console.error("خطا:", error);
      return false;
    }
  };
    const handleLogout = () => {
    // ۱. پاک کردن تمام اطلاعات ذخیره شده در مرورگر
    window.sessionStorage.clear();
    
    // ۲. خالی کردن استیت‌ها
    setAuthToken("");
    setFirstName("");
    setLastName("");
    setMobile("");
    setPatient({ name: "", nationalId: "", age: "", yearOfBirth: "", gender: "" });
    setNotes([]);
    setNotices([]);
    
    // ۳. برگشت به تب خانه و صفحه خوش‌آمدگویی
    setDashboardTab("home");
    setScreenHistory([]);
    setAuthScreen("welcome");
  };

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
    setIsNoteModalOpen(false);
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
  // احراز هویت
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
      setError("ارتباط با سرور برقرار نشد.");
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

    const nextPatient = { ...patient, name: fullName, age: String(currentYear - year), yearOfBirth: birthYear };
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
      setError("ارتباط با سرور برقرار نشد.");
    }
  };

  // =========================
  // رندر صفحات احراز هویت
  // =========================
  if (authScreen !== "complete"
       && authScreen !== "dashboard" 
       && authScreen !== "upload"
       && authScreen !== "confirm_upload"
      ) {
    return (
      <AppFrame progress={getProgress()} onBack={goBack} showFooter={false}>
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
                    <input id="mobile-number" className={phoneErrorKind === "invalid" || phoneErrorKind === "send" ? "input-error" : ""} type="tel" value={mobile} onChange={handleMobileChange} placeholder="مثال :147***0912" maxLength="11" inputMode="numeric" autoComplete="tel" dir="ltr" />
                  </div>
                  {error && <div className="phone-error-message" role="alert">{error}</div>}
                  <button className="auth-button auth-button-primary" type="submit">دریافت کد تأیید</button>
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
                <form className="auth-form" onSubmit={handlePasswordLogin}>
                  <div className="phone-input-panel">
                    <label htmlFor="password-mobile">شماره موبایل</label>
                    <input id="password-mobile" type="tel" value={mobile} onChange={handleMobileChange} maxLength="11" inputMode="numeric" dir="ltr" />
                  </div>
                  <label htmlFor="account-password">رمز عبور</label>
                  <input id="account-password" type="password" value={password} onChange={(event) => { setPassword(event.target.value); setError(""); }} />
                  {error && <div className="error-message" role="alert">{error}</div>}
                  <button className="auth-button auth-button-primary" type="submit">ورود</button>
                </form>
              </>
            )}

            {authScreen === "verify" && (
              <>
                <h1 className="auth-title auth-page-title">{authMode === "signup" ? "تأیید شماره موبایل" : "تأیید ورود"}</h1>
                <p className="auth-description">کد شش‌رقمی ارسال‌شده به شماره <bdi dir="ltr">{maskedMobile}</bdi> را وارد کنید.</p>
                <form className="auth-form verification-form" onSubmit={(event) => { event.preventDefault(); handleVerificationSubmit(); }}>
                  <div className="verification-panel">
                    <div className="verification-inputs" dir="ltr">
                      {Array.from({ length: 6 }, (_, index) => (
                        <input key={index} ref={(element) => { verificationInputs.current[index] = element; }} type="text" value={verificationCode[index] || ""} onChange={(event) => handleVerificationCodeChange(index, event)} onKeyDown={(event) => handleVerificationKeyDown(index, event)} maxLength="6" inputMode="numeric" />
                      ))}
                    </div>
                  </div>
                  {error && <div className="error-message" role="alert">{error}</div>}
                  <button className="auth-button auth-button-primary" type="submit">{authMode === "signup" ? "تأیید و ادامه" : "ورود"}</button>
                </form>
              </>
            )}

            {authScreen === "identity" && (
              <>
                <h1 className="auth-title auth-page-title">تکمیل اطلاعات</h1>
                <form className="auth-form" onSubmit={handleIdentityContinue}>
                  <label htmlFor="identity-last-name">نام خانوادگی</label>
                  <input id="identity-last-name" type="text" value={lastName} onChange={(event) => setLastName(event.target.value)} />
                  <label htmlFor="identity-first-name">نام</label>
                  <input id="identity-first-name" type="text" value={firstName} onChange={(event) => setFirstName(event.target.value)} />
                  <label htmlFor="identity-national-id">کد ملی</label>
                  <input id="identity-national-id" type="text" value={patient.nationalId} onChange={(event) => { const nationalId = toEnglishDigits(event.target.value).replace(/\D/g, "").slice(0, 10); setPatient({ ...patient, nationalId }); }} maxLength="10" inputMode="numeric" dir="ltr" />
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
      <AppFrame progress={getProgress()} onBack={goBack}>
        <main className="auth-shell">
          <section className="auth-card completion-card">
            <div className="completion-icon">✓</div>
            <h1 className="auth-title auth-page-title">اطلاعات با موفقیت ثبت شد</h1>
            <button className="auth-button auth-button-primary" type="button" onClick={() => navigateTo("dashboard", true)}>ورود به حساب</button>
          </section>
        </main>
      </AppFrame>
    );
  }

  // =========================
  // صفحه بارگذاری سند جدید
  // =========================
  if (authScreen === "upload") {
    return (
      <AppFrame progress={getProgress()} canGoBack={true} onBack={() => navigateTo("dashboard", true)} showFooter={true} dashboardTab={dashboardTab} setDashboardTab={setDashboardTab} hasActiveNotices={hasActiveNotices}>
        <main className="auth-shell upload-shell">
          <UploadScreen
            authToken={authToken}
            toPersianDigits={toPersianDigits}
            onUploadSuccess={(resultsArray) => {
             setUploadResults(resultsArray);
             setAuthScreen("confirm_upload"); // ⬅️ می‌ریم به صفحه جدید
            }}
          />
        </main>
      </AppFrame>
    );
  }

      // =========================
  // صفحه تأیید دسته‌بندی اسناد
  // =========================
  if (authScreen === "confirm_upload") {
    return (
      <AppFrame progress={0.8} onBack={() => setAuthScreen("upload")} showFooter={false}>
        <ConfirmCategorizationScreen 
          results={uploadResults} 
          onConfirm={async (finalResults) => {
            try {
              // ⬇️ ارسال تغییرات به بک‌اند ⬇️
              await fetch("http://127.0.0.1:8001/api/confirm-categorization/", {
                method: "POST",
                headers: { 
                  "Content-Type": "application/json",
                  Authorization: `Bearer ${authToken}` 
                },
                body: JSON.stringify({ updates: finalResults })
              });
            } catch (error) {
              console.error("خطا در ذخیره تغییرات:", error);
            }

            // رفتن به پرونده‌ها
            const firstStory = finalResults[0]?.story_id;
            if (firstStory) setPendingStoryId(firstStory);
            setDashboardTab("cases");
            navigateTo("dashboard", true);
          }}
          onCancel={() => setAuthScreen("upload")}
        />
      </AppFrame>
    );
  }

  // =========================
  // صفحه داشبورد
  // =========================
  if (authScreen === "dashboard") {
    return (
      <AppFrame
        progress={getProgress()}
        onBack={() => {
          if (dashboardTab === "cases" && casesGoBack) casesGoBack();
          else if (screenHistory.length > 0) goBack();
        }}
        showFooter={true}
        dashboardTab={dashboardTab}
        setDashboardTab={setDashboardTab}
        activeNoticesCount={activeNoticesCount}
      >
        <main className="auth-shell">
          <section className="auth-card dashboard-card">
            {dashboardTab === "home" && (
             <HomeScreen
             firstName={firstName}
             getCurrentPersianDate={getCurrentPersianDate}
             onNavigate={(screen) => {
             if (screen === "cases") {
             setDashboardTab("cases");   // ⬅️ دقیقاً همون کاری که فوتر می‌کنه
             return;
             }
              navigateTo(screen);           // بقیه (مثل "upload") دست‌نخورده
            }}
           onAddNote={() => { setEditingNoteId(null); setNoteTitle(""); setNoteBody(""); setIsNoteModalOpen(true); }}
           notes={notes}
           onNoteClick={handleNoteClick}
           />
          )}

            {dashboardTab === "cases" && (
              <CasesScreen
                authToken={authToken}
                toPersianDigits={toPersianDigits}
                registerGoBack={registerGoBack}
                initialStoryId={pendingStoryId}
                onStoryOpened={() => setPendingStoryId(null)}
              />
            )}

            {dashboardTab === "notices" && (
              <NoticesScreen
                notices={notices}
                onClose={() => setDashboardTab("home")} />
            )}
            {dashboardTab === "account" && (
             <AccountScreen 
              firstName={firstName} 
              lastName={lastName} 
              mobile={mobile} 
              patient={patient} 
              onUpdateProfile={handleUpdateProfile} 
              onChangePassword={handleChangePassword}
              onLogout={handleLogout}
             />
            )}
          </section>
        </main>

        {/* مودال یادداشت */}
        {isNoteModalOpen && (
          <div className="note-modal-backdrop" onClick={handleCancelNote}>
            <div className="note-modal" onClick={(e) => e.stopPropagation()}>
              <div className="note-modal-header">
                <h2 className="note-modal-title">{editingNoteId ? "ویرایش یادداشت" : "افزودن یادداشت"}</h2>
                <button type="button" className="note-modal-close" onClick={handleCancelNote}>×</button>
              </div>
              <label className="note-modal-label" htmlFor="note-title">موضوع</label>
              <input id="note-title" type="text" className="note-modal-input" value={noteTitle} onChange={(e) => setNoteTitle(e.target.value)} />
              <label className="note-modal-label" htmlFor="note-body">متن یادداشت</label>
              <textarea id="note-body" className="note-modal-textarea" value={noteBody} onChange={(e) => setNoteBody(e.target.value)} rows={5} />
              <div className="note-modal-actions">
                <button type="button" className="note-modal-save" onClick={handleSaveNote}>{editingNoteId ? "ذخیره تغییرات" : "ذخیره یادداشت"}</button>
                <button type="button" className="note-modal-cancel" onClick={handleCancelNote}>انصراف</button>
              </div>
              {editingNoteId && (
                <button type="button" className="note-delete-trigger" onClick={handleDeleteNote}>
                <svg 
                  xmlns="http://www.w3.org/2000/svg" 
                  width="16" 
                  height="16" 
                  viewBox="0 0 24 24" 
                  fill="none" 
                  stroke="currentColor" 
                  strokeWidth="2" 
                  strokeLinecap="round" 
                  strokeLinejoin="round"
                >
      <polyline points="3 6 5 6 21 6"></polyline>
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
      <line x1="10" y1="11" x2="10" y2="17"></line>
      <line x1="14" y1="11" x2="14" y2="17"></line>
    </svg>
    حذف یادداشت
  </button>
)}
            </div>
          </div>
        )}

        {/* مودال تایید حذف یادداشت */}
{isDeleteConfirmOpen && selectedNote && (
  <div className="note-modal-backdrop" onClick={cancelDeleteNote}>
    <div className="note-modal note-delete-modal" onClick={(e) => e.stopPropagation()}>
      
      {/* هدر با عنوان و دکمه ضربدر گوشه */}
      <div className="note-modal-header">
        <h2 className="note-modal-title">حذف یادداشت؟</h2>
        <button type="button" className="note-modal-close" onClick={cancelDeleteNote}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      {/* متن هشدار */}
      <p className="note-delete-description">
        آیا این یادداشت حذف شود؟ پس از حذف، امکان بازگرداندن آن وجود ندارد.
      </p>

      {/* کادر پیش‌نمایش یادداشت (پس‌زمینه صورتی/طوسی) */}
      <div className="note-delete-preview">
        <strong>{selectedNote.title || "بدون موضوع"}</strong>
        {selectedNote.body && <p>{selectedNote.body}</p>}
      </div>

      {/* دکمه‌ها (انصراف آبی، حذف قرمز) */}
      <div className="note-delete-actions">
        <button type="button" className="note-modal-cancel" onClick={cancelDeleteNote}>انصراف</button>
        <button type="button" className="note-delete-confirm" onClick={confirmDeleteNote}>حذف یادداشت</button>
      </div>

    </div>
  </div>
)}
      </AppFrame>
    );
  }

  return null;
}

export default App;
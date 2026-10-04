
import { useEffect, useRef, useState } from "react";
import "./app.css";
import userRoundKey from "./assets/user-round-key.svg";

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
      new Intl.DateTimeFormat("fa-IR-u-ca-persian", { year: "numeric" })
        .format(new Date())
    )
  );

function LockIcon({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
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

function AppFrame({ progress, canGoBack, onBack, children }) {
  return (
    <div className="app-frame">
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
      <div
        className="progress-track"
        role="progressbar"
        aria-label="میزان پیشرفت"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={Math.round(progress * 100)}
      >
        <span className="progress-fill" style={{ width: `${progress * 100}%` }} />
      </div>
      {children}
    </div>
  );
}

function App() {
  const [authScreen, setAuthScreen] = useState("welcome");
  const [screenHistory, setScreenHistory] = useState([]);
  const [authMode, setAuthMode] = useState("signup");
  const [birthYear, setBirthYear] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [authToken, setAuthToken] = useState("");
  const [resendSeconds, setResendSeconds] = useState(0);
  const verificationInputs = useRef([]);

  const [mobile, setMobile] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [error, setError] = useState("");
  const [phoneErrorKind, setPhoneErrorKind] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [nationalIdError, setNationalIdError] = useState(false);
  const [patient, setPatient] = useState({
    name: "",
    nationalId: "",
    age: "",
    yearOfBirth: "",
    gender: "",
  });

  const navigateTo = (screen, replace = false) => {
    if (replace) {
      setScreenHistory((history) => history.slice(0, -1));
    } else {
      setScreenHistory((history) => [...history, authScreen]);
    }
    setAuthScreen(screen);
  };

  const goBack = () => {
    const previousScreen = screenHistory[screenHistory.length - 1];
    if (!previousScreen) {
      return;
    }

    setScreenHistory((history) => history.slice(0, -1));
    setAuthScreen(previousScreen);
    setError("");
  };

  const getProgress = () => {
    if (authScreen === "complete") return 1;
    if (authScreen === "identity") return 0.78;
    if (authScreen === "verify") return 0.57;
    if (authScreen === "phone" || authScreen === "password") return 0.32;
    return 0.08;
  };

  useEffect(() => {
    if (resendSeconds <= 0) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      setResendSeconds((seconds) => Math.max(0, seconds - 1));
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [authScreen, resendSeconds]);

  const formatResendTime = () =>
    `${Math.floor(resendSeconds / 60).toString().padStart(2, "0")}:${(resendSeconds % 60)
      .toString().padStart(2, "0")}`;

  const maskedMobile = mobile.length === 11
    ? toPersianDigits(`${mobile.slice(0, 4)}***${mobile.slice(-4)}`)
    : mobile;
  const codeExpired = authScreen === "verify" && resendSeconds === 0;

  // =========================
  // شماره موبایل
  // =========================
  const handleMobileChange = (e) => {
    const value = toEnglishDigits(e.target.value);

    if (!/^\d*$/.test(value)) {
      return;
    }

    if (value.length > 11) {
      return;
    }

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
    const response = await fetch(
      "http://localhost:5000/api/send-code",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          mobile: mobile,
          mode: authMode,
        }),
      }
    );

    const data = await response.json();

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
      setError(response.status >= 500
        ? "پیامک ارسال نشد، چند لحظه دیگر دوباره تلاش کنید."
        : data.message || "پیامک ارسال نشد، چند لحظه دیگر دوباره تلاش کنید.");
      return;
    }

    setError("");
    setPhoneErrorKind("");
    setVerificationCode("");
    setResendSeconds(180);
    navigateTo("verify");

  } catch (error) {
    console.error(error);
    setPhoneErrorKind("send");
    setError("پیامک ارسال نشد، چند لحظه دیگر دوباره تلاش کنید.");
  }
};

  const handleResendCode = async () => {
    try {
      const response = await fetch("http://localhost:5000/api/send-code", {
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
      console.error(requestError);
      setError("ارتباط با سرور برقرار نشد. ارسال دوباره کد ممکن نیست.");
    }
  };


  // =========================
  // کد تأیید
  // =========================
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
      if (index < 5) {
        verificationInputs.current[index + 1]?.focus();
      }
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
    const response = await fetch(
      "http://localhost:5000/api/verify-code",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          mobile: mobile,
          code: verificationCode,
          mode: authMode,
        }),
      }
    );

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
    // ==========================
    // دریافت پرونده با شماره موبایل
    // ==========================

    const patientResponse = await fetch(
      `http://localhost:5000/api/patients/${mobile}`,
      { headers: { Authorization: `Bearer ${data.token}` } }
    );

    if (patientResponse.ok) {
      const patientData = await patientResponse.json();

      setPatient({
        name: patientData.name || "",
        nationalId: patientData.nationalId || "",
        age: patientData.age || "",
        yearOfBirth: patientData.age
          ? String(getCurrentPersianYear() - Number(patientData.age))
          : "",
        gender: patientData.gender || "",
      });
      const [savedLastName = "", ...savedFirstNames] = (patientData.name || "").split(/\s+/);
      setLastName(savedLastName);
      setFirstName(savedFirstNames.join(" "));
      setBirthYear(patientData.age
        ? String(getCurrentPersianYear() - Number(patientData.age))
        : "");
    } else if (patientResponse.status === 404) {
      setBirthYear("");
    } else {
      const patientError = await patientResponse.json();
      setError(patientError.message || "دریافت اطلاعات حساب انجام نشد.");
      return;
    }

    setError("");
    navigateTo("identity");

  } catch (error) {
    console.error(error);

    setError(
      "ارتباط با سرور برقرار نشد. مطمئن شوید Backend روشن است."
    );
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
      const response = await fetch("http://localhost:5000/api/login", {
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
        yearOfBirth: data.age
          ? String(getCurrentPersianYear() - Number(data.age))
          : "",
        gender: data.gender || "",
      });
      const [savedLastName = "", ...savedFirstNames] = (data.name || "").split(/\s+/);
      setLastName(savedLastName);
      setFirstName(savedFirstNames.join(" "));
      setAuthToken(data.token);
      setBirthYear(data.age
        ? String(getCurrentPersianYear() - Number(data.age))
        : "");
      setAuthMode("login");
      navigateTo("identity");
      setError("");
    } catch (requestError) {
      console.error(requestError);
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
      const response = await fetch("http://localhost:5000/api/patients", {
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
      console.error(requestError);
      setError("ارتباط با سرور برقرار نشد. تکمیل ثبت‌نام ممکن نیست.");
    }
  };

  if (authScreen !== "complete") {
    return (
    <AppFrame
      progress={getProgress()}
      canGoBack={screenHistory.length > 0}
      onBack={goBack}
    >
    <main className="auth-shell">
      <section className="auth-card">
          {authScreen === "welcome" && (
            <>
              <div className="auth-logo">
  <img src={userRoundKey} alt="ورود امن" />
</div>           
              <h1 className="auth-title">ورود امن به همراه حقوقی شما</h1>
              <p className="auth-description">
                برای پیگیری پرونده‌ها و خدمات قضایی وارد حساب خود شوید یا حساب تازه‌ای بسازید.
              </p>

              <div className="privacy-notice">
                <LockIcon className="privacy-lock" />
                <p>
            ورود شما امن است و      اطلاعات بدون اجازه شما به اشتراک گذاشته نمی‌شود.
                </p>
              </div>

              <div className="auth-actions">
                <button
                  type="button"
                  className="auth-button auth-button-primary"
                  onClick={() => {
                    setAuthMode("login");
                    navigateTo("phone");
                    setError("");
                    setPhoneErrorKind("");
                  }}
                >
                  ورود
                </button>
                <button
                  type="button"
                  className="auth-button auth-button-primary"
                  onClick={() => {
                    setAuthMode("signup");
                    navigateTo("phone");
                    setError("");
                    setPhoneErrorKind("");
                  }}
                >
                  ثبت‌ نام
                </button>
              </div>
            </>
          )}

          {authScreen === "phone" && (
            <>
              <h1 className="auth-title auth-page-title">
                {authMode === "signup" ? "ثبت‌نام" : "ورود با پیامک"}
              </h1>
              <p className="auth-description">
                {authMode === "signup"
                  ? "شماره موبایلی که به نام خودتان است وارد کنید."
                  : "شماره موبایل ثبت‌شده در حساب را وارد کنید."}
              </p>

              <form className="auth-form" onSubmit={handleMobileSubmit}>
                <div className={`phone-input-panel ${phoneErrorKind === "invalid" ? "has-error" : ""}`}>
                  <label htmlFor="mobile-number">شماره موبایل</label>
                  <input
                    id="mobile-number"
                    className={phoneErrorKind === "invalid" || phoneErrorKind === "send" ? "input-error" : ""}
                    type="tel"
                    value={mobile}
                    onChange={handleMobileChange}
                    placeholder="مثال :147***0912"
                    maxLength="11"
                    inputMode="numeric"
                    autoComplete="tel"
                    aria-invalid={phoneErrorKind !== ""}
                    dir="ltr"
                  />
                </div>
                {error && (
                  <div className="phone-error-message" role="alert">
                    {phoneErrorKind === "invalid"
                      ? "شماره موبایل معتبر نیست؛ با ۰۹ شروع کنید."
                      : error}
                  </div>
                )}
                <button
                  className="auth-button auth-button-primary"
                  type="submit"
                >
                  {phoneErrorKind === "send" ? "تلاش دوباره برای ارسال" : "دریافت کد تأیید"}
                </button>
              </form>

              {authMode === "login" ? (
                <button
                  className="auth-text-button"
                  type="button"
                  onClick={() => {
                    navigateTo("password");
                    setError("");
                  }}
                >
                  ورود با رمز عبور
                </button>
              ) : (
                <p className="auth-switch">
                  حساب دارید؟{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setAuthMode("login");
                      setError("");
                      setPhoneErrorKind("");
                    }}
                  >
                    ورود
                  </button>
                </p>
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
                  <input
                    id="password-mobile"
                    type="tel"
                    value={mobile}
                    onChange={handleMobileChange}
                    placeholder="مثال :147***0912"
                    maxLength="11"
                    inputMode="numeric"
                    autoComplete="tel"
                    dir="ltr"
                  />
                </div>
                <label htmlFor="account-password">رمز عبور</label>
                <input
                  id="account-password"
                  type="password"
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    setError("");
                  }}
                  autoComplete="current-password"
                />
                {error && <div className="error-message" role="alert">{error}</div>}
                <button className="auth-button auth-button-primary" type="submit">
                  ورود
                </button>
              </form>
              <button
                className="auth-text-button"
                type="button"
                onClick={() => {
                  navigateTo("phone", true);
                  setError("");
                }}
              >
                ورود با پیامک
              </button>
            </>
          )}

          {authScreen === "verify" && (
            <>
              <h1 className="auth-title auth-page-title">
                {authMode === "signup" ? "تأیید شماره موبایل" : "تأیید ورود"}
              </h1>
              {codeExpired && (
                <p className="expired-heading" role="alert">
                  مهلت استفاده از کد به پایان رسیده است.
                </p>
              )}
              <p className="auth-description">
                کد شش‌رقمی ارسال‌شده به شماره{" "}
                <bdi className="verified-mobile" dir="ltr">{maskedMobile}</bdi>
                {" "}را وارد کنید.
              </p>
              <form
                className="auth-form verification-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  handleVerificationSubmit();
                }}
              >
                <div className="verification-panel">
                  
                  <div className="verification-inputs" dir="ltr">
                    {Array.from({ length: 6 }, (_, index) => (
                      <input
                        key={index}
                        ref={(element) => {
                          verificationInputs.current[index] = element;
                        }}
                        id={index === 0 ? "verification-code-1" : undefined}
                        aria-label={`رقم ${index + 1} کد تأیید`}
                        type="text"
                        value={verificationCode[index] === " " ? "" : verificationCode[index] || ""}
                        onChange={(event) => handleVerificationCodeChange(index, event)}
                        onKeyDown={(event) => handleVerificationKeyDown(index, event)}
                        onPaste={(event) => {
                          event.preventDefault();
                          handleVerificationCodeChange(index, {
                            target: { value: event.clipboardData.getData("text") },
                          });
                        }}
                        maxLength="6"
                        inputMode="numeric"
                        autoComplete={index === 0 ? "one-time-code" : "off"}
                      />
                    ))}
                  </div>
                  <p className={`verification-countdown ${codeExpired ? "expired" : ""}`}>
                    {codeExpired ? "زمان کد: 00:00" : (
                      <>ارسال دوباره تا <bdi dir="ltr">{formatResendTime()}</bdi></>
                    )}
                  </p>
                  {!codeExpired && (
                    <button
                      className="resend-button"
                      type="button"
                      onClick={handleResendCode}
                      disabled={resendSeconds > 0}
                    >
                      ارسال دوباره کد
                    </button>
                  )}
                </div>
                {error && !codeExpired && <div className="error-message" role="alert">{error}</div>}
                {codeExpired && (
                  <>
                    <p className="expired-message" role="alert">
                      کد منقضی شده؛ یک کد تازه دریافت کنید.
                    </p>
                    <button
                      className="resend-button resend-button-expired"
                      type="button"
                      onClick={handleResendCode}
                    >
                      ارسال دوباره کد
                    </button>
                  </>
                )}
                <button
                  className="auth-button auth-button-primary"
                  type="submit"
                  disabled={!/^\d{6}$/.test(verificationCode) || codeExpired}
                >
                  {authMode === "signup" ? "تأیید و ادامه" : "ورود"}
                </button>
              </form>
              <button
                className="auth-text-button"
                type="button"
                onClick={() => {
                  navigateTo("phone", true);
                  setVerificationCode("");
                  setError("");
                }}
              >
                تغییر شماره موبایل
              </button>
            </>
          )}

          {authScreen === "identity" && (
            <>
              <h1 className="auth-title auth-page-title">تکمیل اطلاعات</h1>
              <p className="auth-description">
                اطلاعات هویتی را مطابق مدارک رسمی وارد کنید.
              </p>
              <form className="auth-form" onSubmit={handleIdentityContinue}>
                <div className="identity-name-grid">
                  <div className="identity-field">
                    <label htmlFor="identity-last-name"><span className="required-star">*</span> نام خانوادگی </label>
                    <input
                      id="identity-last-name"
                      type="text"
                      value={lastName}
                      onChange={(event) => setLastName(event.target.value)}
                      autoComplete="family-name"
                      required
                    />
                  </div>
                  <div className="identity-field">
                    <label htmlFor="identity-first-name"> <span className="required-star">*</span>نام </label>
                    <input
                      id="identity-first-name"
                      type="text"
                      value={firstName}
                      onChange={(event) => setFirstName(event.target.value)}
                      autoComplete="given-name"
                      required
                    />
                  </div>
                </div>
                <label htmlFor="identity-national-id"><span className="required-star">*</span>کد ملی </label>
                <input
                  id="identity-national-id"
                  type="text"
                  className={nationalIdError ? "national-id-error" : ""}
                  value={patient.nationalId}
                  onChange={(event) => {
                    const nationalId = toEnglishDigits(event.target.value)
                      .replace(/\D/g, "")
                      .slice(0, 10);
                    setPatient({ ...patient, nationalId });
                    if (isValidIranianNationalId(nationalId)) {
                      setNationalIdError(false);
                    }
                  }}
                  maxLength="10"
                  inputMode="numeric"
                  dir="ltr"
                  required
                  aria-invalid={nationalIdError}
                />
                {nationalIdError && (
                  <div className="national-id-error-message" role="alert">
                    کد ملی ایرانی واردشده معتبر نیست.
                  </div>
                )}
                <label><span className="required-star">*</span>جنسیت </label>
                <div className="gender-options">
                  <label className={`gender-option ${patient.gender === "male" ? "selected" : ""}`}>
                    <input
                      type="radio"
                      name="identity-gender"
                      value="male"
                      checked={patient.gender === "male"}
                      onChange={(event) =>
                        setPatient({ ...patient, gender: event.target.value })
                      }
                    />
                    مرد
                  </label>
                  <label className={`gender-option ${patient.gender === "female" ? "selected" : ""}`}>
                    <input
                      type="radio"
                      name="identity-gender"
                      value="female"
                      checked={patient.gender === "female"}
                      onChange={(event) =>
                        setPatient({ ...patient, gender: event.target.value })
                      }
                    />
                    زن
                  </label>
                </div>
                <label htmlFor="identity-birth-year"><span className="required-star">*</span>سال تولد </label>
                <input
                  id="identity-birth-year"
                  type="text"
                  value={birthYear}
                  onChange={(event) =>
                    setBirthYear(toEnglishDigits(event.target.value).replace(/\D/g, "").slice(0, 4))
                  }
                  maxLength="4"
                  inputMode="numeric"
                  placeholder="انتخاب سال شمسی"
                  dir="ltr"
                  required
                />
                {authMode === "signup" && (
                  <>
                    <label htmlFor="new-password">ایجاد رمز عبور</label>
                    <input
                      id="new-password"
                      type="password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      autoComplete="new-password"
                      minLength="8"
                    />
                    <small>رمز عبور باید حداقل ۸ نویسه باشد.</small>
                    <label htmlFor="confirm-password">تکرار رمز عبور</label>
                    <input
                      id="confirm-password"
                      type="password"
                      value={passwordConfirmation}
                      onChange={(event) => setPasswordConfirmation(event.target.value)}
                      autoComplete="new-password"
                    />
                  </>
                )}
                {error && <div className="error-message" role="alert">{error}</div>}
                <button className="auth-button auth-button-primary" type="submit">
                  تکمیل ثبت‌ نام
                </button>
              </form>
            </>
          )}
          <SecurityFooter />
        </section>
      </main>
      </AppFrame>
    );
  }

  // =========================
  // صفحه تکمیل ثبت‌نام
  // =========================
  return (
    <AppFrame progress={getProgress()} canGoBack={screenHistory.length > 0} onBack={goBack}>
      <main className="auth-shell">
        <section className="auth-card completion-card" aria-live="polite">
          <div className="completion-icon" aria-hidden="true">✓</div>
          <h1 className="auth-title auth-page-title">اطلاعات با موفقیت ثبت شد</h1>
          <p className="auth-description">
            اطلاعات هویتی شما با موفقیت ذخیره شد.
          </p>
          <button className="auth-button auth-button-primary" type="button" onClick={() => {
            setAuthMode("login");
            navigateTo("phone");
          }}>
            ورود به حساب
          </button>
          <SecurityFooter />
        </section>
      </main>
    </AppFrame>
  );
}

export default App;

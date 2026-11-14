import React, { useState, useEffect } from "react";

function AccountScreen({ 
  firstName, 
  lastName, 
  mobile, 
  patient, 
  onUpdateProfile, 
  onChangePassword,
  onLogout          
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [isContactOpen, setIsContactOpen] = useState(false);
  const [isPasswordOpen, setIsPasswordOpen] = useState(false); 
  const [isSecurityOpen, setIsSecurityOpen] = useState(false); 
  const [isSettingsOpen, setIsSettingsOpen] = useState(false); // ⬅️ استیت جدید تنظیمات
  
  const [loading, setLoading] = useState(false);

  // استیت‌های تنظیمات (سوییچ‌ها)
  const [smsNotify, setSmsNotify] = useState(true);
  const [appNotify, setAppNotify] = useState(true);
  const [darkMode, setDarkMode] = useState(false);

  // استیت‌های فرم ویرایش
  const [editFirstName, setEditFirstName] = useState(firstName || "");
  const [editLastName, setEditLastName] = useState(lastName || "");
  const [editNationalId, setEditNationalId] = useState(patient?.nationalId || "");
  const [editGender, setEditGender] = useState(patient?.gender || "");

  // استیت‌های فرم رمز عبور
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");

  useEffect(() => {
    if (isEditing) {
      setEditFirstName(firstName || "");
      setEditLastName(lastName || "");
      setEditNationalId(patient?.nationalId || "");
      setEditGender(patient?.gender || "");
    }
  }, [isEditing, firstName, lastName, patient]);

  const handleSave = async () => {
    setLoading(true);
    const success = await onUpdateProfile({
      name: `${editLastName.trim()} ${editFirstName.trim()}`.trim(),
      nationalId: editNationalId,
      gender: editGender,
      mobile: mobile
    });
    setLoading(false);
    if (success) setIsEditing(false);
    else alert("خطا در ذخیره اطلاعات.");
  };

  const handleSavePassword = async () => {
    setPasswordError("");
    if (!oldPassword || !newPassword || !confirmPassword) return setPasswordError("همه فیلدها را پر کنید.");
    if (newPassword !== confirmPassword) return setPasswordError("رمز عبور جدید و تکرار آن یکسان نیستند.");
    if (newPassword.length < 8) return setPasswordError("رمز عبور باید حداقل ۸ کاراکتر باشد.");

    setLoading(true);
    const success = await onChangePassword({ oldPassword, newPassword });
    setLoading(false);

    if (success) {
      alert("رمز عبور با موفقیت تغییر کرد.");
      setIsPasswordOpen(false);
      setOldPassword(""); setNewPassword(""); setConfirmPassword("");
    } else {
      setPasswordError("رمز عبور فعلی اشتباه است یا خطایی رخ داد.");
    }
  };

  // -----------------------------------------
  // ۱. صفحه تنظیمات و اعلان‌ها (جدید)
  // -----------------------------------------
  if (isSettingsOpen) {
    return (
      <div className="account-page">
        <div className="account-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 className="account-title">تنظیمات برنامه</h2>
          <button onClick={() => setIsSettingsOpen(false)} style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: "0.85rem" }}>بازگشت</button>
        </div>
        
        <div className="account-list" style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
          
          {/* اعلان پیامکی */}
          <div className="setting-row">
            <div>
              <span className="setting-title">اعلان‌های پیامکی</span>
              <span className="setting-desc">دریافت ابلاغیه‌ها و جلسات از طریق پیامک</span>
            </div>
            <label className="switch">
              <input type="checkbox" checked={smsNotify} onChange={() => setSmsNotify(!smsNotify)} />
              <span className="slider"></span>
            </label>
          </div>

          {/* اعلان برنامه */}
          <div className="setting-row">
            <div>
              <span className="setting-title">اعلان‌های درون‌برنامه‌ای</span>
              <span className="setting-desc">نمایش هشدارها داخل اپلیکیشن</span>
            </div>
            <label className="switch">
              <input type="checkbox" checked={appNotify} onChange={() => setAppNotify(!appNotify)} />
              <span className="slider"></span>
            </label>
          </div>

          {/* حالت تاریک */}
          <div className="setting-row">
            <div>
              <span className="setting-title">حالت تاریک</span>
              <span className="setting-desc">تغییر ظاهر برنامه به رنگ‌های تیره</span>
            </div>
            <label className="switch">
              <input type="checkbox" checked={darkMode} onChange={() => setDarkMode(!darkMode)} />
              <span className="slider"></span>
            </label>
          </div>

          {/* نسخه برنامه */}
          <div className="setting-row" style={{ borderBottom: "none" }}>
            <div>
              <span className="setting-title">نسخه برنامه</span>
              <span className="setting-desc" dir="ltr">v1.0.0</span>
            </div>
          </div>

        </div>
      </div>
    );
  }

  // -----------------------------------------
  // (بقیه صفحات ویرایش، راه ارتباطی، رمز عبور و امنیت مثل قبل...)
  // -----------------------------------------
  
  if (isEditing) {
    return (
      <div className="account-page">
        <div className="account-header"><h2 className="account-title">ویرایش اطلاعات</h2></div>
        <div className="account-profile-card" style={{ flexDirection: "column", alignItems: "stretch", gap: "12px", marginTop: "16px", backgroundColor: "#fff", border: "1px solid #e5eaf0" }}>
          <label style={{ fontSize: "0.8rem", color: "#6b7280" }}>نام</label>
          <input type="text" value={editFirstName} onChange={(e) => setEditFirstName(e.target.value)} className="edit-input" />
          <label style={{ fontSize: "0.8rem", color: "#6b7280" }}>نام خانوادگی</label>
          <input type="text" value={editLastName} onChange={(e) => setEditLastName(e.target.value)} className="edit-input" />
          <label style={{ fontSize: "0.8rem", color: "#6b7280" }}>کد ملی</label>
          <input type="text" value={editNationalId} onChange={(e) => setEditNationalId(e.target.value)} dir="ltr" className="edit-input" />
          <label style={{ fontSize: "0.8rem", color: "#6b7280" }}>جنسیت</label>
          <select value={editGender} onChange={(e) => setEditGender(e.target.value)} className="edit-input">
            <option value="">انتخاب کنید</option>
            <option value="male">مرد</option>
            <option value="female">زن</option>
          </select>
          <div style={{ display: "flex", gap: "10px", marginTop: "16px" }}>
            <button onClick={handleSave} disabled={loading} style={{ flex: 1, padding: "12px", backgroundColor: "#2563eb", color: "#fff", border: "none", borderRadius: "8px", cursor: "pointer", fontWeight: "bold" }}>
              {loading ? "در حال ذخیره..." : "ثبت تغییرات"}
            </button>
            <button onClick={() => setIsEditing(false)} style={{ flex: 1, padding: "12px", backgroundColor: "#f3f4f6", color: "#333", border: "none", borderRadius: "8px", cursor: "pointer" }}>انصراف</button>
          </div>
        </div>
      </div>
    );
  }

  if (isContactOpen) {
    return (
      <div className="account-page">
        <div className="account-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 className="account-title">راه‌های ارتباطی</h2>
          <button onClick={() => setIsContactOpen(false)} style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: "0.85rem" }}>بازگشت</button>
        </div>
        <div className="account-list" style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <div className="account-item" style={{ display: "flex", justifyContent: "space-between", padding: "16px", backgroundColor: "#fff", borderRadius: "12px", border: "1px solid #e5eaf0" }}>
            <span style={{ fontSize: "0.85rem", color: "#333" }}>شماره موبایل</span>
            <span dir="ltr" style={{ fontSize: "0.85rem", fontWeight: "bold" }}>{mobile}</span>
          </div>
          <button className="account-item" style={{ display: "flex", justifyContent: "space-between", padding: "16px", backgroundColor: "#eaf2ff", borderRadius: "12px", border: "1px solid #d2e3fc", cursor: "pointer" }}>
            <span style={{ fontSize: "0.85rem", color: "#2563eb", fontWeight: "bold" }}>تماس با پشتیبانی حقوقی</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
          </button>
        </div>
      </div>
    );
  }

  if (isPasswordOpen) {
    return (
      <div className="account-page">
        <div className="account-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 className="account-title">تغییر رمز عبور</h2>
          <button onClick={() => setIsPasswordOpen(false)} style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: "0.85rem" }}>بازگشت</button>
        </div>
        <div className="account-profile-card" style={{ flexDirection: "column", alignItems: "stretch", gap: "12px", marginTop: "16px", backgroundColor: "#fff", border: "1px solid #e5eaf0" }}>
          <label style={{ fontSize: "0.8rem", color: "#6b7280" }}>رمز عبور فعلی</label>
          <input type="password" value={oldPassword} onChange={(e) => setOldPassword(e.target.value)} className="edit-input" />
          <label style={{ fontSize: "0.8rem", color: "#6b7280" }}>رمز عبور جدید</label>
          <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="edit-input" />
          <label style={{ fontSize: "0.8rem", color: "#6b7280" }}>تکرار رمز عبور جدید</label>
          <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="edit-input" />
          {passwordError && <p style={{ color: "#ef4444", fontSize: "0.75rem", margin: 0 }}>{passwordError}</p>}
          <button onClick={handleSavePassword} disabled={loading} style={{ marginTop: "16px", padding: "12px", backgroundColor: "#2563eb", color: "#fff", border: "none", borderRadius: "8px", cursor: "pointer", fontWeight: "bold" }}>
            {loading ? "در حال ذخیره..." : "تغییر رمز عبور"}
          </button>
        </div>
      </div>
    );
  }

  if (isSecurityOpen) {
    return (
      <div className="account-page">
        <div className="account-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 className="account-title">مدیریت ورود و امنیت</h2>
          <button onClick={() => setIsSecurityOpen(false)} style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: "0.85rem" }}>بازگشت</button>
        </div>
        <div className="account-list" style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ padding: "16px", backgroundColor: "#fff", borderRadius: "12px", border: "1px solid #e5eaf0" }}>
            <h4 style={{ margin: "0 0 8px 0", fontSize: "0.85rem", color: "#1a1a1a" }}>دستگاه‌های فعال</h4>
            <p style={{ margin: "0 0 12px 0", fontSize: "0.75rem", color: "#6b7280" }}>شما در حال حاضر در ۲ دستگاه وارد شده‌اید.</p>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px", backgroundColor: "#f9fafb", borderRadius: "8px", marginBottom: "8px" }}>
              <div>
                <span style={{ fontSize: "0.8rem", fontWeight: "bold", display: "block" }}>این دستگاه (ویندوز)</span>
                <span style={{ fontSize: "0.7rem", color: "#10b981" }}>فعال</span>
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px", backgroundColor: "#f9fafb", borderRadius: "8px" }}>
              <div>
                <span style={{ fontSize: "0.8rem", fontWeight: "bold", display: "block" }}>گوشی همراه (اندروید)</span>
                <span style={{ fontSize: "0.7rem", color: "#6b7280" }}>۲ روز پیش</span>
              </div>
              <button style={{ background: "none", border: "1px solid #ef4444", color: "#ef4444", borderRadius: "6px", padding: "4px 8px", fontSize: "0.7rem", cursor: "pointer" }}>خروج</button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // -----------------------------------------
  // منوی اصلی
  // -----------------------------------------
  return (
    <div className="account-page">
      <div className="account-header">
        <h2 className="account-title">حساب من</h2>
        <p className="account-subtitle">مدیریت اطلاعات و تنظیمات</p>
      </div>

      <div className="account-profile-card">
        <div className="profile-avatar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
        </div>
        <div className="profile-info">
          <h3>{firstName} {lastName}</h3>
          <p dir="ltr" className="profile-mobile">{mobile}</p>
          <p className="profile-national-id">کد ملی: {patient?.nationalId || "ثبت نشده"}</p>
        </div>
        <div className="profile-arrow">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
        </div>
      </div>

      <div className="account-section">
        <h4 className="section-title">اطلاعات شخصی</h4>
        <div className="account-list">
          <button className="account-item" onClick={() => setIsEditing(true)}>
            <div className="item-right-side"><div className="item-icon-box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></div><span>ویرایش اطلاعات شخصی</span></div>
            <svg className="item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
          <button className="account-item" onClick={() => setIsContactOpen(true)}>
            <div className="item-right-side"><div className="item-icon-box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg></div><span>شماره تماس و راه‌های ارتباطی</span></div>
            <svg className="item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
        </div>
      </div>

      <div className="account-section">
        <h4 className="section-title">امنیت</h4>
        <div className="account-list">
          <button className="account-item" onClick={() => setIsPasswordOpen(true)}>
            <div className="item-right-side"><div className="item-icon-box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div><span>تغییر رمز عبور</span></div>
            <svg className="item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
          <button className="account-item" onClick={() => setIsSecurityOpen(true)}>
            <div className="item-right-side"><div className="item-icon-box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></div><span>مدیریت ورود و امنیت</span></div>
            <svg className="item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
        </div>
      </div>

      <div className="account-section">
        <h4 className="section-title">تنظیمات برنامه</h4>
        <div className="account-list">
          {/* ⬅️ دکمه تنظیمات وصل شد */}
          <button className="account-item" onClick={() => setIsSettingsOpen(true)}>
            <div className="item-right-side"><div className="item-icon-box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg></div><span>اعلان‌ها و تنظیمات برنامه</span></div>
            <svg className="item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
          
          {/* ⬅️ دکمه خروج */}
          <button className="account-item text-danger" onClick={onLogout}>
            <div className="item-right-side"><div className="item-icon-box danger-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg></div><span>خروج از حساب کاربری</span></div>
            <svg className="item-arrow text-danger" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export default AccountScreen;
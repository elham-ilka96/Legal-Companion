import React from "react";

// دقت کنید اگر از آیکون‌های lucide-react استفاده می‌کنید، ایمپورت‌ها را اضافه کنید.
// در اینجا از SVG مستقیم استفاده شده تا نیازی به نصب پکیج نباشد.

function AccountScreen({ firstName, lastName, mobile }) {
  return (
    <div className="account-page">
      {/* هدر صفحه */}
      <div className="account-header">
        <h2 className="account-title">حساب من</h2>
        <p className="account-subtitle">مدیریت اطلاعات و تنظیمات</p>
      </div>

      {/* کارت پروفایل با بک‌گراند آبی کمرنگ */}
      <div className="account-profile-card">
          <div className="profile-avatar">
          {/* اگر عکس دارید، اینجا img قرار بدید، فعلاً یک دایره آبی با آیکون */}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
        <div className="profile-info">
          {/* نام و نام خانوادگی اصلاح شد */}
          <h3>{firstName} {lastName}</h3>
          <p dir="ltr" className="profile-mobile">{mobile}</p>
          {/* کد ملی */}
          <p className="profile-national-id">کد ملی: ۰۰۱۲۳۴۵۶۷۸</p>
        </div>
        
        {/* فلش بزرگ سمت چپ */}
        <div className="profile-arrow">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </div>
      </div>

      {/* بخش اطلاعات شخصی */}
      <div className="account-section">
        <h4 className="section-title">اطلاعات شخصی</h4>
        <div className="account-list">
          <button className="account-item">
            <div className="item-right-side">
              <div className="item-icon-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              </div>
              <span>ویرایش اطلاعات شخصی</span>
            </div>
            <svg className="item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>

          <button className="account-item">
            <div className="item-right-side">
              <div className="item-icon-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
              </div>
              <span>شماره تماس و راه‌های ارتباطی</span>
            </div>
            <svg className="item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
        </div>
      </div>

      {/* بخش امنیت */}
      <div className="account-section">
        <h4 className="section-title">امنیت</h4>
        <div className="account-list">
          <button className="account-item">
            <div className="item-right-side">
              <div className="item-icon-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              </div>
              <span>تغییر رمز عبور</span>
            </div>
            <svg className="item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>

          <button className="account-item">
            <div className="item-right-side">
              <div className="item-icon-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              </div>
              <span>مدیریت ورود و امنیت</span>
            </div>
            <svg className="item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
        </div>
      </div>

      {/* بخش تنظیمات برنامه */}
      <div className="account-section">
        <h4 className="section-title">تنظیمات برنامه</h4>
        <div className="account-list">
          <button className="account-item">
            <div className="item-right-side">
              <div className="item-icon-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
              </div>
              <span>اعلان‌ها و تنظیمات برنامه</span>
            </div>
            <svg className="item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>

          <button className="account-item text-danger">
            <div className="item-right-side">
              <div className="item-icon-box danger-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
              </div>
              <span>خروج از حساب کاربری</span>
            </div>
            <svg className="item-arrow text-danger" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export default AccountScreen;
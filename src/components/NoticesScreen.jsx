import React from "react";
import "./NoticesScreen.css";

// تابعی برای تبدیل اعداد انگلیسی به فارسی
const toPersianDigits = (str) => {
  if (!str) return "";
  const persianDigits = "۰۱۲۳۴۵۶۷۸۹";
  return str.toString().replace(/\d/g, (d) => persianDigits[parseInt(d)]);
};

function NoticesScreen({ notices = [], onClose }) {
  return (
    <div className="notices-page">
      <div className="notices-header">
        <h1 className="notices-title">ابلاغیه‌ها</h1>
        <button className="close-square-btn" onClick={onClose} aria-label="بستن">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
          </svg>
        </button>
      </div>

      <div className="notices-list">
        {notices.length === 0 ? (
          <p className="empty-text-small" style={{ textAlign: "center", marginTop: "20px", color: "#888" }}>
            هیچ ابلاغیه‌ای وجود ندارد.
          </p>
        ) : (
          notices.map((notice) => (
            <div key={notice.id} className="notice-card">
              <div className="notice-info">
                <h3 className="notice-doc-title">{notice.document_title}</h3>
                <p className="notice-story-title">{notice.story_title}</p>
                
                {/* ⬇️ اینجا تابع رو صدا زدیم ⬇️ */}
                <p className="notice-datetime">
                  {toPersianDigits(notice.date)} - ساعت {toPersianDigits(notice.time)}
                </p>
              </div>

              <div className="notice-status">
                {notice.is_active ? (
                  <>
                    <div className="notice-active-dot"></div>
                    <div className="notice-hearing-box">
                      {/* ⬇️ اینجا هم تابع رو صدا زدیم ⬇️ */}
                      {toPersianDigits(notice.hearing_date)}، {toPersianDigits(notice.hearing_time || notice.time)}
                    </div>
                  </>
                ) : (
                  <span className="notice-expired-text">مهلت اعتراض پایان یافته</span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default NoticesScreen;
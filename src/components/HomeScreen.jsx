import React from "react";

function HomeScreen({ 
  firstName, 
  getCurrentPersianDate, 
  onNavigate, 
  onAddNote, 
  notes = [], 
  onNoteClick 
}) {
  return (
    <div className="home-screen">
      {/* هدر خوش‌آمدگویی */}
      <header className="dashboard-greeting">
        <h2 className="dashboard-hello">سلام، {firstName || "کاربر"}</h2>
        <p className="dashboard-date">{getCurrentPersianDate()}</p>
      </header>

      {/* پنل بارگذاری سند */}
      <div className="dashboard-upload-panel">
        <h3 className="dashboard-upload-title">پرونده‌های شما در یک نگاه</h3>
        <p className="dashboard-upload-description">
          سند دادگاه، ابلاغیه یا قرارداد جدید را بارگذاری کنید تا هوش مصنوعی آن را به زبان ساده تحلیل کند.
        </p>
        <button type="button" className="dashboard-upload-button" onClick={() => onNavigate("upload")}>
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="16 16 12 12 8 16" /><line x1="12" y1="12" x2="12" y2="21" /><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" /></svg>
          بارگذاری سند جدید
        </button>
      </div>

      {/* دکمه‌های عملیات سریع */}
      <div className="dashboard-quick-actions">
        <div className="dashboard-action-card" onClick={() => onNavigate("cases")} role="button" tabIndex={0}>
          <svg className="dashboard-action-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h6l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" /></svg>
          <span className="dashboard-action-label">مشاهده پرونده</span>
        </div>
        
        <div className="dashboard-action-card" onClick={onAddNote} role="button" tabIndex={0}>
          <svg className="dashboard-action-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" /></svg>
          <span className="dashboard-action-label">افزودن یادداشت</span>
        </div>
        
        <div className="dashboard-action-card">
          <svg className="dashboard-action-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="6" y="2" width="12" height="20" rx="2" ry="2" /><line x1="12" y1="18" x2="12.01" y2="18" /></svg>
          <span className="dashboard-action-label">تماس با وکیل</span>
        </div>
      </div>

      {/* بخش نیازمند توجه */}
      <div className="dashboard-section-header">
        <h3 className="dashboard-section-title">نیازمند توجه</h3>
        <button type="button" className="dashboard-section-link">مشاهده همه</button>
      </div>

      <div className="dashboard-attention-panel">
        {/* نزدیک‌ترین مهلت */}
        <div className="dashboard-deadline-row">
          <div className="dashboard-deadline-icon-box">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>
          </div>
          <span className="dashboard-deadline-title">نزدیک‌ترین مهلت</span>
          <svg className="dashboard-deadline-arrow" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="15 18 9 12 15 6" /></svg>
        </div>

        {/* ابلاغیه */}
        <div className="dashboard-notice-box">
          <p className="dashboard-notice-text">ابلاغیه جدید از شعبه ۱۵ تهران</p>
        </div>

        {/* لیست یادداشت‌ها */}
        {notes.map((note) => (
          <div 
            className="dashboard-note-box" 
            key={note.id} 
            onClick={() => onNoteClick(note)} 
            role="button" 
            tabIndex={0} 
            style={{ cursor: "pointer" }}
          >
            <div className="dashboard-note-header">
              <span className="dashboard-note-time">
                امروز، ساعت {new Date(note.created_at).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' })}
              </span>
              <span className="dashboard-note-badge">یادداشت</span>
            </div>
            <p className="dashboard-note-title">{note.title}</p>
            {note.body && <p className="dashboard-note-body">{note.body}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

export default HomeScreen;
import { useState } from "react";
import "./DocumentDetails.css";

function DocumentDetails({ documents = [], story = null, onBack, authToken }) {
  const [selectedCase, setSelectedCase] = useState(null);

  if (selectedCase) {
    return (
      <div className="legal-story-page">
        <div className="legal-story-container">
          <button className="auth-text-button" onClick={() => setSelectedCase(null)} style={{ marginBottom: '16px', alignSelf: 'flex-start' }}>
            ← بازگشت
          </button>
          <h1 className="case-detail-title-plain">{selectedCase.main_topic || selectedCase.topic || "پرونده"}</h1>
          <section className="story-card case-detail-card">
            <h2 className="case-detail-section-title">مشخصات پرونده</h2>
            <div className="detail-block">
              <span className="detail-label">نوع پرونده</span>
              <span className="detail-value dark">{selectedCase.topic || "نامشخص"}</span>
            </div>
            <div className="detail-block">
              <span className="detail-label">شماره پرونده</span>
              <span className="detail-value blue" dir="ltr">{selectedCase.case_number || "نامشخص"}</span>
            </div>
            <div className="detail-block">
              <span className="detail-label">مرجع رسیدگی</span>
              <span className="detail-value dark">{selectedCase.court || "نامشخص"}</span>
            </div>
            <div className="detail-status-row">
              <span className="detail-label">وضعیت پرونده</span>
              <span className="case-status-badge">در جریان</span>
            </div>
          </section>
          <section className="story-card summary-card">
            <h2 className="story-card-title">خلاصه داستان</h2>
            <p className="story-card-text">{selectedCase.summary || "خلاصه‌ای ثبت نشده است."}</p>
          </section>
        </div>
      </div>
    );
  }

  const latestDocument = documents[documents.length - 1];
  if (!latestDocument) {
    return (
      <div className="legal-story-page">
        <div className="legal-story-container">
          <p>سندی برای نمایش وجود ندارد.</p>
        </div>
      </div>
    );
  }

  const data = latestDocument.extractedData || {};
  const relatedCases = data.related_cases || [];

  return (
    <div className="legal-story-page">
      <div className="legal-story-container">
        <div className="story-header-center">
          <h1 className="story-title-center">{data.main_topic && data.main_topic !== "نامشخص" ? data.main_topic : "پرونده حقوقی"}</h1>
          <span className="story-status-badge-center">در جریان</span>
        </div>
        <section className="story-card summary-card">
          <h2 className="story-card-title">خلاصه داستان</h2>
          <p className="story-card-text">{data.summary || "خلاصه‌ای تولید نشد."}</p>
        </section>
        {relatedCases.length > 0 && (
          <section className="related-cases-section">
            <h2 className="section-title">پرونده‌های مرتبط</h2>
            {relatedCases.map((rc) => (
              <div className="story-card case-item-card" key={rc.id}>
                <div className="case-item-header">
                  <div className="case-item-info">
                    <h3 className="case-item-title">{rc.title || "پرونده"}</h3>
                    <p className="case-number">شماره پرونده: <span dir="ltr">{rc.case_number || "نامشخص"}</span></p>
                    <p className="case-branch">{rc.court || "نامشخص"}</p>
                  </div>
                  <button className="case-status-badge" onClick={() => setSelectedCase(rc)} style={{ border: 'none', cursor: 'pointer' }}>فعال</button>
                </div>
              </div>
            ))}
          </section>
        )}
      </div>
    </div>
  );
}

export default DocumentDetails;
import { useState, useEffect } from "react";
import "./CasesScreen.css";

function CasesScreen({ authToken, initialStoryId, onStoryOpened }) {
  const [activeScreen, setActiveScreen] = useState("list"); // list | story | case | document
  const [stories, setStories] = useState([]);
  const [selectedStory, setSelectedStory] = useState(null);
  const [selectedCase, setSelectedCase] = useState(null);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);

  // دریافت لیست داستان‌ها از بک‌اند
  useEffect(() => {
    const fetchStories = async () => {
      if (!authToken) return;
      try {
        const res = await fetch("http://127.0.0.1:8001/api/legal-stories/", {
          headers: { Authorization: `Bearer ${authToken}` },
        });
        if (res.ok) {
          const data = await res.json();
          setStories(data);
        }
      } catch (e) {
        console.error("خطا در دریافت داستان‌ها:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchStories();
  }, [authToken]);

  // اگر از صفحه آپلود برگشتیم و storyId داشتیم، مستقیم برو بهش
  useEffect(() => {
    if (initialStoryId) {
      handleStoryClick(initialStoryId);
      if (onStoryOpened) onStoryOpened();
    }
  }, [initialStoryId]);

  // بازگشت به صفحه قبل
  const handleBack = () => {
    if (activeScreen === "document") {
      setActiveScreen("case");
      setSelectedDocument(null);
    } else if (activeScreen === "case") {
      setActiveScreen("story");
      setSelectedCase(null);
    } else if (activeScreen === "story") {
      setActiveScreen("list");
      setSelectedStory(null);
    }
  };

  // بستن کامل صفحه سند و برگشت به لیست اصلی
  const handleCloseAll = () => {
    setActiveScreen("list");
    setSelectedDocument(null);
    setSelectedCase(null);
    setSelectedStory(null);
  };

  // وقتی روی یک داستان کلیک می‌شود
  const handleStoryClick = async (storyId) => {
    try {
      const res = await fetch(`http://127.0.0.1:8001/api/legal-stories/${storyId}/`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSelectedStory(data);
        setActiveScreen("story");
      }
    } catch (e) {
      console.error("خطا در دریافت جزئیات داستان:", e);
    }
  };

  // -----------------------------------------
  // ۱. صفحه لیست داستان‌ها
  // -----------------------------------------
  if (activeScreen === "list") {
    const filteredStories = stories.filter((s) =>
      s.title.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
      <div className="cases-list-page">
        <div className="cases-header">
          <h1 className="cases-title">پرونده‌ها</h1>
        </div>

        <div className="cases-search-bar">
          <input
            type="text"
            placeholder="جستجو در عنوان یا شماره پرونده..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <svg className="search-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </div>

        <div className="stories-list">
          {loading ? (
            <p className="loading-text">در حال بارگذاری...</p>
          ) : filteredStories.length === 0 ? (
            <p className="empty-text">هیچ پرونده‌ای یافت نشد.</p>
          ) : (
            filteredStories.map((story) => (
              <div 
                key={story.id} 
                className="story-card"
                onClick={() => handleStoryClick(story.id)}
              >
                <div className="story-card-header">
                  <h3 className="story-card-title">{story.title}</h3>
                </div>
                <div className="story-card-details">
                  <p className="story-card-date">آخرین تاریخ: {new Date(story.created_at).toLocaleDateString('fa-IR')}</p>
                  <p className="story-card-branch">شعبه: {story.branch || story.court || "نامشخص"}</p>
                </div>
                <div className="story-card-footer">
                  <div className="next-hearing-container">
                    <span className="next-hearing">جلسه بعدی: تعیین نشده</span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    );
  }

  // -----------------------------------------
  // ۲. صفحه جزئیات داستان
  // -----------------------------------------
  if (activeScreen === "story" && selectedStory) {
    return (
      <div className="story-detail-page">
        <div className="detail-header">
          <button className="back-circle-btn" onClick={handleBack}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
          </button>
          <h1 className="detail-title-blue">{selectedStory.title}</h1>
        </div>

        <div className="white-card">
          <h2 className="card-title-blue">خلاصه داستان</h2>
          <p className="summary-text">{selectedStory.summary || "خلاصه‌ای ثبت نشده است."}</p>
        </div>

        <h3 className="section-title-black">پرونده‌های مرتبط</h3>
        <div className="related-cases-list">
          {selectedStory.cases && selectedStory.cases.length > 0 ? (
            selectedStory.cases.map((c) => (
              <div 
                key={c.id} 
                className="white-card case-card-clickable case-card-outlined"
                onClick={() => { setSelectedCase(c); setActiveScreen("case"); }}
              >
                <div className="case-card-row">
                  <div>
                    <h4 className="case-card-title">{c.title}</h4>
                    <p className="case-card-number">شماره: <span dir="ltr">{c.case_number}</span></p>
                  </div>
                  <span className="case-card-court">{c.court}</span>
                </div>
              </div>
            ))
          ) : (
            <p className="empty-text-small">پرونده‌ای ثبت نشده است.</p>
          )}
        </div>

                <h3 className="section-title-black">افراد مرتبط</h3>
        <div className="people-tags">
          {(() => {
            // جمع‌آوری افراد از همه پرونده‌های این داستان
            const allPeople = selectedStory.cases?.flatMap(c => c.people || []) || [];
            const uniquePeople = [];
            const rolesSeen = new Set();

            // فیلتر کردن تا فقط یک نفر از هر نقش (خواهان/خوانده) نشون داده بشه
            allPeople.forEach(p => {
              if (!rolesSeen.has(p.role)) {
                rolesSeen.add(p.role);
                uniquePeople.push(p);
              }
            });

            return uniquePeople.length > 0 ? (
              uniquePeople.map((person, idx) => (
                <div key={idx} className="person-tag-white">
                  {person.name} {/* ⬅️ فقط اسم، بدون پرانتز و نقش */}
                </div>
              ))
            ) : (
              <p className="empty-text-small">فردی ثبت نشده است.</p>
            );
          })()}
        </div>
      </div>
    );
  }

    // -----------------------------------------
  // ۳. صفحه جزئیات پرونده (Case)
  // -----------------------------------------
  if (activeScreen === "case" && selectedCase) {
    return (
      <div className="case-detail-page">
        <div className="detail-header">
          <button className="back-circle-btn" onClick={handleBack}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
          </button>
          <h1 className="detail-title-black">جزئیات پرونده</h1>
        </div>

        {/* ⬇️ کارت خلاصه پرونده (جایگزین کارت مشخصات قبلی) ⬇️ */}
        <div className="white-card">
          <h2 className="card-title-blue">خلاصه پرونده</h2>
          <p className="summary-text">
            {selectedCase.summary || "خلاصه‌ای برای این پرونده ثبت نشده است."}
          </p>
        </div>

        {/* مراحل پرونده (لیست اسناد) - دقیقاً مثل قبل */}
        <h3 className="section-title-black">مراحل پرونده</h3>
        <div className="documents-timeline-list">
          {selectedCase.documents && selectedCase.documents.length > 0 ? (
            selectedCase.documents.map((doc, index) => (
              <div key={doc.id} className="timeline-item">
                
                {/* ستون تایم‌لاین سمت راست (دایره و خط) */}
                <div className="timeline-graphic">
                  <div className="timeline-dot"></div>
                  {index !== selectedCase.documents.length - 1 && (
                    <div className="timeline-line"></div>
                  )}
                </div>

                {/* کارت سند */}
                <div 
                  className="white-card doc-step-card"
                  onClick={() => {
                    setSelectedDocument(doc);
                    setActiveScreen("document");
                  }}
                >
                  {/* متن‌ها سمت راست */}
                  <div className="doc-step-content">
                    <h4 className="doc-step-title">{doc.filename}</h4>
                    <p className="doc-step-date">
                      تاریخ: {new Date(doc.date).toLocaleDateString('fa-IR')}
                    </p>
                  </div>
                  
                  {/* فلش آبی سمت چپ */}
                  <div className="doc-step-arrow-wrapper">
                    <svg 
                      className="doc-step-arrow" 
                      xmlns="http://www.w3.org/2000/svg" 
                      width="18" height="18" 
                      viewBox="0 0 24 24" 
                      fill="none" 
                      stroke="currentColor" 
                      strokeWidth="2.5" 
                      strokeLinecap="round" 
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <polyline points="15 18 9 12 15 6" />
                    </svg>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <p className="empty-text-small">سندی برای این پرونده ثبت نشده است.</p>
          )}
        </div>
      </div>
    );
  }

      

  // -----------------------------------------
  // ۴. صفحه جزئیات سند (Document) - اصلاح شده
  // -----------------------------------------
  if (activeScreen === "document" && selectedDocument) {
    // استخراج نوع سند از فکت‌ها (اگر وجود نداشت، پیش‌فرض می‌گذاریم)
    const docType = selectedDocument.facts?.case_type || selectedDocument.facts?.document_type || "سند";
    
    // آدرس پیش‌فرض برای نمایش فایل (باید در بک‌اند یک Route برای دانلود/proxy فایل سند داشته باشیم)
    // اگر Paperless داره، معمولاً از طریق API خودش با آیدی نمایش داده میشه
    const documentPreviewUrl = `http://127.0.0.1:8001/api/paperless/document/${selectedDocument.paperless_id}/preview/?token=${authToken}`;

    return (
      <div className="document-detail-page">
        {/* هدر اختصاصی سند: عنوان راست، دکمه بستن چپ */}
        <div className="detail-header doc-header">
          <h1 className="detail-title-black doc-title-right">{selectedDocument.filename}</h1>
          <button className="close-circle-btn" onClick={handleCloseAll} title="بستن">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        
        {/* زیرعنوان: نوع سند و تاریخ */}
        <div className="doc-meta-row">
          <span className="doc-type">نوع سند: {docType}</span>
          <span className="doc-date-text"> {new Date(selectedDocument.date).toLocaleDateString('fa-IR')}</span>
        </div>
        
        {/* نمایش اطلاعات استخراج‌شده (فکت‌ها) */}
        {selectedDocument.facts && Object.keys(selectedDocument.facts).length > 0 && (
          <div className="white-card" style={{ marginBottom: "16px" }}>
            <h3 className="section-title-black-small" style={{ marginTop: 0 }}>اطلاعات کلیدی</h3>
            <div className="facts-grid">
              {selectedDocument.facts.judgment_number && (
                <div className="fact-row">
                  <span className="fact-label">شماره دادنامه:</span>
                  <span className="fact-value" dir="ltr">{selectedDocument.facts.judgment_number}</span>
                </div>
              )}
              {selectedDocument.facts.case_number && (
                <div className="fact-row">
                  <span className="fact-label">شماره پرونده:</span>
                  <span className="fact-value" dir="ltr">{selectedDocument.facts.case_number}</span>
                </div>
              )}
            </div>
          </div>
        )}

        <h3 className="section-title-black-small">خلاصه هوشمند</h3>
        <div className="ai-summary-box">
          <p>{selectedDocument.summary || "خلاصه‌ای ثبت نشده است."}</p>
        </div>

        <h3 className="section-title-black-small" style={{ marginTop: "0px" }}>اصل سند</h3>
        
        
        {/* نمایش اصل سند به شکل باکس خط‌چین */}
        {selectedDocument.paperless_id ? (
          <a 
            href={documentPreviewUrl} 
            target="_blank" 
            rel="noreferrer"
            className="document-scan-box"
          >
            <svg 
              xmlns="http://www.w3.org/2000/svg" 
              width="56" height="56" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="#9ca3af" 
              strokeWidth="1.5" 
              strokeLinecap="round" 
              strokeLinejoin="round"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <span>برای مشاهده نسخه اصلی اسکن شده کلیک کنید</span>
          </a>
        ) : (
          <div className="document-scan-box">
            <p style={{ textAlign: "center", color: "#9ca3af", fontSize: "0.85rem", margin: 0 }}>
              فایلی برای نمایش موجود نیست.
            </p>
          </div>
        )}
      </div>
    );
  }

  return null;
}

export default CasesScreen;
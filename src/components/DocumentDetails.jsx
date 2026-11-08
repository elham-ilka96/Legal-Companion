import "./DocumentDetails.css";

function DocumentDetails({ documents = [] }) {
  return (
    <div className="legal-story-page">
      {documents.map((document, index) => {
        const summary = document.extractedData?.summary || "خلاصه‌ای برای این سند یافت نشد.";
        const defendantName = "حامد بیگی";

        return (
          <div key={document.id || index} className="legal-story-container">
            
            {/* هدر وسط‌چین در بالای کادر سفید */}
            <div className="story-header-center">
              <h1 className="story-title-center">طلاق از {defendantName}</h1>
              <span className="story-status-badge-center">در جریان</span>
            </div>

            {/* بخش‌های داخل کادر سفید */}
            <section className="story-card summary-card">
              <h2 className="story-card-title">خلاصه داستان</h2>
              <p className="story-card-text">{summary}</p>
            </section>

            <section className="related-cases-section">
              <h2 className="section-title">پرونده‌های مرتبط</h2>
              <div className="story-card case-item-card">
                <div className="case-item-header">
                  <h3 className="case-item-title">پرونده حقوقی طلاق</h3>
                  <span className="case-status-badge">فعال</span>
                </div>
                <p className="case-number">شماره پرونده: <span dir="ltr">۱۴۰۵/۲۵/۰۱۲۳</span></p>
                <p className="case-branch">شعبه ۲۵ خانواده</p>
              </div>
              <div className="story-card case-item-card">
                <div className="case-item-header">
                  <h3 className="case-item-title">پرونده مهریه</h3>
                  <span className="case-status-badge">فعال</span>
                </div>
                <p className="case-number">شماره پرونده: <span dir="ltr">۱۴۰۵/۲۵/۰۱۲۴</span></p>
                <p className="case-branch">شعبه ۲۵ خانواده</p>
              </div>
            </section>

            <section className="related-people-section">
              <h2 className="section-title">افراد مرتبط</h2>
              <div className="people-tags-container">
                <span className="person-tag">حامد بیگی (خوانده)</span>
                <span className="person-tag">سارا بهرامی (وکیل)</span>
              </div>
            </section>
          </div>
        );
      })}
    </div>
  );
}

export default DocumentDetails;
import React, { useState } from "react";
import "./ConfirmCategorizationScreen.css";

function ConfirmCategorizationScreen({ results, onConfirm, onCancel }) {
  // استیت برای نگهداری لیست نتایج (تا بتونیم تغییرات رو روش اعمال کنیم)
  const [documents, setDocuments] = useState(results || []);
  
  // استیت برای مودال ویرایش
  const [editingDocIndex, setEditingDocIndex] = useState(null);
  const [editField, setEditField] = useState(""); // "story" یا "case"
  const [editValue, setEditValue] = useState(""); // برای عنوان
  const [editSummary, setEditSummary] = useState(""); // برای خلاصه
  const [editCaseNumber, setEditCaseNumber] = useState(""); // ⬅️ جدید: برای شماره پرونده

  const handleOpenEdit = (index, field, currentValue, currentSummary, currentCaseNumber = "") => {
    setEditingDocIndex(index);
    setEditField(field);
    setEditValue(currentValue || "");
    setEditSummary(currentSummary || "");   
    setEditCaseNumber(currentCaseNumber || ""); // ⬅️ تنظیم شماره پرونده
  };

  const handleSaveEdit = () => {
    if (editingDocIndex !== null) {
      const updatedDocs = [...documents];
      
      if (editField === "story") {
        updatedDocs[editingDocIndex].main_topic = editValue;
        updatedDocs[editingDocIndex].story_summary = editSummary;
      } else if (editField === "case") {
        // ⬇️ اینجا تفکیک کردیم: اسم پرونده از شماره پرونده جدا شد ⬇️
        updatedDocs[editingDocIndex].case_title = editValue;
        updatedDocs[editingDocIndex].case_number = editCaseNumber;
        updatedDocs[editingDocIndex].case_summary = editSummary;
      }
      
      setDocuments(updatedDocs);
      setEditingDocIndex(null);
    }
  };

  return (
    <div className="confirm-page">
      <div className="confirm-container">
        
        {/* هدر صفحه */}
        <h1 className="confirm-title">تأیید دسته‌بندی اسناد</h1>

        {/* کادر آبی کم‌رنگ راهنما */}
        <div className="confirm-info-box">
          <h3>دسته‌بندی‌ها را بررسی کنید</h3>
          <p>پیش از نهایی کردن، نوع سند و پرونده‌های پیشنهادی را تأیید کنید.</p>
        </div>

        {/* لیست اسناد */}
        <div className="confirm-list">
          {documents.map((doc, index) => (
            <div key={index} className="confirm-card">
              
              {/* بخش بالایی: دایره، اسم سند، آیکون */}
              <div className="confirm-card-header">
                <div className="header-right">
                  <div className="success-circle">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                  </div>
                  <span className="doc-name">{doc.document_type || "دادنامه"} - {doc.filename}</span>
                </div>
                <div className="header-left">
                  <div className="doc-icon-square">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                      <polyline points="14 2 14 8 20 8"></polyline>
                      <line x1="16" y1="13" x2="8" y2="13"></line>
                      <line x1="16" y1="17" x2="8" y2="17"></line>
                    </svg>
                  </div>
                </div>
              </div>

              {/* خط جداکننده */}
              <hr className="divider" />

              {/* ردیف داستان حقوقی */}
              <div className="confirm-edit-row">
                <button className="change-btn" onClick={() => handleOpenEdit(index, "story", doc.main_topic, doc.story_summary || doc.summary)}>
                  تغییر
                </button>
                <span className="edit-label">داستان حقوقی</span>
                <p className="edit-value">{doc.main_topic || "نامشخص"}</p>
              </div>

              {/* ردیف پرونده */}
              <div className="confirm-edit-row">
                {/* ⬇️ در دکمه تغییر، اسم پرونده (case_title) و شماره پرونده (case_number) رو جدا پاس می‌دیم ⬇️ */}
                <button className="change-btn" onClick={() => handleOpenEdit(index, "case", doc.case_title, doc.case_summary || doc.summary, doc.case_number)}>
                  تغییر
                </button>
                <span className="edit-label">پرونده</span>
                <p className="edit-value" style={{ border: "1px solid #e5eaf0", padding: "4px 8px", borderRadius: "6px", width: "100%" }}>
                  {doc.case_title || "نامشخص"}
                </p>
                <p className="edit-subvalue" dir="ltr">شماره پرونده: {doc.case_number || "نامشخص"}</p>
              </div>

              {/* کادر پایینی تاریخ و شعبه */}
              <div className="confirm-footer-box">
                تاریخ: {doc.date} - {doc.court}
              </div>

            </div>
          ))}
        </div>

        {/* دکمه‌های پایین صفحه */}
        <div className="confirm-actions">
          <button className="confirm-btn" onClick={() => onConfirm(documents)}>
            تأیید و نهایی کردن
          </button>
          <button className="back-link-btn" onClick={onCancel}>
            بازگشت و اصلاح
          </button>
        </div>

      </div>

      {/* مودال ویرایش */}
      {editingDocIndex !== null && (
        <div className="edit-modal-backdrop" onClick={() => setEditingDocIndex(null)}>
          <div className="edit-modal" onClick={(e) => e.stopPropagation()}>
            <h3>ویرایش {editField === "story" ? "داستان حقوقی" : "پرونده"}</h3>
            
            {/* دیو اول: عنوان */}
            <div className="modal-section-box">
              <h4 className="modal-section-title">{editField === "story" ? "عنوان داستان" : "عنوان پرونده"}</h4>
              <input 
                type="text" 
                value={editValue} 
                onChange={(e) => setEditValue(e.target.value)} 
                className="edit-input"
                placeholder={editField === "story" ? "عنوان داستان..." : "عنوان پرونده..."}
              />
            </div>

            {/* ⬇️ دیو جدید: فقط برای شماره پرونده (اگر روی پرونده کلیک شده باشد) ⬇️ */}
            {editField === "case" && (
              <div className="modal-section-box">
                <h4 className="modal-section-title">شماره پرونده</h4>
                <input 
                  type="text" 
                  value={editCaseNumber} 
                  onChange={(e) => setEditCaseNumber(e.target.value)} 
                  className="edit-input"
                  placeholder="مثلاً 1402001234567"
                  dir="ltr"
                />
              </div>
            )}

            {/* دیو خلاصه */}
            <div className="modal-section-box">
              <h4 className="modal-section-title">
                خلاصه {editField === "story" ? "داستان" : "پرونده"}
              </h4>
              <textarea 
                value={editSummary} 
                onChange={(e) => setEditSummary(e.target.value)} 
                className="edit-textarea"
                rows={5}
                placeholder="خلاصه را اینجا ویرایش کنید..."
              />
            </div>

            <div className="modal-actions">
              <button className="save-btn" onClick={handleSaveEdit}>ذخیره تغییرات</button>
              <button className="close-btn" onClick={() => setEditingDocIndex(null)}>انصراف</button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default ConfirmCategorizationScreen;
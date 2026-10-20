import "./DocumentDetails.css";

const detailFields = [
  { key: "caseDate", label: "شماره پرونده", aliases: ["شماره پرونده", "تاریخ سند", "تاریخ تنظیم", "تاریخ"] },
  { key: "documentNumber", label: "شماره سند", aliases: ["شماره سند", "شماره پرونده", "شماره دادنامه", "شماره ابلاغیه", "شماره"] },
  { key: "defendant", label: "خوانده", aliases: ["خوانده", "محکوم علیه", "طرف خوانده"] },
  { key: "subject", label: "موضوع پرونده", aliases: ["موضوع پرونده", "موضوع", "خواسته"] },
];

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const findFieldValue = (text, aliases) => {
  const labels = aliases.map(escapeRegExp).join("|");
  const expression = new RegExp(
    `^\\s*(?:${labels})\\s*(?:[:：\\-–]\\s*)?(.*)$`,
    "im"
  );
  const match = text.match(expression);
  if (!match) return "";

  const valueOnLabelLine = match[1]?.trim();
  if (valueOnLabelLine) return valueOnLabelLine;

  const lines = text.slice(match.index + match[0].length).split(/\r?\n/);
  return lines.find((line) => line.trim())?.trim() || "";
};

const extractLegalDocumentDetails = (content = "") => {
  const text = String(content).replace(/\r\n/g, "\n");
  return Object.fromEntries(
    detailFields.map(({ key, aliases }) => [
      key,
      findFieldValue(text, aliases),
    ])
  );
};

function DocumentDetails({ documents = [] }) {
  return (
    <div className="document-details-list">
      {documents.map((document, index) => {
        const details = extractLegalDocumentDetails(document.ocrText);

        return (
          <section
            className="document-details-card"
            key={document.id || document.file?.name || index}
          >
            <h2 className="document-details-filename" dir="auto">
              {document.file?.name || `سند ${index + 1}`}
            </h2>
            <dl className="document-details-fields">
              {detailFields.map(({ key, label }) => (
                <div className="document-details-field" key={key}>
                  <dt>{label}</dt>
                  <dd>{details[key] || "در متن سند یافت نشد"}</dd>
                </div>
              ))}
            </dl>
          </section>
        );
      })}
    </div>
  );
}

export default DocumentDetails;

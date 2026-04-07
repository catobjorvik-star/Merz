import { useMemo, useState } from "react";
import { AlertTriangle, Download, Filter, Loader2, Upload, CheckCircle2, Maximize2 } from "lucide-react";

const API_BASE = "";

function Tag({ children, tone = "dark" }) {
  return <span className={`tag tag-${tone}`}>{children}</span>;
}

function FileDrop({ label, file, accept, onChange, icon }) {
  return (
    <label className={`dropzone ${file ? "has-file" : ""}`}>
      <input
        type="file"
        accept={accept}
        onChange={(event) => onChange(event.target.files?.[0] || null)}
      />
      <div className="dropzone-icon">{icon}</div>
      <div className="dropzone-text">
        <strong>{label}</strong>
        <span>{file ? file.name : "Datei wählen oder hier hineinziehen"}</span>
      </div>
    </label>
  );
}

function PreviewTable({ rows }) {
  return (
    <div className="table-wrap desktop-preview">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Geschoss</th>
            <th>Stk</th>
            <th>RBM Breite</th>
            <th>RBM Höhe</th>
            <th>Bestellbreite</th>
            <th>Bestellhöhe</th>
            <th>Beschreibung</th>
            <th>Typ</th>
            <th>Raum</th>
            <th>Lieferantentyp</th>
            <th>Preis</th>
            <th>Match</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={`${row.id}-${idx}`}>
              <td>{row.id}</td>
              <td>{row.floor || "—"}</td>
              <td>{row.qty}</td>
              <td>{row.width_mm} mm</td>
              <td>{row.height_mm} mm</td>
              <td>{row.order_width_mm ?? "—"} mm</td>
              <td>{row.order_height_mm ?? "—"} mm</td>
              <td className="desc-cell">{row.description || row.rohbau || "—"}</td>
              <td>{row.type || "—"}</td>
              <td>{[row.room_no, row.room_name].filter(Boolean).join(" | ") || "—"}</td>
              <td>{row.supplier_type || "—"}</td>
              <td>{row.supplier_price_eur != null ? `${row.supplier_price_eur.toFixed(2)} €` : "—"}</td>
              <td>{row.supplier_confidence || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MobilePreviewCards({ rows }) {
  return (
    <div className="mobile-preview-list">
      {rows.map((row, idx) => (
        <article className="mobile-row-card" key={`${row.id}-${idx}`}>
          <div className="mobile-row-top">
            <strong>{row.id}</strong>
            <span>{row.qty} Stk</span>
          </div>

          <div className="mobile-row-grid">
            <div>
              <label>RBM</label>
              <span>{row.width_mm} × {row.height_mm} mm</span>
            </div>
            <div>
              <label>Bestellmaß</label>
              <span>{row.order_width_mm ?? "—"} × {row.order_height_mm ?? "—"} mm</span>
            </div>
            <div>
              <label>Beschreibung</label>
              <span>{row.description || row.rohbau || "—"}</span>
            </div>
            <div>
              <label>Typ</label>
              <span>{row.type || "—"}</span>
            </div>
            <div>
              <label>Raum</label>
              <span>{[row.room_no, row.room_name].filter(Boolean).join(" | ") || "—"}</span>
            </div>
            <div>
              <label>Lieferant</label>
              <span>{row.supplier_type || "—"}</span>
            </div>
            <div>
              <label>Preis / Match</label>
              <span>
                {row.supplier_price_eur != null ? `${row.supplier_price_eur.toFixed(2)} €` : "—"} · {row.supplier_confidence || "—"}
              </span>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

export default function App() {
  const [pdfFile, setPdfFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [loadingImport, setLoadingImport] = useState(false);

  const canPreview = useMemo(() => Boolean(pdfFile), [pdfFile]);
  const canImport = useMemo(() => Boolean(pdfFile && preview?.rows?.length), [pdfFile, preview]);

  async function loadPreview() {
    if (!pdfFile) {
      setError("Bitte zuerst eine PDF-Fensterliste hochladen.");
      return;
    }

    setLoadingPreview(true);
    setStatus("PDF wird analysiert …");
    setError("");
    setPreview(null);

    const formData = new FormData();
    formData.append("pdf", pdfFile);

    try {
      const response = await fetch(`${API_BASE}/api/preview`, {
        method: "POST",
        body: formData,
      });

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail || "Vorschau konnte nicht erzeugt werden.");
      }

      setPreview(payload);
      setStatus(`Vorschau geladen: ${payload.count} Zeilen erkannt.`);
    } catch (err) {
      setError(err.message || "Unbekannter Fehler");
      setStatus("");
    } finally {
      setLoadingPreview(false);
    }
  }

  async function createExcel() {
    if (!pdfFile) {
      setError("Bitte zuerst eine PDF-Fensterliste hochladen.");
      return;
    }

    setLoadingImport(true);
    setStatus("Excel-Datei wird erzeugt …");
    setError("");

    const formData = new FormData();
    formData.append("pdf", pdfFile);

    try {
      const response = await fetch(`${API_BASE}/api/import`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload.detail || "Import fehlgeschlagen.");
      }

      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="([^"]+)"/);
      const filename = match?.[1] || "MERZ_Fensterimport.xlsx";

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      window.URL.revokeObjectURL(url);

      const warningCount = Number(response.headers.get("X-Import-Warnings") || "0");
      setStatus(`Fertig. Excel-Datei erzeugt.${warningCount ? ` Warnungen: ${warningCount}.` : ""}`);
    } catch (err) {
      setError(err.message || "Unbekannter Fehler");
      setStatus("");
    } finally {
      setLoadingImport(false);
    }
  }

  return (
    <div className="page-shell">
      <div className="hero-card">
        <div className="hero-topline">SCHREINEREI MERZ · FENSTERIMPORT</div>
        <div className="hero-main">
          <div className="hero-copy">
            <img src="/merz-logo.svg" alt="Schreinerei Merz" className="hero-logo" />
            <h1 className="hero-title-single">PDF-EXCEL IMPORT</h1>
            <div className="hero-developed">ENTWICKELT VON CBJORVIK</div>
            <div className="hero-tags">
              <Tag>Nur PDF hochladen</Tag>
              <Tag tone="red">Bestellmaß automatisch</Tag>
              <Tag>MERZ-Logik v1</Tag>
            </div>
          </div>

          <div className="hero-panel">
            <div className="mini-stat">
              <span>WORKFLOW</span>
              <strong>PDF hochladen, prüfen, Excel erzeugen</strong>
            </div>
            <div className="mini-stat">
              <span>LOGIK</span>
              <strong>RBM bleibt erhalten, Bestellmaß wird automatisch mit −30 mm berechnet</strong>
            </div>
            <div className="mini-stat">
              <span>LAYOUT</span>
              <strong className="wide-note"><Maximize2 size={16} /> Mehr Breite, weniger tote Fläche, größere Vorschau</strong>
            </div>
          </div>
        </div>
      </div>

      <section className="panel upload-panel">
        <div className="panel-header">
          <h2>Dateien</h2>
          <p>Bitte nur die Architekten-PDF hochladen. Die MERZ-Vorlage wird automatisch verwendet.</p>
        </div>

        <div className="stack">
          <FileDrop
            label="Architekten-PDF"
            file={pdfFile}
            accept=".pdf,application/pdf"
            onChange={setPdfFile}
            icon={<Upload size={22} />}
          />
        </div>

        <div className="action-row compact-actions desktop-actions">
          <button className="primary-btn" onClick={loadPreview} disabled={!canPreview || loadingPreview}>
            {loadingPreview ? <Loader2 className="spin" size={18} /> : <Filter size={18} />}
            Vorschau laden
          </button>

          <button className="secondary-btn" onClick={createExcel} disabled={!canImport || loadingImport}>
            {loadingImport ? <Loader2 className="spin" size={18} /> : <Download size={18} />}
            Excel erzeugen
          </button>
        </div>
      </section>

      {(status || error) && (
        <section className="feedback-row">
          {status && (
            <div className="status ok">
              <CheckCircle2 size={18} />
              <span>{status}</span>
            </div>
          )}

          {error && (
            <div className="status error">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
          )}
        </section>
      )}

      <section className="panel large-panel preview-panel">
        <div className="panel-header">
          <h2>Import-Vorschau</h2>
          <p>Zeigt die erkannten Fensterzeilen inklusive RBM, Bestellmaß und MERZ-Beschreibung vor dem finalen Excel-Export.</p>
        </div>

        {preview?.rows?.length ? (
          <div className="preview-block">
            {!!preview?.warnings?.length && (
              <div className="warning-list">
                {preview.warnings.map((warning, idx) => (
                  <div className="warning-item" key={idx}>
                    <AlertTriangle size={16} />
                    <span>{warning}</span>
                  </div>
                ))}
              </div>
            )}

            <PreviewTable rows={preview.rows} />
            <MobilePreviewCards rows={preview.rows} />
          </div>
        ) : (
          <div className="empty-state">
            Vorschau wird hier angezeigt, sobald eine PDF geladen und analysiert wurde.
          </div>
        )}
      </section>

      <div className="mobile-action-bar">
        <button className="primary-btn mobile-btn" onClick={loadPreview} disabled={!canPreview || loadingPreview}>
          {loadingPreview ? <Loader2 className="spin" size={18} /> : <Filter size={18} />}
          Vorschau
        </button>

        <button className="secondary-btn mobile-btn" onClick={createExcel} disabled={!canImport || loadingImport}>
          {loadingImport ? <Loader2 className="spin" size={18} /> : <Download size={18} />}
          Excel
        </button>
      </div>
    </div>
  );
}

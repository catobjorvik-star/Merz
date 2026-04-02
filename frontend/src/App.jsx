import { useMemo, useState } from "react";
import { AlertTriangle, Download, FileSpreadsheet, FileUp, Filter, Loader2, Upload, CheckCircle2 } from "lucide-react";

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
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Haus</th>
            <th>Geschoss</th>
            <th>Menge</th>
            <th>Breite</th>
            <th>Höhe</th>
            <th>Rohbauöffnung</th>
            <th>Typ</th>
            <th>Raum</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={`${row.id}-${idx}`}>
              <td>{row.id}</td>
              <td>{row.house}</td>
              <td>{row.floor || "—"}</td>
              <td>{row.qty}</td>
              <td>{row.width_mm} mm</td>
              <td>{row.height_mm} mm</td>
              <td>{row.rohbau}</td>
              <td>{row.type}</td>
              <td>{[row.room_no, row.room_name].filter(Boolean).join(" | ") || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [pdfFile, setPdfFile] = useState(null);
  const [templateFile, setTemplateFile] = useState(null);
  const [houseMode, setHouseMode] = useState("BOTH");
  const [aggregate, setAggregate] = useState(false);
  const [preview, setPreview] = useState(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [loadingImport, setLoadingImport] = useState(false);

  const canPreview = useMemo(() => Boolean(pdfFile), [pdfFile]);
  const canImport = useMemo(() => Boolean(pdfFile && templateFile && preview?.rows?.length), [pdfFile, templateFile, preview]);

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
    formData.append("house_mode", houseMode);
    formData.append("aggregate", String(aggregate));

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
    if (!pdfFile || !templateFile) {
      setError("Bitte PDF und Excel-Vorlage hochladen.");
      return;
    }
    setLoadingImport(true);
    setStatus("Excel-Datei wird erzeugt …");
    setError("");

    const formData = new FormData();
    formData.append("pdf", pdfFile);
    formData.append("template", templateFile);
    formData.append("house_mode", houseMode);
    formData.append("aggregate", String(aggregate));

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
            <h1>PDF-Fensterlisten sicher in die Kalkulationsvorlage übernehmen</h1>
            <p>
              Browser-Oberfläche mit serverseitiger Verarbeitung. Vorschau zuerst,
              danach kontrollierter Excel-Export in die MERZ-Vorlage.
            </p>
            <div className="hero-tags">
              <Tag>Haus A / Haus B / Beide</Tag>
              <Tag tone="red">Aggregierung optional</Tag>
              <Tag>Importbericht inklusive</Tag>
            </div>
          </div>
          <div className="hero-panel">
            <div className="mini-stat">
              <span>Workflow</span>
              <strong>Upload → Vorschau → Import → Download</strong>
            </div>
            <div className="mini-stat">
              <span>Backend</span>
              <strong>FastAPI + Python</strong>
            </div>
            <div className="mini-stat">
              <span>Frontend</span>
              <strong>React</strong>
            </div>
          </div>
        </div>
      </div>

      <div className="content-grid">
        <section className="panel">
          <div className="panel-header">
            <h2>Dateien</h2>
            <p>Bitte zuerst PDF und danach die passende Excel-Vorlage hochladen.</p>
          </div>

          <div className="stack">
            <FileDrop
              label="Architekten-PDF"
              file={pdfFile}
              accept=".pdf,application/pdf"
              onChange={setPdfFile}
              icon={<Upload size={22} />}
            />
            <FileDrop
              label="Excel-Vorlage"
              file={templateFile}
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={setTemplateFile}
              icon={<FileSpreadsheet size={22} />}
            />
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Optionen</h2>
            <p>Filter und Modus vor der Vorschau festlegen.</p>
          </div>

          <div className="control-grid">
            <label className="field">
              <span>Haus</span>
              <div className="segmented">
                <button type="button" className={houseMode === "A" ? "active" : ""} onClick={() => setHouseMode("A")}>Haus A</button>
                <button type="button" className={houseMode === "B" ? "active" : ""} onClick={() => setHouseMode("B")}>Haus B</button>
                <button type="button" className={houseMode === "BOTH" ? "active" : ""} onClick={() => setHouseMode("BOTH")}>Beide</button>
              </div>
            </label>

            <label className="checkbox-line">
              <input
                type="checkbox"
                checked={aggregate}
                onChange={(event) => setAggregate(event.target.checked)}
              />
              <span>Aggregiert nach Breite × Höhe und Typ</span>
            </label>
          </div>

          <div className="action-row">
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
      </div>

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

      <section className="panel large-panel">
        <div className="panel-header">
          <h2>Import-Vorschau</h2>
          <p>
            Erst prüfen, dann importieren. Der Export schreibt anschließend in die
            hochgeladene Excel-Vorlage zurück.
          </p>
        </div>

        {!preview ? (
          <div className="empty-state">
            <FileUp size={28} />
            <strong>Noch keine Vorschau geladen</strong>
            <span>Nach dem PDF-Upload auf „Vorschau laden“ klicken.</span>
          </div>
        ) : (
          <>
            <div className="summary-row">
              <div className="summary-pill">
                <span>Erkannte Zeilen</span>
                <strong>{preview.count}</strong>
              </div>
              <div className="summary-pill">
                <span>Warnungen</span>
                <strong>{preview.warnings.length}</strong>
              </div>
              <div className="summary-pill">
                <span>Modus</span>
                <strong>{houseMode === "BOTH" ? "Beide Häuser" : `Haus ${houseMode}`}</strong>
              </div>
            </div>

            {preview.warnings.length > 0 && (
              <div className="warning-box">
                <div className="warning-head">
                  <AlertTriangle size={18} />
                  <strong>Hinweise vor dem Import</strong>
                </div>
                <ul>
                  {preview.warnings.map((warning, idx) => (
                    <li key={`${warning}-${idx}`}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}

            <PreviewTable rows={preview.rows} />
          </>
        )}
      </section>
    </div>
  );
}

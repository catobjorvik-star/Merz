
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Download,
  FileSpreadsheet,
  Filter,
  FolderOpen,
  Home,
  LayoutGrid,
  Loader2,
  Menu,
  Search,
  Settings,
  Sparkles,
  Upload,
} from "lucide-react";

const API_BASE = "";

function SidebarButton({ icon, label, active, onClick }) {
  return (
    <button type="button" className={`sidebar-btn ${active ? "active" : ""}`} onClick={onClick}>
      {icon}
      <span>{label}</span>
    </button>
  );
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
            <th>Lieferantentyp</th>
            <th>Preis</th>
            <th>Glasfläche</th>
            <th>Match</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={`${row.id}-${idx}`}>
              <td>{row.id}</td>
              <td>{row.house || "—"}</td>
              <td>{row.floor || "—"}</td>
              <td>{row.qty}</td>
              <td>{row.width_mm} mm</td>
              <td>{row.height_mm} mm</td>
              <td>{row.rohbau || "—"}</td>
              <td>{row.type || "—"}</td>
              <td>{[row.room_no, row.room_name].filter(Boolean).join(" | ") || "—"}</td>
              <td>{row.supplier_type || "—"}</td>
              <td>{row.supplier_price_eur != null ? `${row.supplier_price_eur.toFixed(2)} €` : "—"}</td>
              <td>{row.glass_area_index_m2 != null ? `${row.glass_area_index_m2.toFixed(2)} m²` : "—"}</td>
              <td>{row.supplier_confidence || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CatalogueCard({ item, active, onSelect, onQueue }) {
  return (
    <article className={`catalogue-card ${active ? "active" : ""}`} onClick={() => onSelect(item)}>
      <div className="catalogue-head">
        <span className="code-badge">{item.code}</span>
        <span className="page-range">{item.page_range}</span>
      </div>
      <h3>{item.title}</h3>
      <p>{item.description}</p>
      <div className="catalogue-foot">
        <span>{item.category}</span>
        <button type="button" className="ghost-btn accent" onClick={(e) => { e.stopPropagation(); onQueue(item); }}>
          Merken
        </button>
      </div>
    </article>
  );
}

function DetailView({ item, page92Demo, onQueue }) {
  const [dimension, setDimension] = useState("");
  const [variant, setVariant] = useState("");
  const [extras, setExtras] = useState([]);

  useEffect(() => {
    const dims = Object.keys(page92Demo || {});
    if (dims.length && !dimension) setDimension(dims[0]);
  }, [page92Demo, dimension]);

  useEffect(() => {
    if (!dimension || !page92Demo?.[dimension]) return;
    const variants = Object.keys(page92Demo[dimension].base || {});
    if (variants.length && !variant) setVariant(variants[0]);
    setExtras([]);
  }, [dimension, page92Demo, variant]);

  const total = useMemo(() => {
    if (!dimension || !variant || !page92Demo?.[dimension]) return null;
    let sum = page92Demo[dimension].base?.[variant] || 0;
    for (const ex of extras) {
      sum += page92Demo[dimension].extras?.[ex] || 0;
    }
    return sum;
  }, [dimension, variant, extras, page92Demo]);

  if (!item) {
    return <div className="empty-state">Wähle links eine Produktfamilie aus.</div>;
  }

  return (
    <div className="detail-card">
      <div className="detail-kicker">Produktfamilie {item.code}</div>
      <h2>{item.title}</h2>
      <p>{item.description}</p>

      <div className="meta-grid">
        <div className="meta-box"><span>Kategorie</span><strong>{item.category}</strong></div>
        <div className="meta-box"><span>Blätter</span><strong>{item.page_range}</strong></div>
        <div className="meta-box"><span>Preiszeilen</span><strong>{item.pricing_row_count || 0}</strong></div>
      </div>

      {!!item.price_rows?.length && (
        <div className="detail-section">
          <h3>Preiszeilen aus dem Katalog</h3>
          <div className="mini-table">
            <table>
              <thead>
                <tr>
                  <th>Breite</th>
                  <th>Höhe</th>
                  <th>Index</th>
                  <th>Werte</th>
                </tr>
              </thead>
              <tbody>
                {item.price_rows.slice(0, 8).map((row, idx) => (
                  <tr key={idx}>
                    <td>{row.width_mm}</td>
                    <td>{row.height_mm}</td>
                    <td>{row.glass_area_index_m2 || "—"}</td>
                    <td>{row.raw_values.slice(0, 5).join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!!Object.keys(page92Demo || {}).length && (
        <div className="detail-section">
          <h3>Interaktive Preis-Matrix Demo</h3>
          <div className="matrix-grid">
            <div className="matrix-controls">
              <label>Rahmen Außenmaß</label>
              <select value={dimension} onChange={(e) => setDimension(e.target.value)}>
                {Object.keys(page92Demo).map((d) => <option key={d}>{d}</option>)}
              </select>

              <label>System / Material</label>
              <select value={variant} onChange={(e) => setVariant(e.target.value)}>
                {dimension && Object.keys(page92Demo[dimension]?.base || {}).map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>

              <label>Zubehör</label>
              <div className="extras-list">
                {dimension && Object.keys(page92Demo[dimension]?.extras || {}).slice(0, 6).map((name) => (
                  <label key={name} className="check-line">
                    <input
                      type="checkbox"
                      checked={extras.includes(name)}
                      onChange={(e) => {
                        setExtras((prev) => e.target.checked ? [...prev, name] : prev.filter((x) => x !== name));
                      }}
                    />
                    <span>{name}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="matrix-result">
              <div className="result-card">
                <span>Gesamtpreis</span>
                <strong>{total != null ? `${total}.00 €` : "—"}</strong>
                <p>
                  {dimension && page92Demo[dimension]?.index != null
                    ? `Glasflächen-Index: ${page92Demo[dimension].index} ca m²`
                    : "Kein Index"}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="detail-actions">
        <button type="button" className="primary-btn" onClick={() => onQueue(item)}>
          <Sparkles size={16} />
          In Workflow Queue
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const [module, setModule] = useState("import");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [pdfFile, setPdfFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [loadingImport, setLoadingImport] = useState(false);

  const [catalogue, setCatalogue] = useState({ families: [], page92_demo: {} });
  const [loadingCatalogue, setLoadingCatalogue] = useState(false);
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("Alle");
  const [queue, setQueue] = useState([]);

  const categories = useMemo(() => ["Alle", ...Array.from(new Set((catalogue.families || []).map((x) => x.category)))], [catalogue]);
  const canPreview = useMemo(() => Boolean(pdfFile), [pdfFile]);
  const canImport = useMemo(() => Boolean(pdfFile && preview?.rows?.length), [pdfFile, preview]);

  useEffect(() => {
    async function loadCatalogue() {
      setLoadingCatalogue(true);
      try {
        const res = await fetch(`${API_BASE}/api/catalogue`);
        if (!res.ok) throw new Error("Katalog konnte nicht geladen werden.");
        const data = await res.json();
        setCatalogue(data);
        if (data.families?.length) setSelected(data.families[0]);
      } catch (err) {
        setError(err.message || "Katalogfehler");
      } finally {
        setLoadingCatalogue(false);
      }
    }
    loadCatalogue();
  }, []);

  const filteredFamilies = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (catalogue.families || []).filter((item) => {
      const groupMatch = category === "Alle" || item.category === category;
      const hay = `${item.title} ${item.description} ${item.page_range} ${item.code}`.toLowerCase();
      return groupMatch && (!q || hay.includes(q));
    });
  }, [catalogue, search, category]);

  function addToQueue(item) {
    setQueue((prev) => prev.find((x) => x.code === item.code) ? prev : [...prev, item]);
    setStatus(`Zur Queue hinzugefügt: ${item.title}`);
    setError("");
  }

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
    formData.append("catalogue_queue", JSON.stringify(queue.map((x) => x.code)));

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
      setStatus("Excel-Datei erfolgreich erzeugt.");
    } catch (err) {
      setError(err.message || "Unbekannter Fehler");
      setStatus("");
    } finally {
      setLoadingImport(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-brand">
          <img src="/merz-logo.svg" alt="Schreinerei Merz" className="sidebar-logo" />
          <div>
            <span className="side-kicker">Schreinerei Merz</span>
            <strong>Fensterplattform</strong>
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-label">Module</div>
          <SidebarButton icon={<Home size={18} />} label="Import" active={module === "import"} onClick={() => setModule("import")} />
          <SidebarButton icon={<LayoutGrid size={18} />} label="Holz Katalog" active={module === "catalogue"} onClick={() => setModule("catalogue")} />
          <SidebarButton icon={<FileSpreadsheet size={18} />} label="Workflow Queue" active={module === "queue"} onClick={() => setModule("queue")} />
          <SidebarButton icon={<FolderOpen size={18} />} label="Projekte" active={false} onClick={() => {}} />
          <SidebarButton icon={<Settings size={18} />} label="Einstellungen" active={false} onClick={() => {}} />
        </div>
      </aside>

      <main className="main-area">
        <div className="topbar">
          <button className="menu-btn" type="button" onClick={() => setSidebarOpen((v) => !v)}>
            <Menu size={18} />
          </button>
          <div>
            <span className="topbar-kicker">MERZ Plattform</span>
            <strong>{module === "catalogue" ? "Holz Katalog" : module === "queue" ? "Workflow Queue" : "PDF-Excel Import"}</strong>
          </div>
        </div>

        <section className="hero-banner">
          <div className="hero-copy">
            <div className="hero-chip">SCHREINEREI MERZ · EIN SYSTEM</div>
            <h1>{module === "catalogue" ? "Holz-Katalog interaktiv" : "PDF-EXCEL IMPORT"}</h1>
            <p>
              Der vollständige Holz-Katalog sitzt jetzt im selben App-System wie der Import.
              Produktfamilien, Zusatzbereiche, Preiszeilen und Queue sind direkt verbunden.
            </p>
            <div className="hero-tags">
              <span>Klima Futur</span>
              <span>Garda Futur</span>
              <span>HST</span>
              <span>PSK</span>
              <span>Füllungen</span>
              <span>Zubehör</span>
            </div>
          </div>

          <div className="hero-metrics">
            <div className="metric-card"><span>Familien</span><strong>{catalogue.family_count || 0}</strong></div>
            <div className="metric-card"><span>Queue</span><strong>{queue.length}</strong></div>
            <div className="metric-card"><span>Status</span><strong>{loadingCatalogue ? "lädt…" : "bereit"}</strong></div>
          </div>
        </section>

        {module === "import" && (
          <>
            <section className="grid-two">
              <section className="panel">
                <div className="panel-header">
                  <h2>Fensterlisten-Import</h2>
                  <p>Architekten-PDF laden, Vorschau prüfen, Queue optional an den Export koppeln.</p>
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

                {(status || error) && (
                  <section className="feedback-row">
                    {status && <div className="status ok"><CheckCircle2 size={18} /><span>{status}</span></div>}
                    {error && <div className="status error"><AlertTriangle size={18} /><span>{error}</span></div>}
                  </section>
                )}
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>Queue-Anbindung</h2>
                  <p>Katalog-Auswahl wird hier gesammelt und kann später an Exportoptionen gekoppelt werden.</p>
                </div>

                <div className="queue-list">
                  {queue.length ? queue.map((item) => (
                    <div className="queue-item" key={item.code}>
                      <div>
                        <strong>{item.title}</strong>
                        <span>{item.category} · {item.page_range}</span>
                      </div>
                      <span className="code-badge">{item.code}</span>
                    </div>
                  )) : <div className="empty-mini">Noch keine Katalog-Auswahl in der Queue.</div>}
                </div>
              </section>
            </section>

            <section className="panel large-panel">
              <div className="panel-header">
                <h2>Import-Vorschau</h2>
                <p>Zeigt die erkannten Fensterzeilen vor dem finalen Excel-Export.</p>
              </div>
              {preview?.rows?.length ? <PreviewTable rows={preview.rows} /> : <div className="empty-state">Vorschau wird hier angezeigt, sobald eine PDF geladen und analysiert wurde.</div>}
            </section>
          </>
        )}

        {module === "catalogue" && (
          <section className="catalogue-layout">
            <section className="panel">
              <div className="panel-header">
                <h2>Holz-Katalog</h2>
                <p>Strukturiert nach realen Produktgruppen. Suchbar, filterbar, direkt mit Queue verbunden.</p>
              </div>

              <div className="toolbar">
                <div className="search-box">
                  <Search size={16} />
                  <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Suche nach Familie, Code, Blatt …" />
                </div>
                <select value={category} onChange={(e) => setCategory(e.target.value)}>
                  {categories.map((cat) => <option key={cat}>{cat}</option>)}
                </select>
              </div>

              <div className="catalogue-grid">
                {filteredFamilies.map((item) => (
                  <CatalogueCard key={item.code} item={item} active={selected?.code === item.code} onSelect={setSelected} onQueue={addToQueue} />
                ))}
              </div>
            </section>

            <DetailView item={selected} page92Demo={catalogue.page92_demo || {}} onQueue={addToQueue} />
          </section>
        )}

        {module === "queue" && (
          <section className="panel">
            <div className="panel-header">
              <h2>Workflow Queue</h2>
              <p>Vorgemerkte Katalogfamilien für spätere Kopplung an Exportoptionen und Materialwahl.</p>
            </div>

            <div className="queue-board">
              {queue.length ? queue.map((item) => (
                <div className="queue-board-card" key={item.code}>
                  <span className="code-badge">{item.code}</span>
                  <h3>{item.title}</h3>
                  <p>{item.workflow_hint}</p>
                  <div className="foot-note">{item.page_range} · {item.category}</div>
                </div>
              )) : <div className="empty-state">Noch keine Queue-Einträge vorhanden.</div>}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}


import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Filter,
  FolderOpen,
  Home,
  LayoutGrid,
  Loader2,
  Menu,
  Plus,
  Search,
  Settings,
  Sparkles,
  Upload,
  X,
} from "lucide-react";

const API_BASE = "";
const PROJECT_FOLDERS = ["Fensterlisten", "Pläne", "Angebote", "Exports"];

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

function ProjectModal({ open, onClose, onCreate }) {
  const [form, setForm] = useState({ name: "", number: "", client: "", location: "", notes: "" });
  if (!open) return null;

  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <div className="modal-head">
          <div>
            <div className="detail-kicker">Neues Projekt</div>
            <h2>Projekt anlegen</h2>
          </div>
          <button type="button" className="icon-btn" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="form-grid">
          <input placeholder="Projektname" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input placeholder="Projektnummer" value={form.number} onChange={(e) => setForm({ ...form, number: e.target.value })} />
          <input placeholder="Kunde (optional)" value={form.client} onChange={(e) => setForm({ ...form, client: e.target.value })} />
          <input placeholder="Ort (optional)" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
          <textarea placeholder="Notizen (optional)" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>

        <div className="action-row">
          <button type="button" className="primary-btn" onClick={() => onCreate(form)}>Projekt speichern</button>
          <button type="button" className="secondary-btn" onClick={onClose}>Abbrechen</button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [module, setModule] = useState("projects");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [projectDetail, setProjectDetail] = useState(null);
  const [projectModalOpen, setProjectModalOpen] = useState(false);

  const [pdfFile, setPdfFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [loadingImport, setLoadingImport] = useState(false);

  const [catalogue, setCatalogue] = useState({ families: [] });
  const [selectedFamily, setSelectedFamily] = useState(null);
  const [catalogueSearch, setCatalogueSearch] = useState("");
  const [catalogueCategory, setCatalogueCategory] = useState("Alle");
  const [queue, setQueue] = useState([]);

  const categories = useMemo(() => ["Alle", ...Array.from(new Set((catalogue.families || []).map((x) => x.category)))], [catalogue]);
  const filteredFamilies = useMemo(() => {
    const q = catalogueSearch.trim().toLowerCase();
    return (catalogue.families || []).filter((item) => {
      const groupMatch = catalogueCategory === "Alle" || item.category === catalogueCategory;
      const hay = `${item.title} ${item.description} ${item.page_range} ${item.code}`.toLowerCase();
      return groupMatch && (!q || hay.includes(q));
    });
  }, [catalogue, catalogueSearch, catalogueCategory]);

  useEffect(() => {
    loadProjects();
    loadCatalogue();
  }, []);

  useEffect(() => {
    if (selectedProjectId) loadProjectDetail(selectedProjectId);
  }, [selectedProjectId]);

  async function loadProjects() {
    const res = await fetch(`${API_BASE}/api/projects`);
    if (!res.ok) return;
    const data = await res.json();
    setProjects(data.projects || []);
    if (!selectedProjectId && data.projects?.length) {
      setSelectedProjectId(data.projects[0].id);
    }
  }

  async function loadProjectDetail(projectId) {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}`);
    if (!res.ok) return;
    const data = await res.json();
    setProjectDetail(data);
  }

  async function loadCatalogue() {
    try {
      const res = await fetch(`${API_BASE}/api/catalogue`);
      if (!res.ok) throw new Error("Katalog konnte nicht geladen werden.");
      const data = await res.json();
      setCatalogue(data);
      if (data.families?.length) setSelectedFamily(data.families[0]);
    } catch (err) {
      setError(err.message || "Katalogfehler");
    }
  }

  async function createProject(form) {
    try {
      const res = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Projekt konnte nicht erstellt werden.");
      setProjectModalOpen(false);
      setStatus(`Projekt erstellt: ${data.number} ${data.name}`);
      setSelectedProjectId(data.id);
      await loadProjects();
      await loadProjectDetail(data.id);
    } catch (err) {
      setError(err.message || "Projektfehler");
    }
  }

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
    if (selectedProjectId) formData.append("project_id", selectedProjectId);

    try {
      const response = await fetch(`${API_BASE}/api/preview`, { method: "POST", body: formData });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Vorschau konnte nicht erzeugt werden.");
      setPreview(payload);
      setStatus(`Vorschau geladen: ${payload.count} Zeilen erkannt.`);
      if (selectedProjectId) await loadProjectDetail(selectedProjectId);
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
    if (selectedProjectId) formData.append("project_id", selectedProjectId);

    try {
      const response = await fetch(`${API_BASE}/api/import`, { method: "POST", body: formData });
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload.detail || "Import fehlgeschlagen.");
      }
      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="([^"]+)"/);
      const filename = match?.[1] || "MERZ_Fensterimport_export.xlsx";
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      window.URL.revokeObjectURL(url);
      setStatus("Excel-Datei erfolgreich erzeugt.");
      if (selectedProjectId) await loadProjectDetail(selectedProjectId);
    } catch (err) {
      setError(err.message || "Unbekannter Fehler");
      setStatus("");
    } finally {
      setLoadingImport(false);
    }
  }

  return (
    <div className="app-shell">
      <ProjectModal open={projectModalOpen} onClose={() => setProjectModalOpen(false)} onCreate={createProject} />

      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-brand">
          <img src="/merz-logo.svg" alt="Schreinerei Merz" className="sidebar-logo" />
          <div>
            <span className="side-kicker">Schreinerei Merz</span>
            <strong>MERZ ProjektSuite</strong>
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-label">Module</div>
          <SidebarButton icon={<FolderOpen size={18} />} label="Projekte" active={module === "projects"} onClick={() => setModule("projects")} />
          <SidebarButton icon={<Home size={18} />} label="Import" active={module === "import"} onClick={() => setModule("import")} />
          <SidebarButton icon={<LayoutGrid size={18} />} label="Holz-Alu Fenster" active={module === "catalogue"} onClick={() => setModule("catalogue")} />
          <SidebarButton icon={<FileSpreadsheet size={18} />} label="Workflow Queue" active={module === "queue"} onClick={() => setModule("queue")} />
          <SidebarButton icon={<Settings size={18} />} label="Einstellungen" active={false} onClick={() => {}} />
        </div>
      </aside>

      <main className="main-area">
        <div className="topbar">
          <button className="menu-btn" type="button" onClick={() => setSidebarOpen((v) => !v)}>
            <Menu size={18} />
          </button>
          <div>
            <span className="topbar-kicker">MERZ ProjektSuite</span>
            <strong>{module === "catalogue" ? "Holz-Alu Fenster" : module === "queue" ? "Workflow Queue" : module === "projects" ? "Projekte" : "PDF-Excel Import"}</strong>
          </div>
        </div>

        <section className="hero-banner">
          <div className="hero-copy">
            <div className="hero-chip">SCHREINEREI MERZ · EIN SYSTEM</div>
            <h1>{module === "projects" ? "Projektbasiertes Arbeiten" : module === "catalogue" ? "Holz-Alu Fenster" : "PDF-EXCEL IMPORT"}</h1>
            <p>
              Alles in einem System: Projekte, Fensterlisten, Pläne, Angebote, Exporte und Katalogauswahl.
              Klarer, professioneller und bereit für echten Büroalltag.
            </p>
            <div className="hero-tags">
              <span>MERZ ProjektSuite</span>
              <span>Holz-Alu Fenster</span>
              <span>Projektordner</span>
              <span>Exports</span>
            </div>
          </div>

          <div className="hero-metrics">
            <div className="metric-card"><span>Projekte</span><strong>{projects.length}</strong></div>
            <div className="metric-card"><span>Queue</span><strong>{queue.length}</strong></div>
            <div className="metric-card"><span>Status</span><strong>{status || "bereit"}</strong></div>
          </div>
        </section>

        {(status || error) && (
          <section className="feedback-row global-feedback">
            {status && <div className="status ok"><CheckCircle2 size={18} /><span>{status}</span></div>}
            {error && <div className="status error"><AlertTriangle size={18} /><span>{error}</span></div>}
          </section>
        )}

        {module === "projects" && (
          <section className="grid-two">
            <section className="panel">
              <div className="panel-header row-between">
                <div>
                  <h2>Projektübersicht</h2>
                  <p>Sortiert nach Projektnummer, direkt zugänglich und klar gegliedert.</p>
                </div>
                <button type="button" className="primary-btn" onClick={() => setProjectModalOpen(true)}>
                  <Plus size={16} />
                  Neues Projekt
                </button>
              </div>

              <div className="project-list">
                {projects.map((project) => (
                  <button
                    key={project.id}
                    type="button"
                    className={`project-card ${selectedProjectId === project.id ? "active" : ""}`}
                    onClick={() => setSelectedProjectId(project.id)}
                  >
                    <div className="project-card-top">
                      <span className="code-badge">{project.number}</span>
                      <strong>{project.name}</strong>
                    </div>
                    <div className="project-meta">
                      <span>{project.client || "Kein Kunde"}</span>
                      <span>{project.location || "Kein Ort"}</span>
                    </div>
                  </button>
                ))}
              </div>
            </section>

            <section className="panel">
              <div className="panel-header">
                <h2>Projekt-Dashboard</h2>
                <p>Dateien, Ordnerstruktur und Verknüpfungen für das ausgewählte Projekt.</p>
              </div>

              {projectDetail?.project ? (
                <div className="project-dashboard">
                  <div className="meta-grid compact">
                    <div className="meta-box"><span>Projekt</span><strong>{projectDetail.project.name}</strong></div>
                    <div className="meta-box"><span>Nummer</span><strong>{projectDetail.project.number}</strong></div>
                    <div className="meta-box"><span>Kunde</span><strong>{projectDetail.project.client || "—"}</strong></div>
                    <div className="meta-box"><span>Ort</span><strong>{projectDetail.project.location || "—"}</strong></div>
                  </div>

                  <div className="folder-board">
                    {PROJECT_FOLDERS.map((folder) => (
                      <div className="folder-card" key={folder}>
                        <h3>{folder}</h3>
                        {(projectDetail.files?.[folder] || []).length ? (
                          <ul>
                            {projectDetail.files[folder].map((file) => (
                              <li key={`${folder}-${file.name}`}>{file.name}</li>
                            ))}
                          </ul>
                        ) : (
                          <div className="empty-mini">Noch keine Dateien.</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="empty-state">Projekt auswählen oder ein neues Projekt anlegen.</div>
              )}
            </section>
          </section>
        )}

        {module === "import" && (
          <>
            <section className="grid-two">
              <section className="panel">
                <div className="panel-header">
                  <h2>Fensterlisten-Import</h2>
                  <p>PDF laden, Vorschau prüfen und direkt einem Projekt zuordnen.</p>
                </div>

                <div className="project-picker">
                  <label>Aktives Projekt</label>
                  <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)}>
                    <option value="">Kein Projekt ausgewählt</option>
                    {projects.map((project) => <option key={project.id} value={project.id}>{project.number} · {project.name}</option>)}
                  </select>
                </div>

                <div className="stack">
                  <FileDrop label="Architekten-PDF" file={pdfFile} accept=".pdf,application/pdf" onChange={setPdfFile} icon={<Upload size={22} />} />
                </div>

                <div className="action-row">
                  <button className="primary-btn" onClick={loadPreview} disabled={!pdfFile || loadingPreview}>
                    {loadingPreview ? <Loader2 className="spin" size={18} /> : <Filter size={18} />}
                    Vorschau laden
                  </button>
                  <button className="secondary-btn" onClick={createExcel} disabled={!pdfFile || loadingImport}>
                    {loadingImport ? <Loader2 className="spin" size={18} /> : <Download size={18} />}
                    Excel erzeugen
                  </button>
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>Workflow Queue</h2>
                  <p>Ausgewählte Katalogfamilien werden an das Projekt und den Export gekoppelt.</p>
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
                <p>Erkannte Fensterzeilen vor dem finalen Excel-Export.</p>
              </div>
              {preview?.rows?.length ? <PreviewTable rows={preview.rows} /> : <div className="empty-state">Vorschau wird hier angezeigt, sobald eine PDF geladen und analysiert wurde.</div>}
            </section>
          </>
        )}

        {module === "catalogue" && (
          <section className="grid-two">
            <section className="panel">
              <div className="panel-header">
                <h2>Holz-Alu Fenster</h2>
                <p>Interaktiv, filterbar und direkt mit Projekten und Export verbunden.</p>
              </div>

              <div className="toolbar">
                <div className="search-box">
                  <Search size={16} />
                  <input value={catalogueSearch} onChange={(e) => setCatalogueSearch(e.target.value)} placeholder="Suche nach Familie, Code, Blatt …" />
                </div>
                <select value={catalogueCategory} onChange={(e) => setCatalogueCategory(e.target.value)}>
                  {categories.map((cat) => <option key={cat}>{cat}</option>)}
                </select>
              </div>

              <div className="catalogue-grid">
                {filteredFamilies.map((item) => (
                  <CatalogueCard key={item.code} item={item} active={selectedFamily?.code === item.code} onSelect={setSelectedFamily} onQueue={addToQueue} />
                ))}
              </div>
            </section>

            <section className="panel">
              <div className="panel-header">
                <h2>Familien-Detail</h2>
                <p>Für schnelle Auswahl und Workflow-Übernahme.</p>
              </div>

              {selectedFamily ? (
                <div className="detail-card embedded">
                  <div className="detail-kicker">Produktfamilie {selectedFamily.code}</div>
                  <h2>{selectedFamily.title}</h2>
                  <p>{selectedFamily.description}</p>

                  <div className="meta-grid compact">
                    <div className="meta-box"><span>Kategorie</span><strong>{selectedFamily.category}</strong></div>
                    <div className="meta-box"><span>Blätter</span><strong>{selectedFamily.page_range}</strong></div>
                    <div className="meta-box"><span>Preiszeilen</span><strong>{selectedFamily.pricing_row_count || 0}</strong></div>
                  </div>

                  <div className="detail-actions">
                    <button type="button" className="primary-btn" onClick={() => addToQueue(selectedFamily)}>
                      <Sparkles size={16} />
                      In Workflow Queue
                    </button>
                  </div>
                </div>
              ) : (
                <div className="empty-state">Katalogfamilie auswählen.</div>
              )}
            </section>
          </section>
        )}

        {module === "queue" && (
          <section className="panel">
            <div className="panel-header">
              <h2>Workflow Queue</h2>
              <p>Produktfamilien, die später mit Export, Materialwahl und Projekt verknüpft werden.</p>
            </div>

            <div className="queue-board">
              {queue.length ? queue.map((item) => (
                <div className="queue-board-card" key={item.code}>
                  <span className="code-badge">{item.code}</span>
                  <h3>{item.title}</h3>
                  <p>{item.workflow_hint}</p>
                </div>
              )) : <div className="empty-state">Noch keine Queue-Einträge vorhanden.</div>}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

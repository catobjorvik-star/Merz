import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  Building2,
  CheckCircle2,
  ChevronRight,
  Download,
  FileSpreadsheet,
  Files,
  FolderClosed,
  FolderOpen,
  Home,
  LayoutGrid,
  Loader2,
  MapPin,
  Menu,
  PackageSearch,
  Plus,
  Search,
  Sparkles,
  Upload,
  UserRound,
  X,
} from "lucide-react";
import MerzAnimatedBanner from "./MerzAnimatedBanner";

const API_BASE = "";
const PROJECT_FOLDERS = ["Fensterlisten", "Pläne", "Angebote", "Exports"];
const MODULE_META = {
  projects: {
    kicker: "Projektorganisation / strukturierte Ablage",
    title: "Projektbasiertes Arbeiten",
    description:
      "Projekte, Ordnerstruktur und Dateiablage in einer klaren Merz-Oberfläche. Direkt nutzbar für tägliche Vorgänge.",
    chips: ["Projektordner", "Dateiablage", "Skalierbar"],
  },
  import: {
    kicker: "PDF Import / Prüfung / Excel-Export",
    title: "Fensterlisten-Import",
    description:
      "Architekten-PDF hochladen, Vorschau prüfen, Warnungen sauber erfassen und direkt in die Firmenvorlage exportieren.",
    chips: ["PDF Analyse", "Validierung", "Excel Export"],
  },
  catalogue: {
    kicker: "Holz-Alu Fenster / integrierter Katalog",
    title: "Holz-Alu Fenster",
    description:
      "Produktfamilien filtern, technische Gruppen durchsuchen und relevante Familien für den Workflow vormerken.",
    chips: ["Familien", "Filter", "Workflow Queue"],
  },
  queue: {
    kicker: "Workflow Queue / Übergabe in den Export",
    title: "Vorgemerkte Auswahl",
    description:
      "Ausgewählte Katalogfamilien gesammelt prüfen und gezielt für das laufende Projekt einsetzen.",
    chips: ["Auswahl", "Prüfung", "Projektbezug"],
  },
};

function formatDate(value) {
  if (!value) return "Nicht vorhanden";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatBytes(value) {
  if (value == null || Number.isNaN(Number(value))) return "Nicht vorhanden";
  const units = ["B", "KB", "MB", "GB"];
  let size = Number(value);
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function formatCurrency(value) {
  if (value == null || Number.isNaN(Number(value))) return "Nicht vorhanden";
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
  }).format(Number(value));
}

function valueOrFallback(value, fallback = "Nicht vorhanden") {
  if (value == null) return fallback;
  if (typeof value === "string" && !value.trim()) return fallback;
  return value;
}

function countProjectFiles(project) {
  return Object.values(project?.file_counts || {}).reduce((sum, count) => sum + Number(count || 0), 0);
}

function NavButton({ icon, label, active, onClick }) {
  return (
    <button type="button" className={`nav-button ${active ? "active" : ""}`} onClick={onClick}>
      <span className="nav-button-icon">{icon}</span>
      <span className="nav-button-label">{label}</span>
      <ChevronRight size={16} className="nav-button-arrow" />
    </button>
  );
}

function StatusStrip({ status, error }) {
  if (!status && !error) return null;
  return (
    <section className="status-strip">
      {status ? (
        <div className="status-pill is-success">
          <CheckCircle2 size={16} />
          <span>{status}</span>
        </div>
      ) : null}
      {error ? (
        <div className="status-pill is-error">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      ) : null}
    </section>
  );
}

function MetricTile({ label, value, detail, tone = "neutral" }) {
  return (
    <article className={`metric-tile ${tone}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {detail ? <div className="metric-detail">{detail}</div> : null}
    </article>
  );
}

function ProjectModal({ open, onClose, onCreate }) {
  const [form, setForm] = useState({ name: "", number: "", client: "", location: "", notes: "" });

  useEffect(() => {
    if (!open) {
      setForm({ name: "", number: "", client: "", location: "", notes: "" });
    }
  }, [open]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <div className="section-kicker">Neues Projekt</div>
            <h2>Projekt anlegen</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Schließen">
            <X size={18} />
          </button>
        </div>

        <div className="form-grid two-columns">
          <label className="field-block">
            <span>Projektname</span>
            <input
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="z. B. Hubertusstraße"
            />
          </label>
          <label className="field-block">
            <span>Projektnummer</span>
            <input
              value={form.number}
              onChange={(event) => setForm({ ...form, number: event.target.value })}
              placeholder="z. B. 260284"
            />
          </label>
          <label className="field-block">
            <span>Kunde</span>
            <input
              value={form.client}
              onChange={(event) => setForm({ ...form, client: event.target.value })}
              placeholder="optional"
            />
          </label>
          <label className="field-block">
            <span>Ort</span>
            <input
              value={form.location}
              onChange={(event) => setForm({ ...form, location: event.target.value })}
              placeholder="optional"
            />
          </label>
          <label className="field-block span-2">
            <span>Notizen</span>
            <textarea
              value={form.notes}
              onChange={(event) => setForm({ ...form, notes: event.target.value })}
              placeholder="optionale Hinweise für Team und Workflow"
              rows={5}
            />
          </label>
        </div>

        <div className="action-row">
          <button type="button" className="button button-primary" onClick={() => onCreate(form)}>
            <Plus size={16} />
            Projekt speichern
          </button>
          <button type="button" className="button button-secondary" onClick={onClose}>
            Abbrechen
          </button>
        </div>
      </div>
    </div>
  );
}

function FileDrop({ label, file, accept, onChange, helper }) {
  return (
    <label className={`file-drop ${file ? "has-file" : ""}`}>
      <input
        type="file"
        accept={accept}
        onChange={(event) => onChange(event.target.files?.[0] || null)}
      />
      <div className="file-drop-icon">
        <Upload size={18} />
      </div>
      <div className="file-drop-copy">
        <strong>{label}</strong>
        <span>{file ? file.name : helper}</span>
      </div>
      <ArrowUpRight size={16} className="file-drop-arrow" />
    </label>
  );
}

function ProjectCard({ project, active, onClick }) {
  const totalFiles = countProjectFiles(project);
  return (
    <button type="button" className={`project-card ${active ? "active" : ""}`} onClick={onClick}>
      <div className="project-card-top">
        <div>
          <div className="project-number">{valueOrFallback(project.number)}</div>
          <h3>{valueOrFallback(project.name)}</h3>
        </div>
        <span className="small-badge">{totalFiles} Dateien</span>
      </div>
      <div className="project-card-meta">
        <span>
          <UserRound size={14} />
          {valueOrFallback(project.client)}
        </span>
        <span>
          <MapPin size={14} />
          {valueOrFallback(project.location)}
        </span>
      </div>
      <div className="project-count-grid">
        {PROJECT_FOLDERS.map((folder) => (
          <div key={folder} className="project-count-box">
            <strong>{project.file_counts?.[folder] || 0}</strong>
            <span>{folder}</span>
          </div>
        ))}
      </div>
    </button>
  );
}

function ProjectFilesBoard({ files }) {
  return (
    <div className="folder-board">
      {PROJECT_FOLDERS.map((folder) => {
        const entries = files?.[folder] || [];
        return (
          <article key={folder} className="surface-card folder-card">
            <div className="surface-head compact">
              <div>
                <div className="section-kicker">Ordner</div>
                <h3>{folder}</h3>
              </div>
              <span className="small-badge">{entries.length}</span>
            </div>
            {entries.length ? (
              <div className="file-list">
                {entries.map((item) => (
                  <div key={`${folder}-${item.name}-${item.modified_at}`} className="file-row">
                    <div className="file-row-main">
                      <strong>{item.name}</strong>
                      <span>
                        {formatBytes(item.size)} / {formatDate(item.modified_at)}
                      </span>
                    </div>
                    <Files size={16} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-inline">Noch keine Dateien im Ordner.</div>
            )}
          </article>
        );
      })}
    </div>
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
          {rows.map((row, index) => (
            <tr key={`${row.id || "row"}-${index}`}>
              <td>{valueOrFallback(row.id)}</td>
              <td>{valueOrFallback(row.house)}</td>
              <td>{valueOrFallback(row.floor)}</td>
              <td>{valueOrFallback(row.qty)}</td>
              <td>{row.width_mm ? `${row.width_mm} mm` : "Nicht vorhanden"}</td>
              <td>{row.height_mm ? `${row.height_mm} mm` : "Nicht vorhanden"}</td>
              <td>{valueOrFallback(row.rohbau)}</td>
              <td>{valueOrFallback(row.type)}</td>
              <td>{valueOrFallback([row.room_no, row.room_name].filter(Boolean).join(" / "))}</td>
              <td>{valueOrFallback(row.supplier_type)}</td>
              <td>{formatCurrency(row.supplier_price_eur)}</td>
              <td>
                {row.glass_area_index_m2 != null
                  ? `${Number(row.glass_area_index_m2).toFixed(2)} m²`
                  : "Nicht vorhanden"}
              </td>
              <td>{valueOrFallback(row.supplier_confidence)}</td>
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
      <div className="catalogue-card-top">
        <span className="small-badge accent">Code {item.code}</span>
        <span className="small-badge subtle">{item.page_range}</span>
      </div>
      <h3>{item.title}</h3>
      <p>{item.description}</p>
      <div className="catalogue-card-bottom">
        <span className="catalogue-category">{item.category}</span>
        <button
          type="button"
          className="button button-ghost"
          onClick={(event) => {
            event.stopPropagation();
            onQueue(item);
          }}
        >
          <Plus size={14} />
          Merken
        </button>
      </div>
    </article>
  );
}

function QueueCard({ item, onRemove }) {
  return (
    <article className="queue-card">
      <div className="queue-card-top">
        <div>
          <div className="section-kicker">Katalogfamilie</div>
          <h3>{item.title}</h3>
        </div>
        <button type="button" className="icon-button" onClick={() => onRemove(item.code)} aria-label="Eintrag entfernen">
          <X size={16} />
        </button>
      </div>
      <div className="detail-list compact-list">
        <div>
          <span>Code</span>
          <strong>{item.code}</strong>
        </div>
        <div>
          <span>Kategorie</span>
          <strong>{item.category}</strong>
        </div>
        <div>
          <span>Seiten</span>
          <strong>{item.page_range}</strong>
        </div>
        <div>
          <span>Preiszeilen</span>
          <strong>{item.pricing_row_count || 0}</strong>
        </div>
      </div>
      <p className="queue-copy">{item.workflow_hint}</p>
    </article>
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
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [loadingImport, setLoadingImport] = useState(false);

  const [projectUploadFolder, setProjectUploadFolder] = useState(PROJECT_FOLDERS[0]);
  const [projectUploadFile, setProjectUploadFile] = useState(null);
  const [uploadingProjectFile, setUploadingProjectFile] = useState(false);

  const [catalogue, setCatalogue] = useState({ families: [], materials: [], systems: [] });
  const [selectedFamily, setSelectedFamily] = useState(null);
  const [catalogueSearch, setCatalogueSearch] = useState("");
  const [catalogueCategory, setCatalogueCategory] = useState("Alle");
  const [queue, setQueue] = useState([]);

  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const currentProjectMeta = projectDetail?.project || projects.find((item) => item.id === selectedProjectId) || null;
  const selectedProjectFiles = projectDetail?.files || null;

  const categories = useMemo(
    () => ["Alle", ...Array.from(new Set((catalogue.families || []).map((item) => item.category)))],
    [catalogue],
  );

  const filteredFamilies = useMemo(() => {
    const query = catalogueSearch.trim().toLowerCase();
    return (catalogue.families || []).filter((item) => {
      const matchesCategory = catalogueCategory === "Alle" || item.category === catalogueCategory;
      const haystack = [item.title, item.description, item.page_range, item.code, item.category]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return matchesCategory && (!query || haystack.includes(query));
    });
  }, [catalogue, catalogueSearch, catalogueCategory]);

  const queueMetrics = useMemo(() => {
    const categoriesInQueue = new Set(queue.map((item) => item.category)).size;
    const totalRows = queue.reduce((sum, item) => sum + Number(item.pricing_row_count || 0), 0);
    return { categoriesInQueue, totalRows };
  }, [queue]);

  useEffect(() => {
    loadProjects();
    loadCatalogue();
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      loadProjectDetail(selectedProjectId);
    } else {
      setProjectDetail(null);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    if (!filteredFamilies.length) {
      setSelectedFamily(null);
      return;
    }
    if (!selectedFamily || !filteredFamilies.some((item) => item.code === selectedFamily.code)) {
      setSelectedFamily(filteredFamilies[0]);
    }
  }, [filteredFamilies, selectedFamily]);

  function handleModuleChange(nextModule) {
    setModule(nextModule);
    setSidebarOpen(false);
  }

  async function loadProjects() {
    try {
      const response = await fetch(`${API_BASE}/api/projects`);
      if (!response.ok) return;
      const payload = await response.json();
      const nextProjects = payload.projects || [];
      setProjects(nextProjects);
      setSelectedProjectId((current) => {
        if (current && nextProjects.some((item) => item.id === current)) return current;
        return nextProjects[0]?.id || "";
      });
    } catch {
      setError("Projektliste konnte nicht geladen werden.");
    }
  }

  async function loadProjectDetail(projectId) {
    try {
      const response = await fetch(`${API_BASE}/api/projects/${projectId}`);
      if (!response.ok) throw new Error("Projekt konnte nicht geladen werden.");
      const payload = await response.json();
      setProjectDetail(payload);
    } catch (err) {
      setError(err.message || "Projekt konnte nicht geladen werden.");
    }
  }

  async function loadCatalogue() {
    try {
      const response = await fetch(`${API_BASE}/api/catalogue`);
      if (!response.ok) throw new Error("Katalog konnte nicht geladen werden.");
      const payload = await response.json();
      setCatalogue(payload);
      if (payload.families?.length) setSelectedFamily(payload.families[0]);
    } catch (err) {
      setError(err.message || "Katalogfehler");
    }
  }

  async function createProject(form) {
    try {
      setError("");
      const response = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Projekt konnte nicht erstellt werden.");
      setProjectModalOpen(false);
      setStatus(`Projekt erstellt: ${payload.number} / ${payload.name}`);
      await loadProjects();
      setSelectedProjectId(payload.id);
      await loadProjectDetail(payload.id);
    } catch (err) {
      setError(err.message || "Projektfehler");
    }
  }

  async function uploadProjectFile() {
    if (!selectedProjectId) {
      setError("Bitte zuerst ein Projekt auswählen.");
      return;
    }
    if (!projectUploadFile) {
      setError("Bitte zuerst eine Datei auswählen.");
      return;
    }

    setUploadingProjectFile(true);
    setError("");
    setStatus("Datei wird im Projekt abgelegt ...");

    const formData = new FormData();
    formData.append("folder", projectUploadFolder);
    formData.append("file", projectUploadFile);

    try {
      const response = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/upload`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Datei konnte nicht hochgeladen werden.");
      setProjectUploadFile(null);
      setStatus(`Datei gespeichert: ${payload.filename} in ${payload.folder}`);
      await loadProjectDetail(selectedProjectId);
      await loadProjects();
    } catch (err) {
      setError(err.message || "Dateiupload fehlgeschlagen.");
      setStatus("");
    } finally {
      setUploadingProjectFile(false);
    }
  }

  function addToQueue(item) {
    setQueue((current) => {
      if (current.some((entry) => entry.code === item.code)) return current;
      return [...current, item];
    });
    setStatus(`Zur Queue hinzugefügt: ${item.title}`);
    setError("");
  }

  function removeFromQueue(code) {
    setQueue((current) => current.filter((item) => item.code !== code));
  }

  async function loadPreview() {
    if (!pdfFile) {
      setError("Bitte zuerst eine PDF-Fensterliste hochladen.");
      return;
    }

    setLoadingPreview(true);
    setStatus("PDF wird analysiert ...");
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
      await loadProjects();
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
    setStatus("Excel-Datei wird erzeugt ...");
    setError("");

    const formData = new FormData();
    formData.append("pdf", pdfFile);
    formData.append("catalogue_queue", JSON.stringify(queue.map((item) => item.code)));
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
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);

      setStatus("Excel-Datei erfolgreich erzeugt.");
      if (selectedProjectId) await loadProjectDetail(selectedProjectId);
      await loadProjects();
    } catch (err) {
      setError(err.message || "Unbekannter Fehler");
      setStatus("");
    } finally {
      setLoadingImport(false);
    }
  }

  const currentModuleMeta = MODULE_META[module];

  return (
    <div className="app-shell">
      <ProjectModal open={projectModalOpen} onClose={() => setProjectModalOpen(false)} onCreate={createProject} />

      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-top">
          <div className="sidebar-brand-panel">
            <div className="sidebar-brand-header">
              <img src="/25Jahre_Merz_Logo.svg" alt="25 Jahre Merz" className="sidebar-anniversary" />
              <span className="small-badge accent">interne Plattform</span>
            </div>
            <div className="sidebar-logo-wrap">
              <img src="/merz-logo.svg" alt="Schreinerei Merz" className="sidebar-logo" />
            </div>
            <div className="sidebar-brand-copy">
              <div className="section-kicker">Schreinerei Merz</div>
              <strong>MERZ ProjektSuite</strong>
              <p>Produktorientierte Arbeitsoberfläche für Projekte, Import und Export.</p>
            </div>
          </div>

          <nav className="sidebar-nav">
            <div className="sidebar-section-title">Module</div>
            <NavButton
              icon={<FolderOpen size={18} />}
              label="Projekte"
              active={module === "projects"}
              onClick={() => handleModuleChange("projects")}
            />
            <NavButton
              icon={<Home size={18} />}
              label="Import"
              active={module === "import"}
              onClick={() => handleModuleChange("import")}
            />
            <NavButton
              icon={<LayoutGrid size={18} />}
              label="Holz-Alu Fenster"
              active={module === "catalogue"}
              onClick={() => handleModuleChange("catalogue")}
            />
            <NavButton
              icon={<FileSpreadsheet size={18} />}
              label="Workflow Queue"
              active={module === "queue"}
              onClick={() => handleModuleChange("queue")}
            />
          </nav>
        </div>

        <div className="sidebar-bottom">
          <div className="sidebar-section-title">Systemstatus</div>
          <div className="sidebar-status-card">
            <div className="sidebar-status-row">
              <span>Projekte</span>
              <strong>{projects.length}</strong>
            </div>
            <div className="sidebar-status-row">
              <span>Katalogfamilien</span>
              <strong>{catalogue.family_count || catalogue.families?.length || 0}</strong>
            </div>
            <div className="sidebar-status-row">
              <span>Queue</span>
              <strong>{queue.length}</strong>
            </div>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar premium-entrance">
          <button type="button" className="icon-button mobile-only" onClick={() => setSidebarOpen((current) => !current)}>
            <Menu size={18} />
          </button>
          <div className="topbar-copy">
            <div className="section-kicker">MERZ ProjektSuite</div>
            <strong>{currentModuleMeta.title}</strong>
          </div>
          <div className="topbar-meta">
            <span className="small-badge">FastAPI / React</span>
            <span className="small-badge subtle">Produktiv orientiert</span>
          </div>
        </header>

        <MerzAnimatedBanner
          key={module}
          eyebrow={currentModuleMeta.kicker}
          title={currentModuleMeta.title}
          description={currentModuleMeta.description}
          chips={currentModuleMeta.chips}
        />

        <section className="metric-row premium-entrance">
          <MetricTile label="Aktive Projekte" value={projects.length} detail="Verzeichnisbasierte Struktur" tone="dark" />
          <MetricTile
            label="Aktuelle Auswahl"
            value={currentProjectMeta ? valueOrFallback(currentProjectMeta.number) : "Kein Projekt"}
            detail={currentProjectMeta ? valueOrFallback(currentProjectMeta.name) : "Projekt wählen oder neu anlegen"}
            tone="accent"
          />
          <MetricTile
            label="Katalogfamilien"
            value={catalogue.family_count || catalogue.families?.length || 0}
            detail="Holz-Alu Fenster integriert"
          />
          <MetricTile
            label="Queue"
            value={queue.length}
            detail={`${queueMetrics.categoriesInQueue} Kategorien / ${queueMetrics.totalRows} Preiszeilen`}
          />
        </section>

        <StatusStrip status={status} error={error} />

        {module === "projects" ? (
          <section className="module-grid projects-layout module-entrance">
            <div className="surface-card project-list-card">
              <div className="surface-head">
                <div>
                  <div className="section-kicker">Projektübersicht</div>
                  <h2>Projekte</h2>
                </div>
                <button type="button" className="button button-primary" onClick={() => setProjectModalOpen(true)}>
                  <Plus size={16} />
                  Neues Projekt
                </button>
              </div>

              {projects.length ? (
                <div className="project-list">
                  {projects.map((project) => (
                    <ProjectCard
                      key={project.id}
                      project={project}
                      active={project.id === selectedProjectId}
                      onClick={() => setSelectedProjectId(project.id)}
                    />
                  ))}
                </div>
              ) : (
                <div className="empty-state compact-empty">
                  <FolderClosed size={20} />
                  <div>
                    <strong>Noch keine Projekte vorhanden.</strong>
                    <span>Lege das erste Projekt an, damit Uploads und Exporte sauber strukturiert gespeichert werden.</span>
                  </div>
                </div>
              )}
            </div>

            <div className="content-stack">
              <div className="surface-card">
                <div className="surface-head">
                  <div>
                    <div className="section-kicker">Projektordner</div>
                    <h2>{currentProjectMeta ? currentProjectMeta.name : "Kein Projekt ausgewählt"}</h2>
                  </div>
                  {currentProjectMeta ? <span className="small-badge accent">{currentProjectMeta.number}</span> : null}
                </div>

                {currentProjectMeta ? (
                  <>
                    <div className="detail-list">
                      <div>
                        <span>Projektname</span>
                        <strong>{valueOrFallback(currentProjectMeta.name)}</strong>
                      </div>
                      <div>
                        <span>Projektnummer</span>
                        <strong>{valueOrFallback(currentProjectMeta.number)}</strong>
                      </div>
                      <div>
                        <span>Kunde</span>
                        <strong>{valueOrFallback(currentProjectMeta.client)}</strong>
                      </div>
                      <div>
                        <span>Ort</span>
                        <strong>{valueOrFallback(currentProjectMeta.location)}</strong>
                      </div>
                      <div>
                        <span>Erstellt</span>
                        <strong>{formatDate(currentProjectMeta.created_at)}</strong>
                      </div>
                      <div>
                        <span>Dateien gesamt</span>
                        <strong>{countProjectFiles(currentProjectMeta)}</strong>
                      </div>
                    </div>
                    <div className="notes-box">
                      <div className="section-kicker">Notizen</div>
                      <p>{valueOrFallback(currentProjectMeta.notes, "Keine Notizen hinterlegt.")}</p>
                    </div>
                  </>
                ) : (
                  <div className="empty-state compact-empty">
                    <Building2 size={20} />
                    <div>
                      <strong>Projekt auswählen</strong>
                      <span>Nach der Auswahl erscheinen Metadaten, Ordnerstruktur und Dateiliste.</span>
                    </div>
                  </div>
                )}
              </div>

              <div className="surface-card">
                <div className="surface-head">
                  <div>
                    <div className="section-kicker">Projekt Upload</div>
                    <h2>Datei gezielt ablegen</h2>
                  </div>
                  <span className="small-badge subtle">/api/projects/&#123;id&#125;/upload</span>
                </div>
                <div className="upload-grid">
                  <label className="field-block">
                    <span>Zielordner</span>
                    <select value={projectUploadFolder} onChange={(event) => setProjectUploadFolder(event.target.value)}>
                      {PROJECT_FOLDERS.map((folder) => (
                        <option key={folder} value={folder}>
                          {folder}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="field-block span-2">
                    <span>Datei</span>
                    <FileDrop
                      label="Projektdatei"
                      file={projectUploadFile}
                      accept=".pdf,.xlsx,.xls,.dwg,.png,.jpg,.jpeg,.zip"
                      onChange={setProjectUploadFile}
                      helper="Datei auswählen und dem gewählten Ordner zuweisen"
                    />
                  </div>
                </div>
                <div className="action-row">
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={uploadProjectFile}
                    disabled={!selectedProjectId || !projectUploadFile || uploadingProjectFile}
                  >
                    {uploadingProjectFile ? <Loader2 size={16} className="spin" /> : <Upload size={16} />}
                    Datei speichern
                  </button>
                </div>
              </div>

              <ProjectFilesBoard files={selectedProjectFiles} />
            </div>
          </section>
        ) : null}

        {module === "import" ? (
          <section className="module-grid import-layout module-entrance">
            <div className="content-stack">
              <div className="surface-card">
                <div className="surface-head">
                  <div>
                    <div className="section-kicker">Importsteuerung</div>
                    <h2>PDF / Vorschau / Export</h2>
                  </div>
                  <span className="small-badge accent">Stabiler Kernfluss</span>
                </div>

                <div className="form-grid two-columns">
                  <label className="field-block span-2">
                    <span>Projektzuordnung</span>
                    <select value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)}>
                      <option value="">Ohne Projektzuordnung</option>
                      {projects.map((project) => (
                        <option key={project.id} value={project.id}>
                          {project.number} / {project.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="field-block span-2">
                    <span>PDF Fensterliste</span>
                    <FileDrop
                      label="Architekten-PDF"
                      file={pdfFile}
                      accept=".pdf,application/pdf"
                      onChange={setPdfFile}
                      helper="PDF laden und anschließend Vorschau oder Excel-Export starten"
                    />
                  </div>
                </div>

                <div className="action-row">
                  <button type="button" className="button button-primary" onClick={loadPreview} disabled={!pdfFile || loadingPreview}>
                    {loadingPreview ? <Loader2 size={16} className="spin" /> : <PackageSearch size={16} />}
                    Vorschau laden
                  </button>
                  <button type="button" className="button button-secondary" onClick={createExcel} disabled={!pdfFile || loadingImport}>
                    {loadingImport ? <Loader2 size={16} className="spin" /> : <Download size={16} />}
                    Excel erzeugen
                  </button>
                </div>
              </div>

              <div className="surface-card">
                <div className="surface-head">
                  <div>
                    <div className="section-kicker">Vorschau</div>
                    <h2>Extrahierte Fensterdaten</h2>
                  </div>
                  {preview?.count ? <span className="small-badge accent">{preview.count} Zeilen</span> : null}
                </div>

                {preview?.rows?.length ? (
                  <>
                    <div className="detail-list compact-list import-summary-grid">
                      <div>
                        <span>Quell-PDF</span>
                        <strong>{valueOrFallback(preview.source_pdf)}</strong>
                      </div>
                      <div>
                        <span>Warnungen</span>
                        <strong>{preview.warnings?.length || 0}</strong>
                      </div>
                      <div>
                        <span>Projekt</span>
                        <strong>{valueOrFallback(currentProjectMeta?.number, "Nicht zugeordnet")}</strong>
                      </div>
                      <div>
                        <span>Queue</span>
                        <strong>{queue.length} Einträge</strong>
                      </div>
                    </div>
                    {preview.warnings?.length ? (
                      <div className="warning-box">
                        {preview.warnings.map((warning, index) => (
                          <div key={`${warning}-${index}`} className="warning-row">
                            <AlertTriangle size={14} />
                            <span>{warning}</span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    <PreviewTable rows={preview.rows} />
                  </>
                ) : (
                  <div className="empty-state compact-empty">
                    <FileSpreadsheet size={20} />
                    <div>
                      <strong>Noch keine Vorschau geladen.</strong>
                      <span>Nach dem Upload erscheint hier die validierte Vorschau aus dem Backend.</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="content-stack">
              <div className="surface-card accent-card">
                <div className="surface-head">
                  <div>
                    <div className="section-kicker">Workflow Fokus</div>
                    <h2>Importstatus</h2>
                  </div>
                  <Sparkles size={18} />
                </div>
                <div className="detail-list compact-list">
                  <div>
                    <span>PDF ausgewählt</span>
                    <strong>{pdfFile ? "Ja" : "Nein"}</strong>
                  </div>
                  <div>
                    <span>Projektbindung</span>
                    <strong>{selectedProjectId ? "Aktiv" : "Keine"}</strong>
                  </div>
                  <div>
                    <span>Queue aktiv</span>
                    <strong>{queue.length}</strong>
                  </div>
                  <div>
                    <span>Exportstatus</span>
                    <strong>{loadingImport ? "Läuft" : "Bereit"}</strong>
                  </div>
                </div>
                <p className="supporting-copy">
                  Der bestehende Backend-Fluss bleibt erhalten: Upload, Extraktion, Normalisierung, Validierung,
                  Anreicherung, Vorschau und Excel-Erzeugung.
                </p>
              </div>

              <div className="surface-card">
                <div className="surface-head">
                  <div>
                    <div className="section-kicker">Verknüpftes Projekt</div>
                    <h2>{currentProjectMeta ? currentProjectMeta.name : "Kein Projekt"}</h2>
                  </div>
                </div>
                {currentProjectMeta ? (
                  <div className="detail-list compact-list">
                    <div>
                      <span>Nummer</span>
                      <strong>{valueOrFallback(currentProjectMeta.number)}</strong>
                    </div>
                    <div>
                      <span>Kunde</span>
                      <strong>{valueOrFallback(currentProjectMeta.client)}</strong>
                    </div>
                    <div>
                      <span>Ort</span>
                      <strong>{valueOrFallback(currentProjectMeta.location)}</strong>
                    </div>
                    <div>
                      <span>Dateien gesamt</span>
                      <strong>{countProjectFiles(currentProjectMeta)}</strong>
                    </div>
                  </div>
                ) : (
                  <div className="empty-inline">Kein Projekt ausgewählt. Upload und Export funktionieren weiterhin.</div>
                )}
              </div>
            </div>
          </section>
        ) : null}

        {module === "catalogue" ? (
          <section className="module-grid catalogue-layout module-entrance">
            <div className="surface-card">
              <div className="surface-head">
                <div>
                  <div className="section-kicker">Filter und Suche</div>
                  <h2>Katalogfamilien</h2>
                </div>
                <span className="small-badge accent">{filteredFamilies.length} Treffer</span>
              </div>

              <div className="catalogue-toolbar">
                <label className="search-field">
                  <Search size={16} />
                  <input
                    value={catalogueSearch}
                    onChange={(event) => setCatalogueSearch(event.target.value)}
                    placeholder="Suche nach Familie, Bereich, Code oder Kategorie"
                  />
                </label>
                <label className="field-block compact-field">
                  <span>Kategorie</span>
                  <select value={catalogueCategory} onChange={(event) => setCatalogueCategory(event.target.value)}>
                    {categories.map((category) => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {filteredFamilies.length ? (
                <div className="catalogue-grid">
                  {filteredFamilies.map((item) => (
                    <CatalogueCard
                      key={item.code}
                      item={item}
                      active={selectedFamily?.code === item.code}
                      onSelect={setSelectedFamily}
                      onQueue={addToQueue}
                    />
                  ))}
                </div>
              ) : (
                <div className="empty-state compact-empty">
                  <Search size={20} />
                  <div>
                    <strong>Keine Treffer gefunden.</strong>
                    <span>Bitte Filter oder Suchbegriff anpassen.</span>
                  </div>
                </div>
              )}
            </div>

            <div className="content-stack sticky-stack">
              <div className="surface-card accent-card">
                <div className="surface-head">
                  <div>
                    <div className="section-kicker">Ausgewählte Familie</div>
                    <h2>{selectedFamily ? selectedFamily.title : "Keine Auswahl"}</h2>
                  </div>
                  {selectedFamily ? <span className="small-badge accent">Code {selectedFamily.code}</span> : null}
                </div>

                {selectedFamily ? (
                  <>
                    <p className="supporting-copy">{selectedFamily.description}</p>
                    <div className="detail-list compact-list">
                      <div>
                        <span>Kategorie</span>
                        <strong>{selectedFamily.category}</strong>
                      </div>
                      <div>
                        <span>Seitenbereich</span>
                        <strong>{selectedFamily.page_range}</strong>
                      </div>
                      <div>
                        <span>Pricing PDF Seite</span>
                        <strong>{valueOrFallback(selectedFamily.pricing_pdf_page)}</strong>
                      </div>
                      <div>
                        <span>Preiszeilen</span>
                        <strong>{selectedFamily.pricing_row_count || 0}</strong>
                      </div>
                    </div>
                    <div className="action-row tight-row">
                      <button type="button" className="button button-primary" onClick={() => addToQueue(selectedFamily)}>
                        <Plus size={16} />
                        Zur Queue
                      </button>
                    </div>
                    <div className="notes-box dark-note">
                      <div className="section-kicker">Workflow Hinweis</div>
                      <p>{selectedFamily.workflow_hint}</p>
                    </div>
                  </>
                ) : (
                  <div className="empty-inline">Bitte eine Familie aus der Liste auswählen.</div>
                )}
              </div>

              <div className="surface-card">
                <div className="surface-head compact">
                  <div>
                    <div className="section-kicker">Preisraster</div>
                    <h3>Erste Zeilen</h3>
                  </div>
                  <span className="small-badge subtle">max. 8</span>
                </div>
                {selectedFamily?.price_rows?.length ? (
                  <div className="mini-table-wrap">
                    <table className="mini-table">
                      <thead>
                        <tr>
                          <th>Breite</th>
                          <th>Höhe</th>
                          <th>Glasfläche</th>
                          <th>Spalten</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedFamily.price_rows.slice(0, 8).map((row, index) => (
                          <tr key={`${row.width_mm}-${row.height_mm}-${index}`}>
                            <td>{row.width_mm} mm</td>
                            <td>{row.height_mm} mm</td>
                            <td>{valueOrFallback(row.glass_area_index_m2)}</td>
                            <td>{row.column_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty-inline">Für diese Familie sind keine Preiszeilen im Snapshot vorhanden.</div>
                )}
              </div>

              <div className="surface-card">
                <div className="surface-head compact">
                  <div>
                    <div className="section-kicker">Zusatzdaten</div>
                    <h3>Materialien und Systeme</h3>
                  </div>
                </div>
                <div className="pill-stack">
                  {(catalogue.materials || []).map((item) => (
                    <span key={item.label} className="pill-tag">
                      {item.label} / {item.note}
                    </span>
                  ))}
                  {(catalogue.systems || []).map((item) => (
                    <span key={item.name} className="pill-tag dark-pill">
                      {item.name} / {item.kind}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </section>
        ) : null}

        {module === "queue" ? (
          <section className="module-grid queue-layout module-entrance">
            <div className="content-stack">
              <div className="surface-card">
                <div className="surface-head">
                  <div>
                    <div className="section-kicker">Workflow Queue</div>
                    <h2>Vorgemerkte Familien</h2>
                  </div>
                  <span className="small-badge accent">{queue.length} Einträge</span>
                </div>
                {queue.length ? (
                  <div className="queue-grid">
                    {queue.map((item) => (
                      <QueueCard key={item.code} item={item} onRemove={removeFromQueue} />
                    ))}
                  </div>
                ) : (
                  <div className="empty-state compact-empty">
                    <LayoutGrid size={20} />
                    <div>
                      <strong>Die Queue ist noch leer.</strong>
                      <span>Im Katalog ausgewählte Familien erscheinen hier für die weitere Projektarbeit.</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="content-stack sticky-stack">
              <div className="surface-card accent-card">
                <div className="surface-head">
                  <div>
                    <div className="section-kicker">Queue Kontext</div>
                    <h2>{currentProjectMeta ? currentProjectMeta.name : "Kein Projekt ausgewählt"}</h2>
                  </div>
                </div>
                <div className="detail-list compact-list">
                  <div>
                    <span>Projekt</span>
                    <strong>{valueOrFallback(currentProjectMeta?.number, "Nicht zugeordnet")}</strong>
                  </div>
                  <div>
                    <span>Kategorien</span>
                    <strong>{queueMetrics.categoriesInQueue}</strong>
                  </div>
                  <div>
                    <span>Preiszeilen</span>
                    <strong>{queueMetrics.totalRows}</strong>
                  </div>
                  <div>
                    <span>Exportbereit</span>
                    <strong>{pdfFile ? "Ja" : "PDF fehlt"}</strong>
                  </div>
                </div>
                <p className="supporting-copy">
                  Die Queue wird unverändert über <code>catalogue_queue</code> an den bestehenden Import-Endpunkt übergeben.
                </p>
              </div>

              <div className="surface-card">
                <div className="surface-head compact">
                  <div>
                    <div className="section-kicker">Nächste Schritte</div>
                    <h3>Empfohlene Reihenfolge</h3>
                  </div>
                </div>
                <div className="check-list">
                  <div>
                    <CheckCircle2 size={16} />
                    <span>Projekt auswählen oder anlegen</span>
                  </div>
                  <div>
                    <CheckCircle2 size={16} />
                    <span>Passende Katalogfamilien vormerken</span>
                  </div>
                  <div>
                    <CheckCircle2 size={16} />
                    <span>PDF laden und Vorschau prüfen</span>
                  </div>
                  <div>
                    <CheckCircle2 size={16} />
                    <span>Excel-Datei auf Basis des Templates erzeugen</span>
                  </div>
                </div>
              </div>
            </div>
          </section>
        ) : null}
      </main>
    </div>
  );
}

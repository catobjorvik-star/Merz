export default function MerzAnimatedBanner() {
  return (
    <section className="merz-banner">
      <div className="merz-glow merz-glow-left" />
      <div className="merz-glow merz-glow-right" />
      <div className="merz-grid" />

      <div className="merz-banner-inner">
        <div className="merz-logo-wrap">
          <div className="merz-logo-ring" />
          <div className="merz-logo-ring merz-logo-ring-2" />
          <img src="/merz-logo.svg" alt="Schreinerei MERZ" className="merz-logo" />
        </div>

        <div className="merz-copy">
          <div className="merz-kicker">Schreinerei MERZ</div>
          <h1>PDF-EXCEL IMPORT</h1>
          <p>
            Fensterlisten schneller prüfen, sauber zuordnen und direkt in die
            Kalkulation übernehmen.
          </p>

          <div className="merz-pills">
            <span>PDF Import</span>
            <span>Excel Workflow</span>
            <span>Mobile Ready</span>
          </div>
        </div>
      </div>

      <div className="merz-shine" />
    </section>
  );
}

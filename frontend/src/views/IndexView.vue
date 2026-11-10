<script setup>
import BrandLogo from '../components/ui/BrandLogo.vue'

const professions = [
  'Polymechaniker/in EFZ',
  'Konstrukteur/in EFZ',
  'Automatiker/in EFZ',
  'Automatikmonteur/in EFZ',
  'Anlagen- und Apparatebauer/in EFZ',
  'Produktionsmechaniker/in EFZ',
  'Elektroniker/in EFZ',
  'Mechanikpraktiker/in EBA'
]

const steps = [
  {
    number: '01',
    title: 'Firma registrieren',
    text: 'Mit der Firmen-E-Mail-Adresse registrieren. Die Domain (z. B. firma.ch) eröffnet Ihrer Firma einen eigenen, abgetrennten Datenbereich. Bestätigung per E-Mail-Link.'
  },
  {
    number: '02',
    title: 'Team einladen',
    text: 'Die Administration lädt Ausbildner/innen und Lernende über die Personenverwaltung ein. Diese setzen ihr Passwort selbst über den Einladungslink.'
  },
  {
    number: '03',
    title: 'Loslegen',
    text: 'Projekte planen, Lernziele bewerten, Noten erfassen und die Lerndokumentation führen – alles an einem Ort, ohne Papier.'
  }
]

const features = [
  {
    icon: 'chart',
    title: 'Noten & Prüfungen',
    text: 'Schulnoten und Prüfungsresultate erfassen – mit direktem Bezug zu den Lernzielen des Lehrplans.'
  },
  {
    icon: 'award',
    title: 'Zeugnisse & Nachweise',
    text: 'Zeugnisse, Kursbestätigungen und Zertifikate ablegen und jederzeit wiederfinden.'
  },
  {
    icon: 'chat',
    title: 'Ausbildungsgespräche',
    text: 'Gespräche vorbereiten und protokollieren – nachvollziehbar für Lernende und Ausbildnende.'
  },
  {
    icon: 'journal',
    title: 'Lernjournal',
    text: 'Arbeits- und Lernreflexion chronologisch festhalten, direkt in der App geschrieben.'
  }
]
</script>

<template>
  <div class="landing">
    <div class="alpha-bar">
      <span class="alpha-tag">Alpha</span>
      <span class="alpha-text">
        Frühe Testversion – wir freuen uns über Feedback an
        <a href="mailto:kontakt@lehrjahre.ch">kontakt@lehrjahre.ch</a>.
      </span>
    </div>

    <header class="site-header">
      <div class="container header-inner">
        <RouterLink to="/" class="brand">
          <BrandLogo :size="40" />
          <span class="brand-name">lehrjahre<span class="brand-suffix">.ch</span></span>
        </RouterLink>
        <nav class="header-nav">
          <a href="#ablauf" class="nav-link">So funktioniert's</a>
          <a href="#lerndokumentation" class="nav-link">Lerndokumentation</a>
          <RouterLink to="/login" class="btn header-login">Anmelden</RouterLink>
          <RouterLink to="/registrierung" class="btn btn-primary">Registrieren</RouterLink>
        </nav>
      </div>
    </header>

    <section class="hero">
      <div class="container hero-grid">
        <div class="hero-copy">
          <span class="eyebrow">
            <span class="eyebrow-dot"></span>
            Digitale Lerndokumentation für MEM-Berufslehren
          </span>
          <h1>
            Die Berufslehre.<br />
            <span class="hero-accent">Digital dokumentiert.</span>
          </h1>
          <p class="hero-lead">
            Projekte planen, Lernziele bewerten, Noten erfassen und Dokumente
            ablegen – das Papier-Heft, neu an einem Ort. Für Lernende,
            Ausbildner/innen und Administration.
          </p>
          <div class="hero-actions">
            <RouterLink to="/registrierung" class="btn btn-primary btn-xl">
              Firma registrieren
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </RouterLink>
            <RouterLink to="/login" class="btn btn-xl">Anmelden</RouterLink>
          </div>
          <ul class="hero-checks">
            <li>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6" /></svg>
              Eigener Datenbereich pro Firma
            </li>
            <li>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6" /></svg>
              PDF, Word oder direkt in der App
            </li>
            <li>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6" /></svg>
              Bereit für die ganze Lehre
            </li>
          </ul>
        </div>

        <div class="hero-visual" aria-hidden="true">
          <div class="app-window">
            <div class="app-bar">
              <span class="app-dot"></span>
              <span class="app-dot"></span>
              <span class="app-dot"></span>
              <span class="app-bar-title">lehrjahre.ch</span>
            </div>
            <div class="app-body">
              <aside class="app-side">
                <span class="side-item">Projekte</span>
                <span class="side-item active">Lerndokumentation</span>
                <span class="side-item">Wissen</span>
                <span class="side-item">Lehrplan</span>
              </aside>
              <div class="app-content">
                <div class="mock-kicker">Lernjournal · 1. Lehrjahr</div>
                <div class="mock-title">Woche 12 – Fräsen</div>
                <div class="mock-lines">
                  <span></span>
                  <span></span>
                  <span class="short"></span>
                </div>
                <div class="mock-doc">
                  <span class="mock-file">PDF</span>
                  <span class="mock-doc-text">
                    <strong>Zeugnis 1. Semester</strong>
                    <small>hochgeladen · 1.2 MB</small>
                  </span>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 21h16" /></svg>
                </div>
                <div class="mock-chips">
                  <span class="mock-chip">Note 5.5</span>
                  <span class="mock-chip green">Ziel erreicht</span>
                  <span class="mock-chip soft">Konstrukteur/in EFZ</span>
                </div>
              </div>
            </div>
          </div>
          <div class="float-card float-a">
            <span class="float-icon">✓</span>
            Noten erfasst
          </div>
          <div class="float-card float-b">
            <span class="float-icon accent">↑</span>
            Dokument hochgeladen
          </div>
        </div>
      </div>
    </section>

    <section class="professions">
      <div class="container">
        <p class="professions-label">Gemacht für die MEM-Berufslehren</p>
        <ul class="profession-list">
          <li v-for="profession in professions" :key="profession">{{ profession }}</li>
        </ul>
      </div>
    </section>

    <section id="ablauf" class="section">
      <div class="container">
        <div class="section-head">
          <span class="section-eyebrow">Registrierung</span>
          <h2>In drei Schritten startklar</h2>
          <p>
            Der Zugang gehört der Firma, nicht einer Einzelperson. So bleibt die
            Lerndokumentation auch bei Personalwechseln vollständig.
          </p>
        </div>
        <div class="steps">
          <article v-for="step in steps" :key="step.number" class="step-card">
            <span class="step-number">{{ step.number }}</span>
            <h3>{{ step.title }}</h3>
            <p>{{ step.text }}</p>
          </article>
        </div>
        <p class="section-note">
          Ihre Firma ist bereits registriert? Dann warten Sie auf die Einladung
          Ihrer Administration oder
          <RouterLink to="/login">melden Sie sich direkt an</RouterLink>.
        </p>
      </div>
    </section>

    <section id="lerndokumentation" class="section section-alt">
      <div class="container">
        <div class="section-head">
          <span class="section-eyebrow">Lerndokumentation</span>
          <h2>Alles, was die Lehre braucht</h2>
          <p>
            Die digitale Lerndokumentation begleitet vom ersten Projekt bis zum
            Qualifikationsverfahren – übersichtlich, nachvollziehbar und ohne
            Papierstapel.
          </p>
        </div>
        <div class="feature-grid">
          <article v-for="feature in features" :key="feature.title" class="feature-card">
            <span class="feature-icon">
              <svg v-if="feature.icon === 'chart'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M4 20V10M10 20V4M16 20v-6M22 20H2" />
              </svg>
              <svg v-else-if="feature.icon === 'award'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="9" r="5" />
                <path d="M9 13.5 8 21l4-2 4 2-1-7.5" />
              </svg>
              <svg v-else-if="feature.icon === 'chat'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M21 12a8 8 0 0 1-8 8H7l-4 3v-6a8 8 0 0 1 6-12h4a8 8 0 0 1 8 7z" />
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M6 4h10a3 3 0 0 1 3 3v13H9a3 3 0 0 1-3-3V4z" />
                <path d="M10 8h5M10 12h5" />
              </svg>
            </span>
            <h3>{{ feature.title }}</h3>
            <p>{{ feature.text }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <div class="section-head">
          <span class="section-eyebrow">Dokumente</span>
          <h2>Hochladen oder direkt schreiben</h2>
          <p>
            Ob gescanntes Zeugnis oder frisch verfasster Journal-Eintrag – beides
            landet am selben Ort und ist für berechtigte Personen sofort sichtbar.
          </p>
        </div>
        <div class="doc-grid">
          <article class="doc-card">
            <span class="doc-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 16V4m0 0 4 4m-4-4L8 8" />
                <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
              </svg>
            </span>
            <h3>Datei hochladen</h3>
            <p>
              PDFs, Word-Dokumente oder Bilder hochladen – Zeugnisse,
              Kursnachweise, Formulare. PDFs und Office-Dateien lassen sich
              direkt in der App ansehen.
            </p>
            <div class="file-chips" aria-hidden="true">
              <span class="file-chip"><span class="file-badge pdf">PDF</span> Zeugnis_2026.pdf</span>
              <span class="file-chip"><span class="file-badge doc">DOC</span> Bericht.docx</span>
            </div>
          </article>
          <article class="doc-card">
            <span class="doc-icon accent">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 20h9" />
                <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
              </svg>
            </span>
            <h3>In der App schreiben</h3>
            <p>
              Lernjournal und Ausbildungsgespräche direkt in der App verfassen –
              mit einem Editor für formatierten Text. Änderungen sind sofort
              versioniert und nachvollziehbar.
            </p>
            <div class="editor-mock" aria-hidden="true">
              <span class="editor-line bold"></span>
              <span class="editor-line"></span>
              <span class="editor-line short"></span>
            </div>
          </article>
        </div>
      </div>
    </section>

    <section class="section section-os">
      <div class="container">
        <div class="os-panel">
          <span class="os-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 .5A11.5 11.5 0 0 0 .5 12a11.5 11.5 0 0 0 7.86 10.92c.58.1.79-.25.79-.55v-2.1c-3.2.7-3.88-1.36-3.88-1.36-.52-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.56-.29-5.25-1.28-5.25-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.8 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.43-2.7 5.4-5.27 5.69.41.36.78 1.06.78 2.14v3.17c0 .3.21.66.8.55A11.5 11.5 0 0 0 23.5 12 11.5 11.5 0 0 0 12 .5z" />
            </svg>
          </span>
          <div class="os-copy">
            <span class="section-eyebrow">Open Source</span>
            <h2>Auch auf Ihren eigenen Servern</h2>
            <p>
              lehrjahre.ch ist Open Source. Installieren Sie die Anwendung
              auf eigene Faust in Ihrer Firma – die Daten bleiben bei Ihnen.
            </p>
          </div>
          <a
            class="btn btn-xl os-btn"
            href="https://github.com/cazaugg/lehrjahre.ch"
            target="_blank"
            rel="noopener noreferrer"
          >
            Auf GitHub ansehen
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M7 17 17 7M9 7h8v8" />
            </svg>
          </a>
        </div>
      </div>
    </section>

    <section class="cta-section">
      <div class="container">
        <div class="cta-panel">
          <div>
            <h2>Bereit für die digitale Lerndokumentation?</h2>
            <p>
              Registrieren Sie Ihre Firma und laden Sie Ihr Team ein – in wenigen
              Minuten einsatzbereit.
            </p>
          </div>
          <div class="cta-actions">
            <RouterLink to="/registrierung" class="btn btn-accent btn-xl">
              Jetzt Firma registrieren
            </RouterLink>
            <RouterLink to="/login" class="cta-login">Bereits registriert? Anmelden</RouterLink>
          </div>
        </div>
      </div>
    </section>

    <footer class="site-footer">
      <div class="container footer-inner">
        <div class="brand footer-brand">
          <BrandLogo :size="30" />
          <span class="brand-name small">lehrjahre<span class="brand-suffix">.ch</span></span>
          <span class="badge badge-warning" title="Frühe Prototyp-Version">Alpha</span>
        </div>
        <div class="footer-right">
          <p class="footer-note">Digitale Lerndokumentation für MEM-Berufslehren in der Schweiz.</p>
          <div class="footer-links">
            <a href="mailto:kontakt@lehrjahre.ch">Feedback</a>
            <span class="footer-sep" aria-hidden="true">·</span>
            <a
              href="https://github.com/cazaugg/lehrjahre.ch"
              target="_blank"
              rel="noopener noreferrer"
            >GitHub</a>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.landing {
  min-height: 100vh;
  background: var(--color-bg);
  color: var(--color-text);
  overflow-x: hidden;
  scroll-behavior: smooth;
}

.section[id] {
  scroll-margin-top: 84px;
}

/* Alpha notice */
.alpha-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px var(--space-4);
  background: #0b2236;
  color: #dbe4ee;
  font-size: 0.92rem;
  text-align: center;
}

.alpha-tag {
  padding: 2px 9px;
  border-radius: 999px;
  background: var(--color-accent);
  color: #ffffff;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.alpha-bar a {
  color: #ffffff;
  text-decoration: underline;
}

.alpha-bar a:hover {
  color: #ffffff;
}

.container {
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}

/* Header */
.site-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(248, 250, 252, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(191, 213, 230, 0.6);
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  height: 68px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-text);
  text-decoration: none;
}

.brand:hover {
  text-decoration: none;
  color: var(--color-text);
}

.brand-name {
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.brand-name.small {
  font-size: 1rem;
}

.brand-suffix {
  color: var(--color-primary);
}

.header-nav {
  display: flex;
  align-items: center;
  gap: var(--space-5);
}

.nav-link {
  font-size: 0.88rem;
  font-weight: 500;
  color: var(--color-text-muted);
  text-decoration: none;
}

.nav-link:hover {
  color: var(--color-primary);
  text-decoration: none;
}

.header-login {
  background: transparent;
  border-color: transparent;
  box-shadow: none;
}

/* Hero */
.hero {
  position: relative;
  padding: var(--space-8) 0 3rem;
  background:
    radial-gradient(900px 420px at 12% -10%, rgba(22, 78, 120, 0.14), transparent 65%),
    radial-gradient(700px 360px at 92% 0%, rgba(200, 30, 36, 0.08), transparent 60%);
}

.hero-grid {
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  gap: 3.5rem;
  align-items: center;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.8rem;
  border-radius: 999px;
  background: var(--color-primary-soft);
  border: 1px solid var(--color-primary-border);
  color: var(--color-primary);
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.eyebrow-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-accent);
}

.hero h1 {
  margin: var(--space-5) 0 var(--space-4);
  font-size: clamp(2.3rem, 4.6vw, 3.4rem);
  line-height: 1.06;
  letter-spacing: -0.03em;
  font-weight: 750;
}

.hero-accent {
  background: linear-gradient(100deg, var(--color-primary) 10%, #2d7fb8 90%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.hero-lead {
  max-width: 34rem;
  font-size: 1.06rem;
  line-height: 1.65;
  color: var(--color-text-muted);
  margin-bottom: var(--space-6);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-6);
}

.btn-xl {
  height: 48px;
  padding: 0 1.5rem;
  font-size: 0.95rem;
  border-radius: 9px;
}

.btn-xl svg {
  width: 18px;
  height: 18px;
}

.hero-checks {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-5);
  margin: 0;
  padding: 0;
  color: var(--color-text-light);
  font-size: 0.85rem;
}

.hero-checks li {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.hero-checks svg {
  width: 15px;
  height: 15px;
  color: var(--color-success);
}

/* Hero product mock */
.hero-visual {
  position: relative;
  min-width: 0;
}

.app-window {
  position: relative;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid var(--color-border);
  box-shadow:
    0 30px 60px -24px rgba(11, 34, 54, 0.32),
    0 8px 20px -10px rgba(11, 34, 54, 0.14);
  overflow: hidden;
}

.app-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  background: var(--color-surface-muted);
  border-bottom: 1px solid var(--color-border);
}

.app-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #d7e0ea;
}

.app-dot:first-child {
  background: #f3b6b8;
}

.app-dot:nth-child(2) {
  background: #f3ddb0;
}

.app-dot:nth-child(3) {
  background: #bfe3c8;
}

.app-bar-title {
  margin-left: auto;
  font-size: 0.68rem;
  color: var(--color-text-light);
  letter-spacing: 0.03em;
}

.app-body {
  display: flex;
  min-height: 310px;
}

.app-side {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 18px 12px;
  width: 42%;
  max-width: 158px;
  background: var(--color-sidebar);
}

.side-item {
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 0.72rem;
  color: var(--color-sidebar-muted);
}

.side-item.active {
  background: var(--color-sidebar-active);
  color: #ffffff;
  font-weight: 600;
}

.app-content {
  flex: 1;
  padding: 22px 20px;
  min-width: 0;
}

.mock-kicker {
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--color-text-light);
}

.mock-title {
  margin: 4px 0 14px;
  font-size: 1.02rem;
  font-weight: 700;
}

.mock-lines {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-bottom: 16px;
}

.mock-lines span {
  height: 7px;
  border-radius: 4px;
  background: #e8eef4;
}

.mock-lines span:nth-child(2) {
  width: 88%;
}

.mock-lines span.short {
  width: 60%;
}

.mock-doc {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface-muted);
}

.mock-doc svg {
  width: 16px;
  height: 16px;
  color: var(--color-text-light);
  margin-left: auto;
}

.mock-file {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: var(--color-accent-soft);
  color: var(--color-accent);
  font-size: 0.6rem;
  font-weight: 700;
}

.mock-doc-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.mock-doc-text strong {
  font-size: 0.76rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mock-doc-text small {
  font-size: 0.64rem;
  color: var(--color-text-light);
}

.mock-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
}

.mock-chip {
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 0.64rem;
  font-weight: 600;
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.mock-chip.green {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.mock-chip.soft {
  background: var(--color-surface-subtle);
  color: var(--color-text-muted);
}

.float-card {
  position: absolute;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-md);
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--color-text);
  white-space: nowrap;
}

.float-a {
  top: -16px;
  right: 18px;
}

.float-b {
  bottom: -18px;
  left: -10px;
}

.float-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--color-success-bg);
  color: var(--color-success);
  font-size: 0.72rem;
}

.float-icon.accent {
  background: var(--color-accent-soft);
  color: var(--color-accent);
}

/* Professions */
.professions {
  padding: 1.6rem 0;
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.55);
}

.professions-label {
  margin: 0 0 var(--space-3);
  text-align: center;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--color-text-light);
}

.profession-list {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin: 0;
  padding: 0;
}

.profession-list li {
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  background: #ffffff;
  font-size: 0.78rem;
  color: var(--color-text-muted);
}

/* Sections */
.section {
  padding: 4.5rem 0;
}

.section-alt {
  background: linear-gradient(180deg, rgba(234, 242, 248, 0.75), rgba(241, 245, 249, 0));
}

.section-head {
  max-width: 640px;
  margin: 0 auto 2.5rem;
  text-align: center;
}

.section-eyebrow {
  display: inline-block;
  margin-bottom: var(--space-3);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-accent);
}

.section-head h2,
.cta-panel h2 {
  margin: 0 0 var(--space-3);
  font-size: clamp(1.6rem, 2.6vw, 2.15rem);
  line-height: 1.15;
  letter-spacing: -0.02em;
}

.section-head p {
  margin: 0;
  font-size: 0.98rem;
  line-height: 1.65;
  color: var(--color-text-muted);
}

.section-note {
  margin: 1.6rem 0 0;
  text-align: center;
  font-size: 0.88rem;
  color: var(--color-text-light);
}

/* Steps */
.steps {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}

.step-card {
  position: relative;
  padding: 1.6rem 1.5rem 1.4rem;
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.step-number {
  display: block;
  margin-bottom: var(--space-3);
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: var(--color-primary);
}

.step-card h3 {
  margin: 0 0 var(--space-2);
  font-size: 1.02rem;
}

.step-card p {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.6;
  color: var(--color-text-muted);
}

.step-card::after {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: linear-gradient(180deg, var(--color-primary), #2d7fb8);
  opacity: 0.75;
}

/* Features */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
}

.feature-card {
  padding: 1.7rem;
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.feature-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
}

.feature-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  margin-bottom: var(--space-4);
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.feature-icon svg {
  width: 22px;
  height: 22px;
}

.feature-card h3 {
  margin: 0 0 var(--space-2);
  font-size: 1.05rem;
}

.feature-card p {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--color-text-muted);
}

/* Documents */
.doc-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
}

.doc-card {
  padding: 1.9rem;
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
}

.doc-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  margin-bottom: var(--space-4);
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.doc-icon.accent {
  background: var(--color-accent-soft);
  color: var(--color-accent);
}

.doc-icon svg {
  width: 23px;
  height: 23px;
}

.doc-card h3 {
  margin: 0 0 var(--space-2);
  font-size: 1.1rem;
}

.doc-card p {
  margin: 0 0 var(--space-4);
  font-size: 0.92rem;
  line-height: 1.65;
  color: var(--color-text-muted);
}

.file-chips {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  background: var(--color-surface-muted);
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.file-badge {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.file-badge.pdf {
  background: var(--color-accent-soft);
  color: var(--color-accent);
}

.file-badge.doc {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.editor-mock {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  background: var(--color-surface-muted);
}

.editor-line {
  height: 8px;
  border-radius: 4px;
  background: #e2eaf2;
}

.editor-line.bold {
  height: 11px;
  width: 45%;
  background: var(--color-primary-border);
}

.editor-line.short {
  width: 68%;
}

/* Open source */
.section-os {
  padding-top: 0;
}

.os-panel {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 2rem 2.2rem;
  border-radius: 18px;
  border: 1px solid var(--color-border);
  background: linear-gradient(120deg, #ffffff 30%, #eef4f9 100%);
  box-shadow: var(--shadow-sm);
}

.os-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 54px;
  height: 54px;
  flex-shrink: 0;
  border-radius: 14px;
  background: var(--color-sidebar);
  color: #ffffff;
}

.os-icon svg {
  width: 30px;
  height: 30px;
}

.os-copy {
  flex: 1;
  min-width: 0;
}

.os-copy .section-eyebrow {
  margin-bottom: 4px;
}

.os-copy h2 {
  margin: 0 0 6px;
  font-size: 1.4rem;
  letter-spacing: -0.02em;
}

.os-copy p {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.6;
  color: var(--color-text-muted);
}

.os-btn {
  flex-shrink: 0;
}

/* CTA */
.cta-section {
  padding: 0 0 4.5rem;
}

.cta-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-6);
  padding: 2.6rem 2.8rem;
  border-radius: 18px;
  background:
    radial-gradient(600px 260px at 90% -30%, rgba(45, 127, 184, 0.55), transparent 65%),
    linear-gradient(120deg, #0b2236 0%, #164e78 100%);
  color: #ffffff;
  box-shadow: 0 24px 50px -24px rgba(11, 34, 54, 0.45);
}

.cta-panel h2 {
  color: #ffffff;
  margin-bottom: var(--space-2);
}

.cta-panel p {
  margin: 0;
  color: rgba(255, 255, 255, 0.78);
  font-size: 0.95rem;
  max-width: 34rem;
}

.cta-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-3);
  flex-shrink: 0;
}

.cta-login {
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.85rem;
  text-decoration: none;
}

.cta-login:hover {
  color: #ffffff;
  text-decoration: underline;
}

/* Footer */
.site-footer {
  border-top: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.6);
  padding: 1.6rem 0;
}

.footer-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.footer-brand {
  gap: var(--space-2);
}

.footer-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.footer-note {
  margin: 0;
  font-size: 0.8rem;
  color: var(--color-text-light);
}

.footer-links {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
}

.footer-links a {
  color: var(--color-text-muted);
  font-weight: 500;
}

.footer-links a:hover {
  color: var(--color-primary);
}

.footer-sep {
  color: var(--color-border-strong);
}

/* Responsive */
@media (max-width: 960px) {
  .hero-grid {
    grid-template-columns: 1fr;
    gap: 3rem;
  }

  .hero-visual {
    max-width: 520px;
    margin: 0 auto;
    width: 100%;
  }

  .steps {
    grid-template-columns: 1fr;
  }

  .header-nav .nav-link {
    display: none;
  }
}

@media (max-width: 720px) {
  .container {
    padding: 0 var(--space-4);
  }

  .header-inner {
    height: 60px;
  }

  .header-nav {
    gap: var(--space-2);
  }

  .brand-name {
    font-size: 1rem;
  }

  .hero {
    padding: 2.5rem 0 2.5rem;
  }

  .hero h1 {
    font-size: clamp(2rem, 9vw, 2.6rem);
  }

  .hero-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-actions .btn {
    width: 100%;
  }

  .hero-checks {
    flex-direction: column;
  }

  .app-side {
    display: none;
  }

  .app-body {
    min-height: 0;
  }

  .float-b {
    left: 6px;
  }

  .feature-grid,
  .doc-grid {
    grid-template-columns: 1fr;
  }

  .section {
    padding: 3rem 0;
  }

  .cta-panel {
    flex-direction: column;
    align-items: stretch;
    padding: 2rem 1.6rem;
    text-align: left;
  }

  .cta-actions {
    align-items: stretch;
  }

  .cta-actions .btn {
    width: 100%;
  }

  .cta-login {
    text-align: center;
  }

  .os-panel {
    flex-direction: column;
    align-items: flex-start;
    padding: 1.7rem 1.5rem;
  }

  .os-btn {
    width: 100%;
  }

  .footer-inner {
    justify-content: center;
    text-align: center;
  }

  .footer-right {
    align-items: center;
  }
}

@media (max-width: 420px) {
  .header-login {
    padding: 0 0.55rem;
    font-size: 0.8rem;
  }

  .header-nav .btn-primary {
    padding: 0 0.7rem;
    font-size: 0.8rem;
  }

  .float-card {
    display: none;
  }
}
</style>

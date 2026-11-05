import { apiFetch } from '../api'

/**
 * Statische Fallback-Liste (gepflegt in backend/data/lehrplan/jobs.json).
 * Sie hält die Sidebar-Navigation auch bei API-Fehlern benutzbar;
 * massgeblich ist die Liste aus /api/lehrplan/jobs.
 */
export const fallbackJobs = [
  { code: 'AA', name: 'Anlagen- und Apparatebauer/in EFZ', accent: '#1d4f4b', accent_soft: '#e2ecea' },
  { code: 'KR', name: 'Konstrukteur/in EFZ', accent: '#3a3260', accent_soft: '#e7e4ef' },
  { code: 'MP', name: 'Mechanikpraktiker/in EBA', accent: '#6d4715', accent_soft: '#efe7dc' },
  { code: 'PR', name: 'Produktionsmechaniker/in EFZ', accent: '#6b2420', accent_soft: '#f0e4e2' },
  { code: 'PM', name: 'Polymechaniker/in EFZ', accent: '#232f47', accent_soft: '#e6eaf0' },
  { code: 'AM', name: 'Automatikmonteur/in EFZ', accent: '#2b383f', accent_soft: '#e7eaec' },
  { code: 'AU', name: 'Automatiker/in EFZ', accent: '#1f3c68', accent_soft: '#e4ebf3' },
  { code: 'ET', name: 'Elektroniker/in EFZ', accent: '#245029', accent_soft: '#e5ede5' }
]

let jobsPromise = null

/**
 * Holt die Berufsliste einmal pro Sitzung und cached das Promise, damit jede
 * AppLayout-Instanz sie nutzen kann, ohne neu zu laden.
 */
export function fetchLehrplanJobs() {
  if (!jobsPromise) {
    jobsPromise = apiFetch('/api/lehrplan/jobs').catch(() => null)
  }
  return jobsPromise
}

/**
 * Mappt einen user.job_title (Config-Form, z. B. «Polymechanikerin /
 * Polymechaniker EFZ») auf das Lehrplan-Kürzel («PM»). Gibt null zurück,
 * wenn keine Übereinstimmung gefunden wird.
 */
export function jobCodeForProfession(jobTitle) {
  if (!jobTitle) return null
  const norm = String(jobTitle)
    .toLowerCase()
    .replace(/\s*(efz|eba)\s*$/, '')
    .replace(/in\s*\//g, '/')
  for (const job of fallbackJobs) {
    const base = String(job.name)
      .toLowerCase()
      .replace(/\s*(efz|eba)\s*$/, '')
    const parts = base.split('/').map((p) => p.trim()).filter(Boolean)
    const re = new RegExp(`(^|[^\\p{L}])(${parts.map(escapeRegex).join('|')})([^\\p{L}]|$)`, 'u')
    if (re.test(norm)) return job.code
  }
  return null
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

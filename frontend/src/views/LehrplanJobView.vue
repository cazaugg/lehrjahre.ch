<script setup>
import Fuse from 'fuse.js'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiFetch } from '../api'
import { fallbackJobs } from '../utils/lehrplanJobs'

/**
 * Lehrplan-Ansicht (Portierung von memplan.ch): zeigt die
 * HKB → HK → LK → LZ Hierarchie eines MEM-Berufs mit Client-side-Suche
 * (Fuse.js), Toggle-Filter, Einklappen, Querverweisen und ?highlight=-Links.
 */
const route = useRoute()
const router = useRouter()

const code = computed(() => String(route.params.code || 'ET').toUpperCase())
const job = ref(null)
const hkbs = ref([])
const stats = ref(null)
const loading = ref(true)
const error = ref('')

// ---- State -------------------------------------------------------------------
const search = ref('')
const showLz = ref(true)
const showDesc = ref(true)
const showRefs = ref(false)

// Filter-Auswahl (Arrays wie die Sets in memplan: leer = kein Filter).
const filters = reactive({
  hkbs: [],
  hks: [],
  wahlPflicht: [],
  lernorte: [],
  semesters: []
})

// Einklapp-Zustand pro Sektion. Standard ist offen; «Alle einklappen» setzt
// alles zu, ein Klick speichert danach explizite Overrides pro Sektion.
const collapsedAll = ref(false)
const openState = reactive({})

function sectionId(type, id) {
  return `${type}-${String(id || '').replace(/[.\s]+/g, '_')}`
}

function isOpen(type, id) {
  const key = sectionId(type, id)
  // `key in openState` (statt hasOwnProperty) geht über den reaktiven
  // has-Trap, damit auch neu gesetzte Overrides ein Re-Render auslösen.
  return key in openState ? openState[key] : !collapsedAll.value
}

function toggleSection(type, id) {
  const key = sectionId(type, id)
  openState[key] = !isOpen(type, id)
}

function toggleAllSections() {
  collapsedAll.value = !collapsedAll.value
  resetOpenState()
}

function resetOpenState() {
  for (const key of Object.keys(openState)) delete openState[key]
}

// ---- Daten laden ----------------------------------------------------------------
const flatLZs = ref([])
const lernortOptions = ref([])
const semesterOptions = ref([])
const hksByHkb = ref({})
let totalLzCount = 0
let totalLkCount = 0

async function loadJob() {
  loading.value = true
  error.value = ''
  search.value = ''
  filters.hkbs = []
  filters.hks = []
  filters.wahlPflicht = []
  filters.lernorte = []
  filters.semesters = []
  showLz.value = true
  showDesc.value = true
  showRefs.value = false
  resetOpenState()
  try {
    const data = await apiFetch(`/api/lehrplan/${code.value}`)
    job.value = {
      ...data.job,
      accent: data.job?.accent || '#164e78',
      accentSoft: data.job?.accent_soft || '#eaf2f8'
    }
    stats.value = data.stats
    hkbs.value = sortTree(data.handlungskompetenzbereiche)
    buildIndexes(hkbs.value)
  } catch (e) {
    hkbs.value = []
    flatLZs.value = []
    lernortOptions.value = []
    semesterOptions.value = []
    hksByHkb.value = {}
    job.value = fallbackJobs.find((j) => j.code === code.value) || null
    stats.value = null
    error.value = e.message || 'Lehrplan konnte nicht geladen werden.'
  } finally {
    loading.value = false
  }
}

function minSemester(obj) {
  const s = obj.Semester
  return Math.min(...(Array.isArray(s) ? s : [s]).map(Number))
}

function sortTree(hkbList) {
  const sorted = [...hkbList].sort((a, b) =>
    String(a['ID HKB']).localeCompare(String(b['ID HKB']))
  )
  for (const hkb of sorted) {
    ;(hkb.handlungskompetenzen || []).sort((a, b) =>
      String(a['ID HK']).localeCompare(String(b['ID HK']))
    )
    for (const hk of hkb.handlungskompetenzen || []) {
      ;(hk.lernkriterien || []).sort((a, b) => {
        const diff = minSemester(a) - minSemester(b)
        return diff !== 0 ? diff : String(a['ID LK']).localeCompare(String(b['ID LK']))
      })
      for (const lk of hk.lernkriterien || []) {
        ;(lk.lernziele || []).sort((a, b) => minSemester(a) - minSemester(b))
      }
    }
  }
  return sorted
}

// Flache LZ-Liste + Fuse-Index + Optionen (wie in memplan).
let fuse = null

function buildIndexes(hkbList) {
  const flat = []
  const lernorte = new Set()
  const semesters = new Set()
  hksByHkb.value = {}

  for (const hkb of hkbList) {
    hksByHkb.value[hkb['ID HKB']] = (hkb.handlungskompetenzen || []).map((hk) => hk['ID HK'])
    for (const hk of hkb.handlungskompetenzen || []) {
      for (const lk of hk.lernkriterien || []) {
        lernorte.add(lk.Lernort)
        const lkSems = lk.Semester
        if (Array.isArray(lkSems)) lkSems.forEach((s) => semesters.add(s))
        for (const lz of lk.lernziele || []) {
          if (Array.isArray(lz.Semester)) lz.Semester.forEach((s) => semesters.add(s))
          else if (lz.Semester != null) semesters.add(lz.Semester)
          flat.push({ lz, lk, hk, hkb })
        }
      }
    }
  }

  flatLZs.value = flat
  totalLzCount = flat.length
  totalLkCount = hkbList.reduce(
    (sum, hkb) =>
      sum +
      (hkb.handlungskompetenzen || []).reduce(
        (sum2, hk) => sum2 + (hk.lernkriterien || []).length,
        0
      ),
    0
  )

  fuse = new Fuse(flat, {
    keys: [
      { name: 'lz.ID LZ', weight: 5 },
      { name: 'lk.ID LK', weight: 4 },
      { name: 'hk.ID HK', weight: 4 },
      { name: 'lz.Beschreibung LZ', weight: 1 },
      { name: 'lk.Beschreibung LK', weight: 0.5 },
      { name: 'hk.Name', weight: 0.3 },
      { name: 'hk.Beschreibung', weight: 0.3 },
      { name: 'hkb.Name', weight: 0.3 },
      { name: 'lz.Semester', weight: 0.2 },
      { name: 'lz.Taxonomie LZ', weight: 0.2 }
    ],
    threshold: 0.3,
    ignoreLocation: true,
    minMatchCharLength: 3
  })

  lernortOptions.value = [...lernorte].sort()
  semesterOptions.value = [...semesters]
    .sort((a, b) => Number(a) - Number(b))
    .map((s) => ({ value: s, label: String(s) }))
}

const hkbFilterOptions = computed(() =>
  hkbs.value.map((h) => ({
    value: h['ID HKB'],
    label: String(h['ID HKB']).split(' ').pop().toUpperCase()
  }))
)

// ---- Filter-Helfer --------------------------------------------------------------
function checkFilter(values, compare) {
  return values.length === 0 || values.includes(compare)
}

function lzSemesterMatches(lz) {
  if (filters.semesters.length === 0) return true
  const sems = lz.Semester
  if (Array.isArray(sems)) return sems.some((s) => filters.semesters.includes(s))
  return filters.semesters.includes(sems)
}

function lzMatchesFilters(item) {
  return (
    checkFilter(filters.hkbs, item.hkb['ID HKB']) &&
    checkFilter(filters.hks, item.hk['ID HK']) &&
    checkFilter(filters.wahlPflicht, item.hk['P/W']) &&
    checkFilter(filters.lernorte, item.lk.Lernort) &&
    lzSemesterMatches(item.lz)
  )
}

function toggleFilter(group, value) {
  const list = filters[group]
  const idx = list.indexOf(value)
  if (idx >= 0) list.splice(idx, 1)
  else list.push(value)

  // Wählt man einen Bereich, kaskadieren dessen HKs in den HK-Filter
  // (Verhalten von memplan).
  if (group === 'hkbs') {
    if (filters.hkbs.length === 0) {
      filters.hks = []
    } else {
      const visible = []
      for (const hkbId of filters.hkbs) {
        for (const hkId of hksByHkb.value[hkbId] || []) visible.push(hkId)
      }
      filters.hks = visible
    }
  }
}

function resetFilters() {
  search.value = ''
  filters.hkbs = []
  filters.hks = []
  filters.wahlPflicht = []
  filters.lernorte = []
  filters.semesters = []
  resetOpenState()
  setHighlight(null, false)
}

const searchWords = computed(() => {
  if (!search.value) return null
  return search.value
    .trim()
    .split(/\s+/)
    .filter((w) => w.length >= 2)
    .map((w) => w.toLowerCase())
})

// ---- Sicht-Aufbau (Port von memplan render()) -----------------------------------
function toCompetence(hk, lkGroups) {
  return { hk, lks: lkGroups }
}

// Flache LZ-Liste nach HKB → HK → LK gruppieren (für Code-Treffer und Fuse).
function groupFlat(items) {
  const hkbOrder = []
  const hkbMap = new Map()
  for (const item of items) {
    if (!lzMatchesFilters(item)) continue
    const hkbId = item.hkb['ID HKB']
    let hkbEntry = hkbMap.get(hkbId)
    if (!hkbEntry) {
      hkbEntry = { hkb: item.hkb, hkOrder: [], hkMap: new Map() }
      hkbMap.set(hkbId, hkbEntry)
      hkbOrder.push(hkbEntry)
    }
    const hkId = item.hk['ID HK']
    let hkEntry = hkbEntry.hkMap.get(hkId)
    if (!hkEntry) {
      hkEntry = { hk: item.hk, lkOrder: [], lkMap: new Map() }
      hkbEntry.hkMap.set(hkId, hkEntry)
      hkbEntry.hkOrder.push(hkEntry)
    }
    const lkId = item.lk['ID LK']
    let lkEntry = hkEntry.lkMap.get(lkId)
    if (!lkEntry) {
      lkEntry = { lk: item.lk, items: [] }
      hkEntry.lkMap.set(lkId, lkEntry)
      hkEntry.lkOrder.push(lkEntry)
    }
    lkEntry.items.push(item)
  }

  return hkbOrder.map((hkbEntry) => ({
    hkb: hkbEntry.hkb,
    hks: hkbEntry.hkOrder.map((hkEntry) => toCompetence(hkEntry.hk, hkEntry.lkOrder))
  }))
}

function countVisible(sections) {
  let count = 0
  for (const section of sections) {
    for (const comp of section.hks) {
      for (const lkv of comp.lks) count += showLz.value ? lkv.items.length : 1
    }
  }
  return count
}

// Baum durchgehen: ohne Suche via Filter, mit Suche via Wort-Abgleich in den
// Texten der Knoten (alle Suchwörter müssen irgendwo im Knoten vorkommen).
function walkTree() {
  const words = searchWords.value
  const nodeMatch = (texts) => {
    if (!words) return true
    for (const w of words) {
      if (!texts.some((t) => t != null && String(t).toLowerCase().includes(w))) {
        return false
      }
    }
    return true
  }

  let visibleCount = 0
  const sections = []

  for (const hkb of hkbs.value) {
    if (!checkFilter(filters.hkbs, hkb['ID HKB'])) continue
    const hkbMatches = nodeMatch([hkb['ID HKB'], hkb.Name])
    let hasVisibleHk = false
    const section = { hkb, hks: [] }

    for (const hk of hkb.handlungskompetenzen || []) {
      if (!checkFilter(filters.hks, hk['ID HK'])) continue
      if (!checkFilter(filters.wahlPflicht, hk['P/W'])) continue
      const hkMatches = nodeMatch([hk['ID HK'], hk.Name, hk.Beschreibung])
      let hasVisibleLk = false
      const lkGroups = []

      for (const lk of hk.lernkriterien || []) {
        if (!checkFilter(filters.lernorte, lk.Lernort)) continue
        const lkMatches = nodeMatch([lk['ID LK'], lk['Beschreibung LK'], lk.Lernort])
        const lzItems = flatLZs.value.filter(
          (x) =>
            x.lk['ID LK'] === lk['ID LK'] &&
            x.hk['ID HK'] === hk['ID HK'] &&
            lzSemesterMatches(x.lz) &&
            nodeMatch([
              x.lz['ID LZ'],
              x.lz['Beschreibung LZ'],
              x.lz.Semester,
              x.lz['Taxonomie LZ']
            ])
        )

        if (!search.value) {
          // Ohne Suche: LK erscheint, wenn passende Lernziele übrig bleiben
          // bzw. ohne LZ-Anzeige der Semester-Schnitt nicht leer ist.
          const hasLzs = (lk.lernziele || []).length > 0
          if (filters.semesters.length > 0) {
            if (showLz.value && hasLzs) {
              if (lzItems.length === 0) continue
            } else {
              const lkSems = lk.Semester || []
              if (!lkSems.some((s) => filters.semesters.includes(s))) continue
            }
          }
        } else if (!lkMatches && lzItems.length === 0) {
          continue
        }

        lkGroups.push({ lk, items: lzItems })
        hasVisibleLk = true
        visibleCount += showLz.value ? lzItems.length : 1
      }

      if (search.value) {
        // Im Suchmodus bleiben auch passende HK- resp. HKB-Überschriften sichtbar.
        if (hasVisibleLk || hkMatches) {
          section.hks.push(toCompetence(hk, lkGroups))
          hasVisibleHk = true
        }
      } else if (hasVisibleLk) {
        section.hks.push(toCompetence(hk, lkGroups))
        hasVisibleHk = true
      }
    }

    if (search.value) {
      // Im Suchmodus bleibt auch ein passender HKB-Kopf ohne Treffer in HKs sichtbar.
      if (hasVisibleHk || hkbMatches) sections.push(section)
    } else if (hasVisibleHk) {
      sections.push(section)
    }
  }

  return { sections, visibleCount }
}

const view = computed(() => {
  if (!hkbs.value.length) return { sections: [], visibleCount: 0 }

  if (search.value) {
    const q = search.value.trim().toLowerCase()

    // Stufe 1: exakte Code-Treffer (IDs) → gruppierte Darstellung.
    if (q.length >= 2) {
      const codeMatches = flatLZs.value.filter((item) =>
        [item.lz['ID LZ'], item.lk['ID LK'], item.hk['ID HK'], item.hkb['ID HKB']].some(
          (c) => c && String(c).toLowerCase().includes(q)
        )
      )
      if (codeMatches.length > 0) {
        const sections = groupFlat(codeMatches)
        return { sections, visibleCount: countVisible(sections) }
      }
    }

    // Stufe 2: alle Suchwörter müssen irgendwo im Knoten vorkommen.
    const walked = walkTree()
    if (walked.sections.length > 0) return walked

    // Stufe 3: Fuse-Fallback, bestes Score pro Item (volle Query + Wörter).
    const words = searchWords.value || []
    const scoreMap = new Map()
    const record = (res) => {
      for (const r of res) {
        const s = r.score ?? 0
        const prev = scoreMap.get(r.item)
        if (prev === undefined || s < prev) scoreMap.set(r.item, s)
      }
    }
    if (fuse && flatLZs.value.length) {
      record(fuse.search(search.value))
      for (const word of words) record(fuse.search(word))
      const scoredItems = [...scoreMap.entries()].sort((a, b) => a[1] - b[1]).map((e) => e[0])
      const sections = groupFlat(scoredItems)
      return { sections, visibleCount: countVisible(sections), fuse: true }
    }
    return walked
  }

  return walkTree()
})

const totalCount = computed(() => {
  if (!hkbs.value.length) return 0
  return showLz.value ? totalLzCount : totalLkCount
})

// ---- Text-Helfer -----------------------------------------------------------------
function escapeHtml(text) {
  if (text == null) return ''
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function highlight(text) {
  if (!search.value) return escapeHtml(text)
  const escapeRe = (w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const words = (searchWords.value || []).map(escapeRe)
  if (words.length === 0) return escapeHtml(text)
  let result = escapeHtml(text)
  for (const word of words) {
    result = result.replace(new RegExp(`(${word})`, 'gi'), '<mark class="search-hit">$1</mark>')
  }
  return result
}

function formatSemesters(arr) {
  if (!arr || arr.length === 0) return ''
  const nums = arr.map(Number).sort((a, b) => a - b)
  const ranges = []
  let start = nums[0]
  let end = nums[0]
  for (let i = 1; i < nums.length; i++) {
    if (nums[i] === end + 1) {
      end = nums[i]
    } else {
      ranges.push(start === end ? `${start}` : `${start}-${end}`)
      start = end = nums[i]
    }
  }
  ranges.push(start === end ? `${start}` : `${start}-${end}`)
  return ranges.join(', ')
}

// ---- Highlight-Deep-Links (?highlight=lk-…, hk-…, lz-…) ---------------------------
const resultsEl = ref(null)

function setHighlight(value, push = true) {
  const query = { ...route.query }
  if (value) query.highlight = value
  else delete query.highlight
  const method = push ? router.push : router.replace
  method({ path: route.path, query }).catch(() => {})
}

function applyHighlight() {
  const hl = route.query.highlight
  if (!hl || !resultsEl.value) return
  const root = resultsEl.value
  const hlValue = String(hl)
  let el = null
  if (hlValue.startsWith('lk-') || hlValue.startsWith('hk-')) {
    el = root.querySelector(`#${CSS.escape(hlValue)}`)
  } else if (hlValue.startsWith('lz-')) {
    el = root.querySelector(`[data-lz-id="${CSS.escape(hlValue.slice(3))}"]`)
  }
  if (!el) return

  // Alle Vorfahren aufklappen (Sektions-Overrides setzen).
  let current = el.parentElement
  while (current && current !== root) {
    if (
      current.classList.contains('lk-content') ||
      current.classList.contains('competence-content') ||
      current.classList.contains('subject-content')
    ) {
      if (current.dataset.sectionId) openState[current.dataset.sectionId] = true
    }
    current = current.parentElement
  }
  if (el.classList.contains('lk-header') && el.dataset.sectionId) {
    openState[el.dataset.sectionId] = true
  }

  nextTick(() => {
    el.classList.remove('highlighted')
    // Reflow erzwingen, damit die Pulser-Animation erneut startet.
    void el.offsetWidth
    el.classList.add('highlighted')
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

watch(
  [() => route.query.highlight, () => hkbs.value],
  async () => {
    await nextTick()
    if (route.query.highlight) applyHighlight()
  },
  { immediate: true }
)

function handleRefClick(e) {
  const link = e.target.closest('.highlight-link')
  if (!link) return
  e.preventDefault()
  const value = link.getAttribute('href').replace('?highlight=', '')
  setHighlight(value)
}

const jobVars = computed(() => ({
  '--job-accent': job.value?.accent || 'var(--color-primary)',
  '--job-accent-soft': job.value?.accentSoft || 'var(--color-primary-soft)'
}))

const subtitle = computed(() => {
  if (stats.value) {
    return `${stats.value.lz_count} Lernziele, ${stats.value.lk_count} Leistungskriterien in ${stats.value.hkb_count} Handlungskompetenzbereichen und ${stats.value.hk_count} Handlungskompetenzen`
  }
  return ''
})

const jobLinks = computed(() => {
  const links = []
  if (job.value?.verordnung) links.push({ label: 'Verordnung', url: job.value.verordnung })
  if (job.value?.beccPlan) links.push({ label: 'Bildungsplan', url: job.value.beccPlan })
  if (job.value?.futuremem) links.push({ label: 'Qualifikationsprofil', url: job.value.futuremem })
  return links
})

onMounted(loadJob)
watch(code, () => {
  if (!loading.value && route.name === 'lehrplan') loadJob()
})
</script>

<template>
  <div class="lehrplan-page" :style="jobVars">
    <div class="page-header">
      <div>
        <div class="eyebrow">
          Lehrplan · {{ code }}<template v-if="job"> · {{ job.name }}</template>
        </div>
        <h1 class="page-title">{{ job?.title || `Lernziele ${job?.name}` || 'Lehrplan' }}</h1>
        <p class="page-subtitle">{{ subtitle || '&nbsp;' }}</p>
      </div>
      <div class="flex-gap" v-if="jobLinks.length">
        <a
          v-for="link in jobLinks"
          :key="link.url"
          class="job-link"
          :href="link.url"
          target="_blank"
          rel="noopener"
        >
          {{ link.label }} ↗
        </a>
      </div>
    </div>

    <div v-if="loading" class="card text-muted">Lade Lehrplan-Daten …</div>
    <div v-else-if="error" class="alert alert-error">
      {{ error }}
      <div class="text-muted" style="margin-top: 0.5rem">
        Über die Navigation kannst du einen anderen Beruf wählen.
      </div>
    </div>
    <template v-else>
      <div class="controls-card">
        <div class="search-row">
          <input
            v-model="search"
            type="search"
            class="form-control search-input"
            placeholder="Suchen nach ID, Name oder Beschreibung …"
          />
          <span class="count text-muted">{{ view.visibleCount }} von {{ totalCount }}</span>
        </div>
        <div class="filter-row">
          <div class="filter-group">
            <label>Alle</label>
            <div class="options">
              <button type="button" class="filter-btn" @click="toggleAllSections">
                {{ collapsedAll ? 'Alle ausklappen' : 'Alle einklappen' }}
              </button>
            </div>
          </div>
          <div class="filter-group">
            <label>Bereich</label>
            <div class="options">
              <button
                v-for="opt in hkbFilterOptions"
                :key="opt.value"
                type="button"
                class="filter-btn"
                :class="{ active: filters.hkbs.includes(opt.value) }"
                :title="opt.label"
                @click="toggleFilter('hkbs', opt.value)"
              >
                {{ opt.label }}
              </button>
            </div>
          </div>
          <div class="filter-group">
            <label>Typ</label>
            <div class="options">
              <button
                type="button"
                class="filter-btn"
                :class="{ active: filters.wahlPflicht.includes('P') }"
                @click="toggleFilter('wahlPflicht', 'P')"
              >
                Pflicht
              </button>
              <button
                type="button"
                class="filter-btn"
                :class="{ active: filters.wahlPflicht.includes('W') }"
                @click="toggleFilter('wahlPflicht', 'W')"
              >
                Wahl
              </button>
            </div>
          </div>
          <div class="filter-group">
            <label>Lernort</label>
            <div class="options">
              <button
                v-for="opt in lernortOptions"
                :key="opt"
                type="button"
                class="filter-btn"
                :class="{ active: filters.lernorte.includes(opt) }"
                @click="toggleFilter('lernorte', opt)"
              >
                {{ opt }}
              </button>
            </div>
          </div>
          <div class="filter-group">
            <label>Semester</label>
            <div class="options">
              <button
                v-for="opt in semesterOptions"
                :key="opt.value"
                type="button"
                class="filter-btn"
                :class="{ active: filters.semesters.includes(opt.value) }"
                @click="toggleFilter('semesters', opt.value)"
              >
                {{ opt.label }}
              </button>
            </div>
          </div>
          <div class="filter-group">
            <label>Lernziele</label>
            <div class="options">
              <button
                type="button"
                class="filter-btn toggle-btn"
                :class="{ active: showLz }"
                @click="showLz = !showLz"
              >
                {{ showLz ? 'An' : 'Aus' }}
              </button>
            </div>
          </div>
          <div class="filter-group">
            <label>Beschreibung</label>
            <div class="options">
              <button
                type="button"
                class="filter-btn toggle-btn"
                :class="{ active: showDesc }"
                @click="showDesc = !showDesc"
              >
                {{ showDesc ? 'An' : 'Aus' }}
              </button>
            </div>
          </div>
          <div class="filter-group">
            <label>Querverweise</label>
            <div class="options">
              <button
                type="button"
                class="filter-btn toggle-btn"
                :class="{ active: showRefs }"
                @click="showRefs = !showRefs"
              >
                {{ showRefs ? 'An' : 'Aus' }}
              </button>
            </div>
          </div>
          <div class="filter-group">
            <label>Reset</label>
            <div class="options">
              <button type="button" class="filter-btn clear-btn" @click="resetFilters">
                Filter zurücksetzen
              </button>
            </div>
          </div>
        </div>
      </div>

      <div ref="resultsEl" class="results" @click="handleRefClick">
        <div
          v-for="section in view.sections"
          :key="section.hkb['ID HKB']"
          class="subject"
        >
          <div
            class="subject-header"
            :class="{ open: isOpen('hkb', section.hkb['ID HKB']) }"
            @click="toggleSection('hkb', section.hkb['ID HKB'])"
          >
            <span class="arrow">▶</span>
            <span class="code code-hkb">{{
              String(section.hkb['ID HKB']).split(' ').pop().toUpperCase()
            }}</span>
            <span class="name" v-html="highlight(section.hkb.Name)"></span>
          </div>
          <div
            class="subject-content"
            :class="{ open: isOpen('hkb', section.hkb['ID HKB']) }"
            :data-section-id="sectionId('hkb', section.hkb['ID HKB'])"
          >
            <div
              v-for="comp in section.hks"
              :key="comp.hk['ID HK']"
              class="competence"
            >
              <div
                :id="sectionId('hk', comp.hk['ID HK'])"
                class="competence-header"
                :class="{ open: isOpen('hk', comp.hk['ID HK']) }"
                @click="toggleSection('hk', comp.hk['ID HK'])"
              >
                <span class="arrow">▶</span>
                <span class="code" v-html="highlight(comp.hk['ID HK'])"></span>
                <span class="name" v-html="highlight(comp.hk.Name)"></span>
                <span
                  class="hk-pw-badge"
                  :class="comp.hk['P/W'] === 'W' ? 'optional' : 'mandatory'"
                >
                  {{ comp.hk['P/W'] === 'W' ? 'Wahl' : 'Pflicht' }}
                </span>
              </div>
              <div
                class="competence-content"
                :class="{ open: isOpen('hk', comp.hk['ID HK']) }"
                :data-section-id="sectionId('hk', comp.hk['ID HK'])"
              >
                <p v-if="showDesc && comp.hk.Beschreibung" class="competence-desc">
                  {{ comp.hk.Beschreibung }}
                </p>
                <div v-for="lkv in comp.lks" :key="lkv.lk['ID LK']" class="lk">
                  <div
                    :id="sectionId('lk', lkv.lk['ID LK'])"
                    class="lk-header"
                    :class="{ open: isOpen('lk', lkv.lk['ID LK']) }"
                    @click="toggleSection('lk', lkv.lk['ID LK'])"
                  >
                    <span class="arrow">▶</span>
                    <span class="lk-code" v-html="highlight(lkv.lk['ID LK'])"></span>
                    <span class="lk-desc" v-html="highlight(lkv.lk['Beschreibung LK'])"></span>
                    <span class="lernort-badge" :class="'lernort-' + String(lkv.lk.Lernort).toLowerCase()">
                      {{ lkv.lk.Lernort }}
                    </span>
                    <span v-if="formatSemesters(lkv.lk.Semester)" class="semester-range">
                      {{ formatSemesters(lkv.lk.Semester) }}
                    </span>
                  </div>
                  <div
                    class="lk-content"
                    :class="{ open: isOpen('lk', lkv.lk['ID LK']) }"
                    :data-section-id="sectionId('lk', lkv.lk['ID LK'])"
                  >
                    <template v-if="showLz">
                      <div
                        v-for="item in lkv.items"
                        :key="item.lz['ID LZ']"
                        class="lernziel-row"
                        :data-lz-id="item.lz['ID LZ']"
                      >
                        <span class="lz-id" v-html="highlight(item.lz['ID LZ'])"></span>
                        <span class="lz-desc">
                          <span v-html="highlight(item.lz['Beschreibung LZ'])"></span>
                          <span
                            v-if="showRefs && item.lz.duplicated"
                            class="lz-refs"
                          >
                            Dieses Lernziel gehört ebenfalls zum Leistungskriterium:
                            <a
                              v-for="refId in item.lz.duplicated"
                              :key="refId"
                              :href="'?highlight=' + sectionId('lk', refId)"
                              class="highlight-link lk-code"
                            >{{ refId }}</a>
                          </span>
                        </span>
                        <span class="semester-badge">{{
                          Array.isArray(item.lz.Semester)
                            ? item.lz.Semester.join(', ')
                            : item.lz.Semester
                        }}</span>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="view.sections.length === 0" class="no-results empty-state">
          <strong>Keine Lernziele gefunden</strong><br />
          Versuche andere Suchbegriffe oder filtere weniger streng.
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.lehrplan-page {
  --hit-bg: rgba(255, 217, 102, 0.45);
}

/* Kopf */
.eyebrow {
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--job-accent);
  margin-bottom: 0.2rem;
}

.job-link {
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.25rem 0.6rem;
  background: var(--color-surface);
}

.job-link:hover {
  color: var(--color-primary);
  border-color: var(--color-primary);
  text-decoration: none;
}

/* Filter- und Suchleiste */
.controls-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
}

.search-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}

.search-input {
  flex: 1;
  min-width: 240px;
  height: 36px;
}

.count {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3) var(--space-4);
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.filter-group > label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-light);
}

.options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.filter-btn {
  border: 1px solid var(--color-border-strong);
  background: var(--color-surface);
  color: var(--color-text);
  font-size: 0.78rem;
  font-weight: 500;
  font-family: inherit;
  border-radius: 999px;
  padding: 0.2rem 0.6rem;
  cursor: pointer;
  transition: all 0.12s ease;
}

.filter-btn:hover {
  border-color: var(--job-accent);
  color: var(--job-accent);
}

.filter-btn.active {
  background: var(--job-accent);
  border-color: var(--job-accent);
  color: #ffffff;
}

.clear-btn {
  border-color: var(--color-border-strong);
  color: var(--color-text-muted);
}

.clear-btn:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
  background: var(--color-danger-bg);
}

/* Hierarchie */
.subject {
  margin-bottom: var(--space-4);
}

.subject-header,
.competence-header,
.lk-header {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  cursor: pointer;
  user-select: none;
}

.subject-header {
  background: var(--job-accent-soft);
  border-left: 4px solid var(--job-accent);
  border-radius: var(--radius-sm);
  padding: 0.6rem var(--space-3);
  margin-bottom: var(--space-1);
}

.competence-header {
  border-bottom: 1px solid var(--color-border);
  padding: 0.55rem var(--space-2);
  margin-bottom: var(--space-1);
  border-radius: var(--radius-sm);
}

.competence-header:hover,
.subject-header:hover,
.lk-header:hover {
  background: var(--color-surface-subtle);
}

.subject-header:hover {
  background: var(--job-accent-soft);
}

.arrow {
  font-size: 0.65rem;
  color: var(--color-text-light);
  transition: transform 0.15s ease;
  flex-shrink: 0;
}

.open > .arrow {
  transform: rotate(90deg);
}

.code {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--job-accent);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.05rem 0.4rem;
  white-space: nowrap;
}

.code-hkb {
  background: var(--job-accent);
  border-color: var(--job-accent);
  color: #ffffff;
}

.subject-header .name {
  font-weight: 600;
  color: var(--color-text);
  font-size: 0.98rem;
}

.competence-header .name {
  color: var(--color-text);
  font-size: 0.92rem;
}

.hk-pw-badge {
  margin-left: auto;
  flex-shrink: 0;
  font-size: 0.7rem;
  font-weight: 700;
  border-radius: 999px;
  padding: 0.12rem 0.55rem;
}

.hk-pw-badge.mandatory {
  background: var(--color-success-bg);
  color: var(--color-success);
  border: 1px solid var(--color-success-border);
}

.hk-pw-badge.optional {
  background: var(--color-warning-bg);
  color: var(--color-warning);
  border: 1px solid var(--color-warning-border);
}

.subject-content,
.competence-content,
.lk-content {
  display: none;
}

.subject-content.open,
.competence-content.open,
.lk-content.open {
  display: block;
}

.subject-content {
  padding-left: var(--space-3);
}

.subject-content .competence-content {
  padding: var(--space-2) var(--space-3) 0 var(--space-4);
}

.competence-desc {
  font-size: 0.84rem;
  color: var(--color-text-muted);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  margin: 0 0 var(--space-2) 0;
}

.lk {
  margin-bottom: var(--space-2);
}

.lk-header {
  gap: var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.45rem var(--space-3);
  margin-bottom: var(--space-1);
  background: var(--color-surface-muted);
  flex-wrap: wrap;
}

.lk-code {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--color-primary);
  white-space: nowrap;
}

.lk-desc {
  color: var(--color-text);
  font-size: 0.86rem;
  flex: 1;
  min-width: 200px;
}

.lernort-badge {
  flex-shrink: 0;
  font-size: 0.7rem;
  font-weight: 700;
  border-radius: 999px;
  padding: 0.12rem 0.55rem;
  border: 1px solid transparent;
}

.lernort-be {
  background: var(--color-success-bg);
  color: var(--color-success);
  border-color: var(--color-success-border);
}

.lernort-bfs {
  background: var(--color-info-bg);
  color: var(--color-info);
  border-color: var(--color-info-border);
}

.lernort-ük,
.lernort-uk {
  background: var(--color-warning-bg);
  color: var(--color-warning);
  border-color: var(--color-warning-border);
}

.semester-range {
  font-family: var(--font-mono);
  font-size: 0.74rem;
  font-weight: 600;
  color: var(--color-text-light);
  white-space: nowrap;
}

/* Lernziel-Zeilen */
.lernziel-row {
  display: grid;
  grid-template-columns: minmax(90px, max-content) 1fr auto;
  gap: var(--space-2);
  align-items: baseline;
  padding: var(--space-2) var(--space-3);
  border-top: 1px solid var(--color-border);
}

.lernziel-row:first-child {
  border-top: none;
}

.lz-id {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--color-text-light);
  white-space: nowrap;
}

.lz-desc {
  font-size: 0.87rem;
  color: var(--color-text);
}

.lz-refs {
  display: block;
  font-size: 0.78rem;
  color: var(--color-text-muted);
  margin-top: 0.25rem;
}

.lz-refs a.highlight-link {
  margin-left: 0.3rem;
}

.semester-badge {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--color-text-muted);
  background: var(--color-surface-subtle);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.1rem 0.45rem;
  white-space: nowrap;
}

/* Suchtreffer und Highlight-Ziel */
:deep(.search-hit) {
  background: var(--hit-bg);
  border-radius: 2px;
  padding: 0 1px;
}

:deep(.highlighted) {
  animation: highlight-pulse 2.2s ease-out;
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 3px var(--job-accent);
}

@keyframes highlight-pulse {
  0% {
    box-shadow: 0 0 0 6px color-mix(in srgb, var(--job-accent) 45%, transparent);
  }
  100% {
    box-shadow: 0 0 0 3px var(--job-accent);
  }
}

.no-results {
  background: var(--color-surface);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-md);
}

@media (max-width: 720px) {
  .lernziel-row {
    grid-template-columns: 1fr;
    gap: var(--space-1);
  }

  .lz-desc {
    order: 1;
  }

  .semester-badge {
    order: 2;
    justify-self: start;
  }

  .lz-id {
    order: 3;
  }
}
</style>

<script setup>
import Fuse from 'fuse.js'
import { computed, reactive, ref, watch } from 'vue'
import { apiFetch } from '../../api'
import { fallbackJobs, fetchLehrplanJobs, jobCodeForProfession } from '../../utils/lehrplanJobs'
import ModalDialog from './ModalDialog.vue'

/**
 * Lernziel-Picker für die Projektplanung: Modal mit Berufswahl, Suche,
 * Toggle-Filter und HKB → HK → LK → LZ-Baum mit Checkboxen (Anlehnung an
 * die Lehrplan-Ansicht). Gibt beim Übernehmen die gewählten Ziele als
 * { id, description, lkId, lernort, semesters, jobCode } zurück.
 */
const props = defineProps({
  show: { type: Boolean, default: false },
  /** Vorausgewählter Beruf (Kürzel wie «PM») oder «». */
  defaultJobCode: { type: String, default: '' },
  /** Bereits im Projekt erfasste Ziel-Strings; deren Checkboxen sind deaktiviert. */
  existing: { type: Array, default: () => [] }
})

const emit = defineEmits(['close', 'confirm'])

// ---- Berufe -------------------------------------------------------------------
const jobs = ref(fallbackJobs)
fetchLehrplanJobs().then((data) => {
  if (Array.isArray(data) && data.length) {
    jobs.value = data.map((j) => ({ ...j, accent_soft: j.accent_soft || j.accentSoft }))
  } else if (data && data.jobs) {
    jobs.value = data.jobs
  }
})

const code = ref('')

const selectedExisting = computed(() => new Set(props.existing.map(String)))

// ---- Baumdaten (per Beruf gecacht; Daten sind statisch) ------------------------
const treeCache = new Map()
const hkbs = ref([])
const loading = ref(false)
const error = ref('')

const flatLZs = ref([])
const lernortOptions = ref([])
const semesterOptions = ref([])
let fuse = null

watch(
  () => props.show,
  (show) => {
    if (show) initialiseSelection()
  },
  { immediate: true }
)

function initialiseSelection() {
  error.value = ''
  selected.value = []
  const def = String(props.defaultJobCode || '').toUpperCase()
  const valid = jobs.value.some((j) => j.code === def)
  const next = valid ? def : (jobs.value[0]?.code ?? '')
  const changed = code.value !== next
  code.value = next
  if (!changed || hkbs.value.length === 0) {
    loadTree(next)
  }
}

watch(code, (c) => {
  if (c) loadTree(c)
})

async function loadTree(c) {
  search.value = ''
  resetFilters()
  resetOpenState()
  if (!c) {
    hkbs.value = []
    flatLZs.value = []
    return
  }
  if (treeCache.has(c)) {
    applyTree(c, treeCache.get(c))
    return
  }
  loading.value = true
  try {
    const data = await apiFetch(`/api/lehrplan/${c}`)
    treeCache.set(c, data.handlungskompetenzbereiche)
    applyTree(c, data.handlungskompetenzbereiche)
  } catch (e) {
    hkbs.value = []
    flatLZs.value = []
    error.value = e.message || 'Lehrplan konnte nicht geladen werden.'
  } finally {
    loading.value = false
  }
}

function applyTree(c, list) {
  hkbs.value = sortTree(list || [])
  buildIndexes(hkbs.value)
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

function buildIndexes(hkbList) {
  const flat = []
  const lernorte = new Set()
  const semesters = new Set()
  for (const hkb of hkbList) {
    for (const hk of hkb.handlungskompetenzen || []) {
      for (const lk of hk.lernkriterien || []) {
        lernorte.add(lk.Lernort)
        for (const s of lk.Semester || []) semesters.add(s)
        for (const lz of lk.lernziele || []) {
          if (Array.isArray(lz.Semester)) lz.Semester.forEach((s) => semesters.add(s))
          else if (lz.Semester != null) semesters.add(lz.Semester)
          flat.push({ lz, lk, hk, hkb })
        }
      }
    }
  }
  flatLZs.value = flat

  fuse = new Fuse(flat, {
    keys: [
      { name: 'lz.ID LZ', weight: 5 },
      { name: 'lk.ID LK', weight: 4 },
      { name: 'hk.ID HK', weight: 4 },
      { name: 'lz.Beschreibung LZ', weight: 1 },
      { name: 'lk.Beschreibung LK', weight: 0.5 },
      { name: 'hk.Name', weight: 0.3 },
      { name: 'hkb.Name', weight: 0.3 }
    ],
    threshold: 0.3,
    ignoreLocation: true,
    minMatchCharLength: 3
  })

  lernortOptions.value = [...lernorte].sort()
  semesterOptions.value = [...semesters].sort((a, b) => Number(a) - Number(b))
}

// ---- Suche & Filter --------------------------------------------------------------
const search = ref('')
const filters = reactive({
  wahlPflicht: [],
  lernorte: [],
  semesters: []
})

function checkFilter(values, compare) {
  return values.length === 0 || values.includes(compare)
}

function lzSemesterMatches(lz) {
  if (filters.semesters.length === 0) return true
  const sems = lz.Semester
  if (Array.isArray(sems)) return sems.some((s) => filters.semesters.includes(s))
  return filters.semesters.includes(sems)
}

function toggleFilter(group, value) {
  const list = filters[group]
  const idx = list.indexOf(value)
  if (idx >= 0) list.splice(idx, 1)
  else list.push(value)
}

function resetFilters() {
  filters.wahlPflicht = []
  filters.lernorte = []
  filters.semesters = []
}

const searchWords = computed(() => {
  if (!search.value) return null
  return search.value
    .trim()
    .split(/\s+/)
    .filter((w) => w.length >= 2)
    .map((w) => w.toLowerCase())
})

// ---- Einklappen -------------------------------------------------------------------
// Standard zugeklappt (kompakt im Modal); im Suchmodus werden Treffer-Sektionen erzwungen offen.
const openState = reactive({})

function isOpen(id) {
  const key = String(id)
  return key in openState ? openState[key] : false
}

function toggleSection(id) {
  const key = String(id)
  openState[key] = !isOpen(key)
}

function resetOpenState() {
  for (const key of Object.keys(openState)) delete openState[key]
}

// ---- Sicht-Aufbau (Port aus der Lehrplan-Ansicht) --------------------------------
function toCompetence(hk, lkGroups) {
  return { hk, lks: lkGroups }
}

// Flache LZ-Liste nach HKB → HK → LK gruppieren (für Code-Treffer und Fuse).
function groupFlat(items) {
  const hkbOrder = []
  const hkbMap = new Map()
  for (const item of items) {
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

// Baum durchgehen: ohne Suche via Filter, mit Suche via Wort-Abgleich.
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

  const sections = []

  for (const hkb of hkbs.value) {
    const hkbMatches = nodeMatch([hkb['ID HKB'], hkb.Name])
    let hasVisibleHk = false
    const section = { hkb, hks: [] }

    for (const hk of hkb.handlungskompetenzen || []) {
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
            checkFilter(filters.wahlPflicht, x.hk['P/W']) &&
            lzSemesterMatches(x.lz) &&
            nodeMatch([
              x.lz['ID LZ'],
              x.lz['Beschreibung LZ'],
              x.lz.Semester,
              x.lz['Taxonomie LZ']
            ])
        )

        if (search.value) {
          if (!lkMatches && lzItems.length === 0) continue
        } else if (lzItems.length === 0) {
          continue
        }

        lkGroups.push({ lk, items: lzItems })
        hasVisibleLk = true
      }

      if (search.value) {
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
      if (hasVisibleHk || hkbMatches) sections.push(section)
    } else if (hasVisibleHk) {
      sections.push(section)
    }
  }

  return sections
}

const view = computed(() => {
  if (!hkbs.value.length) return []

  if (search.value) {
    const q = search.value.trim().toLowerCase()

    // Stufe 1: exakte Code-Treffer (IDs) → gruppiert.
    if (q.length >= 2) {
      const codeMatches = flatLZs.value.filter((item) =>
        [item.lz['ID LZ'], item.lk['ID LK'], item.hk['ID HK'], item.hkb['ID HKB']].some(
          (c) => c && String(c).toLowerCase().includes(q)
        )
      )
      if (codeMatches.length > 0) return groupFlat(codeMatches)
    }

    // Stufe 2: alle Suchwörter müssen irgendwo im Knoten vorkommen.
    const walked = walkTree()
    if (walked.length > 0) return walked

    // Stufe 3: Fuse-Fallback.
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
      return groupFlat(scoredItems)
    }
    return walked
  }

  return walkTree()
})

// ---- Auswahl ---------------------------------------------------------------------
const selected = ref([])

function isSelected(id) {
  return selected.value.includes(id)
}

function toggleLz(id) {
  const idx = selected.value.indexOf(id)
  if (idx >= 0) selected.value.splice(idx, 1)
  else selected.value.push(id)
}

const selectedCount = computed(() => selected.value.length)

function confirmSelection() {
  const picked = selected.value
    .map((id) => flatLZs.value.find((x) => String(x.lz['ID LZ']) === id))
    .filter(Boolean)
    .map((x) => ({
      id: String(x.lz['ID LZ']),
      description: x.lz['Beschreibung LZ'],
      lkId: x.lk['ID LK'],
      lernort: x.lk.Lernort,
      semesters: x.lz.Semester,
      jobCode: code.value
    }))
  emit('confirm', picked)
  emit('close')
}

const jobName = computed(() => jobs.value.find((j) => j.code === code.value)?.name || '')

// Wiederverwendete Semester-Formatierung (aus der Lehrplan-Ansicht).
function formatSemesters(arr) {
  if (!arr || arr.length === 0) return ''
  if (!Array.isArray(arr)) return String(arr)
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
</script>

<template>
  <ModalDialog :show="show" title="Lernziel aus dem Lehrplan wählen" width="880px" @close="emit('close')">
    <div class="gp-body">
      <!-- Berufswahl -->
      <div class="gp-job-row">
        <label class="gp-lab" for="gp-job">Beruf</label>
        <select id="gp-job" v-model="code" class="form-control">
          <option v-for="j in jobs" :key="j.code" :value="j.code">{{ j.name }}</option>
        </select>
      </div>

      <!-- Suche + Filter -->
      <div class="gp-controls">
        <div class="gp-search-row">
          <input
            v-model="search"
            type="search"
            class="form-control gp-search"
            placeholder="Suchen nach ID, Name oder Beschreibung …"
          />
        </div>
        <div class="gp-filter-row">
          <div class="gp-filter-group">
            <label>Typ</label>
            <div class="gp-options">
              <button
                type="button"
                class="gp-pill"
                :class="{ active: filters.wahlPflicht.includes('P') }"
                @click="toggleFilter('wahlPflicht', 'P')"
              >
                Pflicht
              </button>
              <button
                type="button"
                class="gp-pill"
                :class="{ active: filters.wahlPflicht.includes('W') }"
                @click="toggleFilter('wahlPflicht', 'W')"
              >
                Wahl
              </button>
            </div>
          </div>
          <div class="gp-filter-group">
            <label>Lernort</label>
            <div class="gp-options">
              <button
                v-for="opt in lernortOptions"
                :key="opt"
                type="button"
                class="gp-pill"
                :class="{ active: filters.lernorte.includes(opt) }"
                @click="toggleFilter('lernorte', opt)"
              >
                {{ opt }}
              </button>
            </div>
          </div>
          <div class="gp-filter-group">
            <label>Semester</label>
            <div class="gp-options">
              <button
                v-for="opt in semesterOptions"
                :key="opt.value"
                type="button"
                class="gp-pill"
                :class="{ active: filters.semesters.includes(opt.value) }"
                @click="toggleFilter('semesters', opt.value)"
              >
                {{ opt.label }}
              </button>
            </div>
          </div>
          <div class="gp-filter-group">
            <label>Reset</label>
            <div class="gp-options">
              <button type="button" class="gp-pill gp-clear" @click="resetFilters(); search = ''">
                Filter zurücksetzen
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Baum -->
      <div v-if="loading" class="text-muted gp-loading">Lade Lehrplan-Daten …</div>
      <div v-else-if="error" class="alert alert-error">{{ error }}</div>
      <div v-else class="gp-tree">
        <div v-for="section in view" :key="section.hkb['ID HKB']" class="gp-subject">
          <div
            class="gp-head gp-subject-head"
            :class="{ open: isOpen(section.hkb['ID HKB']) || !!search }"
            @click="toggleSection(section.hkb['ID HKB'])"
          >
            <span class="arrow">▶</span>
            <span class="gp-code-b">{{
              String(section.hkb['ID HKB']).split(' ').pop().toUpperCase()
            }}</span>
            <span class="gp-name">{{ section.hkb.Name }}</span>
          </div>
          <div
            class="gp-subject-content"
            :class="{ open: isOpen(section.hkb['ID HKB']) || !!search }"
          >
            <div v-for="comp in section.hks" :key="comp.hk['ID HK']" class="gp-competence">
              <div
                class="gp-head gp-competence-head"
                :class="{ open: isOpen(comp.hk['ID HK']) || !!search }"
                @click="toggleSection(comp.hk['ID HK'])"
              >
                <span class="arrow">▶</span>
                <span class="gp-code">{{ comp.hk['ID HK'] }}</span>
                <span class="gp-name-sm">{{ comp.hk.Name }}</span>
                <span
                  class="gp-pw"
                  :class="comp.hk['P/W'] === 'W' ? 'optional' : 'mandatory'"
                >
                  {{ comp.hk['P/W'] === 'W' ? 'Wahl' : 'Pflicht' }}
                </span>
              </div>
              <div
                class="gp-competence-content"
                :class="{ open: isOpen(comp.hk['ID HK']) || !!search }"
              >
                <p v-if="comp.hk.Beschreibung" class="gp-competence-desc">
                  {{ comp.hk.Beschreibung }}
                </p>
                <div v-for="lkv in comp.lks" :key="lkv.lk['ID LK']" class="gp-lk">
                  <div
                    class="gp-head gp-lk-head"
                    :class="{ open: isOpen(lkv.lk['ID LK']) || !!search }"
                    @click="toggleSection(lkv.lk['ID LK'])"
                  >
                    <span class="arrow">▶</span>
                    <span class="gp-code">{{ lkv.lk['ID LK'] }}</span>
                    <span class="gp-name-sm gp-lk-desc">{{ lkv.lk['Beschreibung LK'] }}</span>
                    <span class="gp-lernort">{{ lkv.lk.Lernort }}</span>
                    <span v-if="formatSemesters(lkv.lk.Semester)" class="gp-sem">{{
                      formatSemesters(lkv.lk.Semester)
                    }}</span>
                  </div>
                  <div
                    class="gp-lk-content"
                    :class="{ open: isOpen(lkv.lk['ID LK']) || !!search }"
                  >
                    <label
                      v-for="item in lkv.items"
                      :key="item.lz['ID LZ']"
                      class="gp-lz-row"
                      :class="{ existing: selectedExisting.has(String(item.lz['ID LZ'])), picked: isSelected(String(item.lz['ID LZ'])) }"
                    >
                      <input
                        type="checkbox"
                        :checked="isSelected(String(item.lz['ID LZ']))"
                        :disabled="selectedExisting.has(String(item.lz['ID LZ']))"
                        @change="toggleLz(String(item.lz['ID LZ']))"
                      />
                      <span class="gp-lz-id">{{ item.lz['ID LZ'] }}</span>
                      <span class="gp-lz-desc">{{ item.lz['Beschreibung LZ'] }}</span>
                      <span class="gp-sem">{{
                        Array.isArray(item.lz.Semester)
                          ? item.lz.Semester.join(', ')
                          : item.lz.Semester
                      }}</span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="view.length === 0" class="text-muted gp-empty">
          Keine Lernziele gefunden – andere Suchbegriffe oder Filter versuchen.
        </div>
      </div>
    </div>

    <div class="gp-footer">
      <span class="text-muted" :class="{ 'gp-count-active': selectedCount > 0 }">
        {{
          selectedCount > 0
            ? selectedCount + ' Lernziel' + (selectedCount === 1 ? '' : 'e') + ' ausgewählt'
            : 'Noch keine Lernziele ausgewählt'
        }}
      </span>
      <div class="flex-gap">
        <button type="button" class="btn" @click="emit('close')">Abbrechen</button>
        <button
          type="button"
          class="btn btn-primary"
          :disabled="selectedCount === 0"
          @click="confirmSelection"
        >
          Übernehmen
        </button>
      </div>
    </div>
  </ModalDialog>
</template>

<style scoped>
.gp-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

/* Berufswahl */
.gp-job-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.gp-job-row .form-control {
  flex: 1;
}

/* Suche + Filter */
.gp-controls {
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}

.gp-search-row {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.gp-search {
  flex: 1;
}

.gp-filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
}

.gp-filter-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.gp-filter-group > label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-light);
}

.gp-options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.gp-pill {
  border: 1px solid var(--color-border-strong);
  background: var(--color-surface);
  color: var(--color-text);
  font-size: 0.76rem;
  font-weight: 500;
  font-family: inherit;
  border-radius: 999px;
  padding: 0.15rem 0.55rem;
  cursor: pointer;
  transition: all 0.12s ease;
}

.gp-pill:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.gp-pill.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #ffffff;
}

.gp-clear:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

/* Baum */
.gp-tree {
  max-height: 46vh;
  overflow-y: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-2);
}

.gp-loading,
.gp-empty {
  padding: var(--space-3);
}

.gp-subject {
  margin-bottom: var(--space-2);
}

.gp-head {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  cursor: pointer;
  user-select: none;
  border-radius: var(--radius-sm);
}

.gp-subject-head {
  background: var(--color-primary-soft);
  border-left: 4px solid var(--color-primary);
  padding: 0.45rem var(--space-2);
}

.gp-competence-head:hover,
.gp-lk-head:hover {
  background: var(--color-surface-subtle);
}

.arrow {
  font-size: 0.6rem;
  color: var(--color-text-light);
  transition: transform 0.15s ease;
  flex-shrink: 0;
}

.open > .arrow {
  transform: rotate(90deg);
}

.gp-code,
.gp-code-b {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  font-weight: 700;
  color: var(--color-primary);
  white-space: nowrap;
}

.gp-code-b {
  background: var(--color-primary);
  color: #ffffff;
  border-radius: var(--radius-sm);
  padding: 0.05rem 0.35rem;
}

.gp-name {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--color-text);
}

.gp-name-sm {
  color: var(--color-text);
  font-size: 0.85rem;
}

.gp-lk-desc {
  flex: 1;
  min-width: 140px;
}

.gp-pw,
.gp-lernort {
  flex-shrink: 0;
  font-size: 0.68rem;
  font-weight: 700;
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
}

.gp-pw.mandatory,
.gp-lernort {
  background: var(--color-success-bg);
  color: var(--color-success);
  border: 1px solid var(--color-success-border);
}

.gp-pw.optional {
  background: var(--color-warning-bg);
  color: var(--color-warning);
  border: 1px solid var(--color-warning-border);
}

.gp-pw {
  margin-left: auto;
}

.gp-sem {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--color-text-light);
  white-space: nowrap;
}

.gp-subject-content,
.gp-competence-content,
.gp-lk-content {
  display: none;
}

.gp-subject-content.open,
.gp-competence-content.open,
.gp-lk-content.open {
  display: block;
}

.gp-subject-content {
  padding-left: var(--space-3);
}

.gp-subject-content .gp-competence-content {
  padding: var(--space-1) var(--space-2) 0 var(--space-3);
}

.gp-competence-desc {
  font-size: 0.8rem;
  color: var(--color-text-muted);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-2);
  margin: 0 0 var(--space-1) 0;
}

.gp-lk {
  margin-bottom: var(--space-1);
}

.gp-lk-head {
  border: 1px solid var(--color-border);
  padding: 0.3rem var(--space-2);
  margin-bottom: var(--space-1);
  background: var(--color-surface-muted);
  flex-wrap: wrap;
}

/* LZ-Zeilen */
.gp-lz-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-top: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.gp-lz-row:first-child {
  border-top: none;
}

.gp-lz-row:hover {
  background: var(--color-surface-subtle);
}

.gp-lz-row input {
  flex-shrink: 0;
  transform: translateY(1px);
}

.gp-lz-row.picked {
  background: var(--color-primary-soft);
}

.gp-lz-row.existing {
  cursor: not-allowed;
  opacity: 0.75;
}

.gp-lz-id {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--color-text-light);
  white-space: nowrap;
}

.gp-lz-desc {
  flex: 1;
  font-size: 0.85rem;
  color: var(--color-text);
}

.gp-lz-row.existing .gp-lz-desc::after {
  content: '· bereits hinzugefügt';
  font-size: 0.72rem;
  color: var(--color-success);
  font-weight: 600;
  margin-left: 0.4rem;
}

/* Fusszeile */
.gp-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  border-top: 1px solid var(--color-border);
  padding-top: var(--space-3);
}

.gp-count-active {
  font-weight: 600 !important;
  color: var(--color-primary) !important;
}

@media (max-width: 720px) {
  .gp-lz-row {
    flex-wrap: wrap;
  }

  .gp-lz-desc {
    order: 1;
    flex-basis: 100%;
  }

  .gp-sem {
    order: 2;
  }

  .gp-lz-id {
    order: 3;
  }
}
</style>

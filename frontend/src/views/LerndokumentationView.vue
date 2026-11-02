<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'
import ModalDialog from '../components/ui/ModalDialog.vue'
import DocumentManager from '../components/ui/DocumentManager.vue'

const auth = useAuthStore()
const route = useRoute()

const activeSection = computed(() => route.params.section || 'noten')
const grades = ref([])
const error = ref('')

// Filter & Search state for Grades
const searchQuery = ref('')
const filterStudent = ref('')
const filterSubject = ref('')
const expandedGradeIds = ref({})

// Grade Modal
const showGradeModal = ref(false)
const editingGrade = ref(null)
const formStudentId = ref('')
const formSubject = ref('')
const formTitle = ref('')
const formGrade = ref('5.0')
const formDate = ref(new Date().toISOString().slice(0, 10))
const formComment = ref('')

const commonSubjects = [
  'Technische Grundlagen (Mathematik & Physik)',
  'Werkstoff- und Fertigungstechnik',
  'Zeichnungstechnik / CAD',
  'Elektrotechnik & Steuerungstechnik',
  'Überbetriebliche Kurse (ÜK)',
  'Allgemeinbildung (ABU)',
  'Technisches Englisch'
]

async function loadGrades() {
  error.value = ''
  try {
    grades.value = await apiFetch('/api/grades')
  } catch (e) {
    error.value = e.message
  }
}

onMounted(loadGrades)

const availableSubjects = computed(() => {
  const s = new Set(grades.value.map((g) => g.subject))
  return Array.from(s).sort()
})

const filteredGrades = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return grades.value.filter((g) => {
    if (filterStudent.value && g.student !== Number(filterStudent.value)) return false
    if (filterSubject.value && g.subject !== filterSubject.value) return false
    if (q) {
      const hay = `${g.title} ${g.subject} ${g.student_name || ''} ${g.comment || ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

const overallAverage = computed(() => {
  if (filteredGrades.value.length === 0) return '–'
  const sum = filteredGrades.value.reduce((acc, item) => acc + Number(item.grade), 0)
  return (sum / filteredGrades.value.length).toFixed(2)
})

function toggleExpandGrade(id) {
  expandedGradeIds.value[id] = !expandedGradeIds.value[id]
}

function openNewGrade() {
  editingGrade.value = null
  formStudentId.value = auth.isStudent
    ? auth.user?.id
    : filterStudent.value || auth.companyStudents[0]?.id || ''
  formSubject.value = filterSubject.value || commonSubjects[0]
  formTitle.value = ''
  formGrade.value = '5.0'
  formDate.value = new Date().toISOString().slice(0, 10)
  formComment.value = ''
  showGradeModal.value = true
}

function openEditGrade(g) {
  editingGrade.value = g
  formStudentId.value = g.student
  formSubject.value = g.subject
  formTitle.value = g.title
  formGrade.value = String(g.grade)
  formDate.value = g.date || new Date().toISOString().slice(0, 10)
  formComment.value = g.comment || ''
  showGradeModal.value = true
}

async function saveGrade() {
  error.value = ''
  try {
    const payload = {
      student: Number(formStudentId.value || auth.user?.id),
      subject: formSubject.value,
      title: formTitle.value,
      grade: parseFloat(formGrade.value),
      date: formDate.value,
      comment: formComment.value
    }
    if (editingGrade.value) {
      await apiFetch(`/api/grades/${editingGrade.value.id}`, {
        method: 'PUT',
        body: payload
      })
    } else {
      await apiFetch('/api/grades', {
        method: 'POST',
        body: payload
      })
    }
    showGradeModal.value = false
    await loadGrades()
  } catch (e) {
    error.value = e.message
  }
}

async function deleteGrade(g) {
  if (!confirm(`Note "${g.title}" (${g.grade}) wirklich löschen?`)) return
  try {
    await apiFetch(`/api/grades/${g.id}`, { method: 'DELETE' })
    await loadGrades()
  } catch (e) {
    error.value = e.message
  }
}

function gradeBadgeClass(val) {
  const num = Number(val)
  if (num >= 5.0) return 'badge-success'
  if (num >= 4.0) return 'badge-info'
  return 'badge-danger'
}

function formatDate(d) {
  if (!d) return '–'
  return new Date(d).toLocaleDateString('de-CH')
}
</script>

<template>
  <div>
    <div v-if="error" class="alert alert-error">{{ error }}</div>

    <!-- Section 1: Noten & Prüfungen -->
    <div v-if="activeSection === 'noten'">
      <div class="page-header">
        <div>
          <h1 class="page-title">Noten & Prüfungen</h1>
          <p class="page-subtitle">
            Schulnoten und Prüfungsresultate (Neueste zuerst)
          </p>
        </div>
        <button type="button" class="btn btn-primary" @click="openNewGrade">
          + Note eintragen
        </button>
      </div>

      <!-- Filter & Search Bar -->
      <div class="filter-bar">
        <input
          v-model="searchQuery"
          type="search"
          class="form-control filter-search"
          placeholder="Prüfung, Fach, Lernende/r oder Bemerkung suchen..."
        />

        <select
          v-if="auth.isTrainer"
          v-model="filterStudent"
          class="form-control filter-select"
        >
          <option value="">Alle Lernenden</option>
          <option v-for="stu in auth.companyStudents" :key="stu.id" :value="stu.id">
            {{ stu.full_name }}
          </option>
        </select>

        <select v-model="filterSubject" class="form-control filter-select">
          <option value="">Alle Fächer</option>
          <option v-for="sub in availableSubjects" :key="sub" :value="sub">
            {{ sub }}
          </option>
        </select>

        <span class="badge badge-info">Ø {{ overallAverage }}</span>
        <span class="text-muted">{{ filteredGrades.length }} Prüfungen</span>
      </div>

      <!-- Collapsible Grades List (Most recent first) -->
      <div v-if="filteredGrades.length === 0" class="card empty-state">
        Keine passenden Noten gefunden.
      </div>
      <div v-else>
        <div
          v-for="g in filteredGrades"
          :key="g.id"
          class="collapsible-card"
        >
          <div class="collapsible-header" @click="toggleExpandGrade(g.id)">
            <div class="flex-gap">
              <span class="expand-indicator">
                {{ expandedGradeIds[g.id] ? '▾' : '▸' }}
              </span>
              <div>
                <div class="flex-gap">
                  <strong>{{ g.title }}</strong>
                  <span class="badge badge-info">{{ g.subject }}</span>
                  <span v-if="auth.isTrainer && g.student_name" class="badge badge-warning">
                    {{ g.student_name }}
                  </span>
                </div>
                <div class="text-muted" style="margin-top: 2px">
                  Prüfungsdatum: {{ formatDate(g.date) }}
                </div>
              </div>
            </div>

            <div class="flex-gap">
              <span
                class="badge"
                :class="gradeBadgeClass(g.grade)"
                style="font-size: 0.9rem; padding: 0.25rem 0.7rem"
              >
                Note {{ Number(g.grade).toFixed(1) }}
              </span>
            </div>
          </div>

          <div v-if="expandedGradeIds[g.id]" class="collapsible-body">
            <div class="flex-between">
              <div>
                <div class="form-label">Bemerkung / Reflexion</div>
                <p style="margin: 0; white-space: pre-line">
                  {{ g.comment || 'Keine Bemerkung hinterlegt.' }}
                </p>
              </div>
              <div class="flex-gap">
                <button type="button" class="btn btn-sm" @click="openEditGrade(g)">
                  Bearbeiten
                </button>
                <button
                  type="button"
                  class="btn btn-sm btn-danger"
                  @click="deleteGrade(g)"
                >
                  Löschen
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Section 2: Zeugnisse -->
    <div v-else-if="activeSection === 'zeugnisse'">
      <DocumentManager
        document-type="zeugnis"
        title="Semesterzeugnisse & Standortbestimmungen"
        subtitle="Offizielle Schulzeugnisse der Berufsfachschule und Berufsmaturitätsschule"
      />
    </div>

    <!-- Section 3: Ausbildungsgespräche / Probezeitgespräch -->
    <div v-else-if="activeSection === 'gespraeche'">
      <DocumentManager
        document-type="ausbildungsgespraech"
        title="Ausbildungsgespräche & Probezeitgespräch"
        subtitle="Halbjährliche Bildungsberichte, Probezeitprotokolle und Zielvereinbarungen"
        :prefer-text-editor="true"
      />
    </div>

    <!-- Section 4: Kursnachweise -->
    <div v-else-if="activeSection === 'kursnachweise'">
      <DocumentManager
        document-type="kursnachweis"
        title="Überbetriebliche Kurse (ÜK) & Kursnachweise"
        subtitle="Bestätigungen, Zertifikate und Kompetenznachweise aus ÜK und internen Kursen"
      />
    </div>

    <!-- Section 5: Lernjournal -->
    <div v-else-if="activeSection === 'lernjournal'">
      <DocumentManager
        document-type="lernjournal"
        title="Lernjournal (Arbeits- und Lernreflexion)"
        subtitle="Regelmässige Einträge zu ausgeführten Arbeiten, Erkenntnissen und Lernschritten (gespeichert im Firmenordner)"
        :prefer-text-editor="true"
      />
    </div>

    <!-- Modal: Grade Create/Edit -->
    <ModalDialog
      :show="showGradeModal"
      :title="editingGrade ? 'Note bearbeiten' : 'Neue Note / Prüfung eintragen'"
      @close="showGradeModal = false"
    >
      <form @submit.prevent="saveGrade">
        <div v-if="auth.isTrainer && !editingGrade" class="form-group">
          <label class="form-label">Lernende/r *</label>
          <select v-model="formStudentId" class="form-control" required>
            <option v-for="stu in auth.companyStudents" :key="stu.id" :value="stu.id">
              {{ stu.full_name }} ({{ stu.job_title }})
            </option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Fach *</label>
          <input
            v-model="formSubject"
            list="subject-suggestions"
            type="text"
            class="form-control"
            required
          />
          <datalist id="subject-suggestions">
            <option v-for="sub in commonSubjects" :key="sub" :value="sub" />
          </datalist>
        </div>

        <div class="form-group">
          <label class="form-label">Prüfungstitel / Thema *</label>
          <input v-model="formTitle" type="text" class="form-control" required />
        </div>

        <div class="grid-2">
          <div class="form-group">
            <label class="form-label">Note (1.0 bis 6.0) *</label>
            <input
              v-model="formGrade"
              type="number"
              step="0.1"
              min="1.0"
              max="6.0"
              class="form-control"
              required
            />
          </div>
          <div class="form-group">
            <label class="form-label">Prüfungsdatum *</label>
            <input v-model="formDate" type="date" class="form-control" required />
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Bemerkung / Reflexion</label>
          <textarea v-model="formComment" class="form-control" rows="3" />
        </div>

        <div class="flex-between">
          <button type="button" class="btn" @click="showGradeModal = false">
            Abbrechen
          </button>
          <button type="submit" class="btn btn-primary">Speichern</button>
        </div>
      </form>
    </ModalDialog>
  </div>
</template>

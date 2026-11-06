<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'
import ModalDialog from '../components/ui/ModalDialog.vue'
import DocumentManager from '../components/ui/DocumentManager.vue'
import EditButton from '../components/ui/EditButton.vue'
import LehrplanGoalPicker from '../components/ui/LehrplanGoalPicker.vue'
import LernzielLabel from '../components/ui/LernzielLabel.vue'
import { jobCodeForProfession } from '../utils/lehrplanJobs'

const auth = useAuthStore()
const route = useRoute()

const activeSection = computed(() => route.params.section || 'noten')
const grades = ref([])
const error = ref('')

// Filter & Search state for Grades
const searchQuery = ref('')
const filterStudent = ref('')
const filterSubject = ref('')
const filterSemester = ref('')
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
const formGradeGoals = ref([])
const newGoalText = ref('')
const showGradeGoalPicker = ref(false)

function applyPickedGradeGoals(picked) {
  for (const item of picked || []) {
    if (item?.id && !formGradeGoals.value.includes(item.id)) {
      formGradeGoals.value.push(item.id)
    }
  }
}

function addGradeGoal() {
  const g = (newGoalText.value || '').trim()
  if (g && !formGradeGoals.value.includes(g)) formGradeGoals.value.push(g)
  newGoalText.value = ''
}

function removeGradeGoal(idx) {
  formGradeGoals.value.splice(idx, 1)
}

const defaultGradeJobCode = computed(() => {
  const ownerUser =
    auth.isStudent && auth.user?.id === Number(formStudentId.value)
      ? auth.user
      : auth.companyStudents.find((s) => s.id === Number(formStudentId.value))
  return jobCodeForProfession(ownerUser?.job_title || '')
})

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

const availableSemesters = computed(() => {
  const s = new Set(
    grades.value.map((g) => g.semester).filter((semester) => semester != null)
  )
  return Array.from(s).sort((a, b) => a - b)
})

const hasGradesWithoutSemester = computed(() =>
  grades.value.some((g) => g.semester == null)
)

const gradesMatchingContext = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return grades.value.filter((g) => {
    if (filterSubject.value && g.subject !== filterSubject.value) return false
    if (filterSemester.value === 'none' && g.semester != null) return false
    if (
      filterSemester.value &&
      filterSemester.value !== 'none' &&
      g.semester !== Number(filterSemester.value)
    ) {
      return false
    }
    if (q) {
      const hay = `${g.title} ${g.subject} ${g.student_name || ''} ${g.comment || ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

const filteredGrades = computed(() => {
  if (!filterStudent.value) return gradesMatchingContext.value
  return gradesMatchingContext.value.filter(
    (g) => g.student === Number(filterStudent.value)
  )
})

const studentAverages = computed(() => {
  const groups = new Map()
  for (const grade of gradesMatchingContext.value) {
    if (!groups.has(grade.student)) {
      groups.set(grade.student, {
        student: grade.student,
        name: grade.student_name || 'Unbekannt',
        total: 0,
        count: 0
      })
    }
    const group = groups.get(grade.student)
    group.total += Number(grade.grade)
    group.count += 1
  }
  return [...groups.values()]
    .map((group) => ({
      ...group,
      average: (group.total / group.count).toFixed(2)
    }))
    .sort((a, b) => a.name.localeCompare(b.name, 'de-CH'))
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
  formGradeGoals.value = []
  newGoalText.value = ''
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
  formGradeGoals.value = [...(g.goals || [])]
  newGoalText.value = ''
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
      comment: formComment.value,
      goals: formGradeGoals.value
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
        <EditButton
          size="lg"
          show-label
          icon="plus"
          variant="primary"
          label="Note eintragen"
          @click="openNewGrade"
        />
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

        <select v-model="filterSemester" class="form-control filter-select">
          <option value="">Alle Semester</option>
          <option v-for="sem in availableSemesters" :key="sem" :value="sem">
            Semester {{ sem }}
          </option>
          <option v-if="hasGradesWithoutSemester" value="none">Ohne Semester</option>
        </select>

      </div>

      <!-- Average per student, respecting the active subject/semester/search filters -->
      <div
        v-if="auth.isTrainer && studentAverages.length"
        class="student-average-bar"
      >
        <span class="student-average-label">Ø pro Lernende/r</span>
        <span
          v-for="entry in studentAverages"
          :key="entry.student"
          class="student-average-chip"
          :class="{ 'is-active': Number(filterStudent) === entry.student }"
        >
          <span>{{ entry.name }}</span>
          <strong>Ø {{ entry.average }}</strong>
          <span class="text-muted">({{ entry.count }})</span>
        </span>
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
                  <span v-if="g.semester" class="badge badge-neutral">
                    Semester {{ g.semester }}
                  </span>
                  <span v-if="auth.isTrainer && g.student_name" class="badge badge-warning">
                    {{ g.student_name }}
                  </span>
                </div>
                <div class="text-muted" style="margin-top: 2px">
                  Prüfungsdatum: {{ formatDate(g.date) }}
                </div>
              </div>
            </div>

            <div class="flex-gap" @click.stop>
              <span
                class="badge"
                :class="gradeBadgeClass(g.grade)"
                style="font-size: 0.9rem; padding: 0.25rem 0.7rem"
              >
                Note {{ Number(g.grade).toFixed(1) }}
              </span>
              <EditButton
                label="Note bearbeiten"
                icon="edit"
                @click="openEditGrade(g)"
              />
              <EditButton
                label="Note löschen"
                icon="delete"
                variant="danger"
                @click="deleteGrade(g)"
              />
            </div>
          </div>

          <div v-if="expandedGradeIds[g.id]" class="collapsible-body">
            <div>
              <div class="form-label">Bemerkung / Reflexion</div>
              <p style="margin: 0; white-space: pre-line">
                {{ g.comment || 'Keine Bemerkung hinterlegt.' }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Section 2: Zeugnisse & Kursnachweise -->
    <div v-else-if="activeSection === 'nachweise'">
      <DocumentManager
        :document-types="['zeugnis', 'kursnachweis']"
        title="Zeugnisse & Kursnachweise"
        subtitle="Semesterzeugnisse, Standortbestimmungen sowie ÜK- und Kursbestätigungen"
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

    <!-- Section 4: Lernjournal -->
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

        <!-- Lernziele -->
        <div class="form-group">
          <label class="form-label">Lernziele</label>

          <div class="goal-list-display">
            <span
              v-for="(g, idx) in formGradeGoals"
              :key="g + idx"
              class="goal-chip"
            >
              <LernzielLabel :goal="g" />
              <button
                type="button"
                class="goal-chip-remove"
                title="Lernziel entfernen"
                @click="removeGradeGoal(idx)"
              >✕</button>
            </span>
            <span v-if="formGradeGoals.length === 0" class="text-muted">Noch keine Lernziele erfasst.</span>
          </div>

          <div class="flex-gap" style="margin-top: var(--space-2)">
            <input
              v-model="newGoalText"
              type="text"
              class="form-control goal-add-input"
              placeholder="Neues Lernziel eingeben..."
              @keydown.enter.prevent="addGradeGoal"
            />
            <button type="button" class="btn btn-sm" @click="addGradeGoal">+ Hinzufügen</button>
            <button type="button" class="btn btn-sm" @click="showGradeGoalPicker = true">
              + Lernziel aus Lehrplan wählen
            </button>
          </div>
        </div>

        <div class="flex-between">
          <button type="button" class="btn" @click="showGradeModal = false">
            Abbrechen
          </button>
          <button type="submit" class="btn btn-primary">Speichern</button>
        </div>
      </form>
    </ModalDialog>

    <!-- Lernziel-Picker (Noten & Prüfungen) -->
    <LehrplanGoalPicker
      :show="showGradeGoalPicker"
      :default-job-code="defaultGradeJobCode"
      :existing="formGradeGoals"
      @confirm="applyPickedGradeGoals"
      @close="showGradeGoalPicker = false"
    />
  </div>
</template>

<style scoped>
/* Lernziele-Pflege im Noten-Modal */
.goal-list-display {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.goal-chip {
  display: inline-flex;
  align-items: flex-start;
  gap: var(--space-1);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.35rem 0.6rem;
  max-width: 100%;
}

.goal-chip-remove {
  border: none;
  background: transparent;
  color: var(--color-text-light);
  cursor: pointer;
  font-size: 0.8rem;
  line-height: 1;
  padding: 2px 0 0;
}

.goal-chip-remove:hover {
  color: var(--color-danger, #a33);
}

.goal-add-input {
  flex: 1;
  min-width: 12rem;
}

.student-average-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-3);
}

.student-average-label {
  margin-right: var(--space-2);
  color: var(--color-text-muted);
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.student-average-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.65rem;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  font-variant-numeric: tabular-nums;
}

.student-average-chip.is-active {
  background: var(--color-primary-soft);
  border-color: var(--color-primary);
  color: var(--color-primary);
}
</style>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'
import ModalDialog from '../components/ui/ModalDialog.vue'

const auth = useAuthStore()

const projects = ref([])
const implementations = ref([])
const evaluations = ref([])
const error = ref('')

// Filter & Search state
const searchQuery = ref('')
const filterStudent = ref('')
const filterStatus = ref('')
const expandedIds = ref({})

// Project Modal (Trainer)
const showProjectModal = ref(false)
const editingProject = ref(null)
const projTitle = ref('')
const projParent = ref('')
const projDescription = ref('')
const projGoalsText = ref('')
const projStartDate = ref('')
const projDueDate = ref('')

// Implementation / Task Report Modal
const showImplModal = ref(false)
const editingImpl = ref(null)
const implProjectId = ref(null)
const implStudentId = ref('')
const implTitle = ref('')
const implText = ref('')
const implIsDone = ref(false)

// Evaluation Modal
const showEvalModal = ref(false)
const editingEval = ref(null)
const evalProjectId = ref(null)
const evalStudentId = ref('')
const evalGoal = ref('')
const evalParticipation = ref('')
const evalPlanningText = ref('')
const evalText = ref('')

const projectTitleMap = computed(() => {
  const m = {}
  for (const p of projects.value) {
    m[p.id] = p.title
  }
  return m
})

const rootProjects = computed(() =>
  projects.value.filter((p) => !p.parent_project)
)

function implementationsFor(projectId) {
  return implementations.value.filter((i) => {
    if (i.project !== projectId) return false
    if (filterStudent.value && i.student !== Number(filterStudent.value)) return false
    return true
  })
}

function evaluationsFor(projectId) {
  return evaluations.value.filter((ev) => {
    if (ev.project !== projectId) return false
    if (filterStudent.value && ev.student !== Number(filterStudent.value)) return false
    return true
  })
}

const filteredProjects = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return projects.value.filter((p) => {
    const impls = implementationsFor(p.id)
    const evals = evaluationsFor(p.id)

    if (filterStatus.value === 'done') {
      if (impls.length === 0 || !impls.every((i) => i.is_done)) return false
    } else if (filterStatus.value === 'open') {
      if (impls.length > 0 && impls.every((i) => i.is_done)) return false
    }

    if (q) {
      const goalsStr = (p.goals || []).join(' ')
      const implStr = impls.map((i) => `${i.title} ${i.text} ${i.student_name}`).join(' ')
      const evalStr = evals
        .map((e) => `${e.goal} ${e.planning_text} ${e.eval_text} ${e.student_name}`)
        .join(' ')
      const hay =
        `${p.title} ${p.description || ''} ${p.author_name || ''} ${goalsStr} ${implStr} ${evalStr}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

function toggleExpand(projectId) {
  expandedIds.value[projectId] = !expandedIds.value[projectId]
}

async function loadAll() {
  error.value = ''
  try {
    const [projData, implData, evalData] = await Promise.all([
      apiFetch('/api/project'),
      apiFetch('/api/implementation'),
      apiFetch('/api/evaluation')
    ])
    projects.value = projData || []
    implementations.value = implData || []
    evaluations.value = evalData || []
  } catch (e) {
    error.value = e.message
  }
}

onMounted(loadAll)

// Project CRUD
function openNewProject(parentId = null) {
  editingProject.value = null
  projTitle.value = ''
  projParent.value = parentId || ''
  projDescription.value = ''
  projGoalsText.value = ''
  projStartDate.value = new Date().toISOString().slice(0, 10)
  projDueDate.value = ''
  showProjectModal.value = true
}

function openEditProject(proj) {
  editingProject.value = proj
  projTitle.value = proj.title
  projParent.value = proj.parent_project || ''
  projDescription.value = proj.description || ''
  projGoalsText.value = (proj.goals || []).join('\n')
  projStartDate.value = proj.start_date || ''
  projDueDate.value = proj.due_date || ''
  showProjectModal.value = true
}

async function saveProject() {
  error.value = ''
  try {
    const payload = {
      title: projTitle.value,
      parent_project: projParent.value || null,
      description: projDescription.value,
      goals: projGoalsText.value,
      start_date: projStartDate.value || null,
      due_date: projDueDate.value || null
    }
    if (editingProject.value) {
      await apiFetch(`/api/project/${editingProject.value.id}`, {
        method: 'PUT',
        body: payload
      })
    } else {
      const created = await apiFetch('/api/project', {
        method: 'POST',
        body: payload
      })
      expandedIds.value[created.id] = true
    }
    showProjectModal.value = false
    await loadAll()
  } catch (e) {
    error.value = e.message
  }
}

async function deleteProject(proj) {
  if (!confirm(`Projekt "${proj.title}" inklusive Unterprojekten wirklich löschen?`))
    return
  try {
    await apiFetch(`/api/project/${proj.id}`, { method: 'DELETE' })
    await loadAll()
  } catch (e) {
    error.value = e.message
  }
}

// Implementation (Aufgaben & Berichte) CRUD
function openNewImpl(proj) {
  editingImpl.value = null
  implProjectId.value = proj.id
  implStudentId.value = auth.isStudent
    ? auth.user?.id
    : filterStudent.value || auth.companyStudents[0]?.id || ''
  implTitle.value = ''
  implText.value = ''
  implIsDone.value = false
  showImplModal.value = true
}

function openEditImpl(item) {
  editingImpl.value = item
  implProjectId.value = item.project
  implStudentId.value = item.student
  implTitle.value = item.title
  implText.value = item.text || ''
  implIsDone.value = item.is_done
  showImplModal.value = true
}

async function saveImpl() {
  try {
    if (editingImpl.value) {
      await apiFetch(`/api/implementation/${editingImpl.value.id}`, {
        method: 'PUT',
        body: {
          title: implTitle.value,
          text: implText.value,
          is_done: implIsDone.value
        }
      })
    } else {
      await apiFetch('/api/implementation', {
        method: 'POST',
        body: {
          project: implProjectId.value,
          student: Number(implStudentId.value),
          title: implTitle.value,
          text: implText.value,
          is_done: implIsDone.value
        }
      })
    }
    showImplModal.value = false
    await loadAll()
  } catch (e) {
    error.value = e.message
  }
}

async function toggleImplDone(item) {
  try {
    await apiFetch(`/api/implementation/${item.id}`, {
      method: 'PUT',
      body: { is_done: !item.is_done }
    })
    await loadAll()
  } catch (e) {
    error.value = e.message
  }
}

async function deleteImpl(item) {
  if (!confirm(`Arbeitsbericht "${item.title}" löschen?`)) return
  try {
    await apiFetch(`/api/implementation/${item.id}`, { method: 'DELETE' })
    await loadAll()
  } catch (e) {
    error.value = e.message
  }
}

// Evaluation (Ziele & Bewertung) CRUD
function openNewEval(proj, prefillGoal = '') {
  editingEval.value = null
  evalProjectId.value = proj.id
  evalStudentId.value = auth.isStudent
    ? auth.user?.id
    : filterStudent.value || auth.companyStudents[0]?.id || ''
  evalGoal.value = prefillGoal || proj.goals?.[0] || ''
  evalParticipation.value = implementationsFor(proj.id)[0]?.id || ''
  evalPlanningText.value = ''
  evalText.value = ''
  showEvalModal.value = true
}

function openEditEval(ev) {
  editingEval.value = ev
  evalProjectId.value = ev.project
  evalStudentId.value = ev.student
  evalGoal.value = ev.goal
  evalParticipation.value = ev.participation || ''
  evalPlanningText.value = ev.planning_text || ''
  evalText.value = ev.eval_text || ''
  showEvalModal.value = true
}

async function saveEval() {
  try {
    if (editingEval.value) {
      await apiFetch(`/api/evaluation/${editingEval.value.id}`, {
        method: 'PUT',
        body: {
          goal: evalGoal.value,
          planning_text: evalPlanningText.value,
          eval_text: evalText.value
        }
      })
    } else {
      await apiFetch('/api/evaluation', {
        method: 'POST',
        body: {
          project: evalProjectId.value,
          participation: evalParticipation.value || null,
          student: Number(evalStudentId.value),
          goal: evalGoal.value,
          planning_text: evalPlanningText.value,
          eval_text: evalText.value
        }
      })
    }
    showEvalModal.value = false
    await loadAll()
  } catch (e) {
    error.value = e.message
  }
}

async function deleteEval(ev) {
  if (!confirm('Bewertungseintrag wirklich löschen?')) return
  try {
    await apiFetch(`/api/evaluation/${ev.id}`, { method: 'DELETE' })
    await loadAll()
  } catch (e) {
    error.value = e.message
  }
}

function formatDate(d) {
  if (!d) return '–'
  return new Date(d).toLocaleDateString('de-CH')
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">Projekte, Themen und Praktika</h1>
        <p class="page-subtitle">
          Aufgaben, Lernziele, Arbeitsberichte und Kompetenzbewertungen (Neueste zuerst)
        </p>
      </div>
      <div v-if="auth.isTrainer" class="flex-gap">
        <button type="button" class="btn btn-primary" @click="openNewProject(null)">
          + Neues Projekt / Praktikum
        </button>
      </div>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>

    <!-- Filter & Search Bar -->
    <div class="filter-bar">
      <input
        v-model="searchQuery"
        type="search"
        class="form-control filter-search"
        placeholder="Projekte, Ziele, Berichte oder Lernende durchsuchen..."
      />

      <select
        v-if="auth.isTrainer"
        v-model="filterStudent"
        class="form-control filter-select"
      >
        <option value="">Alle Lernenden</option>
        <option v-for="stu in auth.companyStudents" :key="stu.id" :value="stu.id">
          {{ stu.full_name }} ({{ stu.job_title }})
        </option>
      </select>

      <select v-model="filterStatus" class="form-control filter-select">
        <option value="">Alle Status</option>
        <option value="open">Offen / In Arbeit</option>
        <option value="done">Erledigt</option>
      </select>

      <span class="text-muted">{{ filteredProjects.length }} Projekte</span>
    </div>

    <!-- Collapsible Project List (collapsed by default, expand on click) -->
    <div v-if="filteredProjects.length === 0" class="card empty-state">
      Keine passenden Projekte gefunden.
    </div>

    <div v-else>
      <div
        v-for="proj in filteredProjects"
        :key="proj.id"
        class="collapsible-card"
      >
        <div class="collapsible-header" @click="toggleExpand(proj.id)">
          <div class="flex-gap">
            <span class="expand-indicator">{{ expandedIds[proj.id] ? '▾' : '▸' }}</span>
            <div>
              <div class="flex-gap">
                <strong style="font-size: 1rem">{{ proj.title }}</strong>
                <span v-if="proj.parent_project" class="badge badge-info">
                  Teilprojekt von: {{ projectTitleMap[proj.parent_project] || '#' + proj.parent_project }}
                </span>
              </div>
              <div class="text-muted" style="margin-top: 2px">
                Zeitraum: {{ formatDate(proj.start_date) }} bis {{ formatDate(proj.due_date) }}
                <span v-if="proj.author_name"> · Verantwortlich: {{ proj.author_name }}</span>
              </div>
            </div>
          </div>

          <div class="flex-gap">
            <span class="badge badge-info">
              {{ (proj.goals || []).length }} Ziele
            </span>
            <span class="badge badge-warning">
              {{ implementationsFor(proj.id).length }} Berichte
            </span>
            <span class="badge badge-success">
              {{ evaluationsFor(proj.id).length }} Bewertungen
            </span>
          </div>
        </div>

        <!-- Expanded Project Content -->
        <div v-if="expandedIds[proj.id]" class="collapsible-body">
          <div class="flex-between" style="margin-bottom: var(--space-3)">
            <p style="white-space: pre-line; margin: 0">
              {{ proj.description || 'Keine Beschreibung hinterlegt.' }}
            </p>
            <div v-if="auth.isTrainer" class="flex-gap">
              <button
                type="button"
                class="btn btn-sm"
                @click="openNewProject(proj.id)"
              >
                + Teilprojekt
              </button>
              <button
                type="button"
                class="btn btn-sm"
                @click="openEditProject(proj)"
              >
                Bearbeiten
              </button>
              <button
                type="button"
                class="btn btn-sm btn-danger"
                @click="deleteProject(proj)"
              >
                Löschen
              </button>
            </div>
          </div>

          <!-- Learning Goals (Ziele) -->
          <div class="section-block">
            <h4>Lernziele (Ziele)</h4>
            <div v-if="!proj.goals || proj.goals.length === 0" class="text-muted">
              Keine spezifischen Lernziele definiert.
            </div>
            <ul v-else class="goal-list">
              <li v-for="(g, idx) in proj.goals" :key="idx" class="goal-item">
                <span>{{ g }}</span>
                <button
                  type="button"
                  class="btn btn-sm"
                  @click="openNewEval(proj, g)"
                >
                  Ziel planen / bewerten
                </button>
              </li>
            </ul>
          </div>

          <!-- Tasks & Reports (Aufgaben & Berichte) -->
          <div class="section-block">
            <div class="flex-between" style="margin-bottom: var(--space-3)">
              <div>
                <h4 style="margin: 0">Aufgaben & Arbeitsberichte</h4>
                <span class="text-muted">Dokumentation der praktischen Umsetzung</span>
              </div>
              <button
                type="button"
                class="btn btn-primary btn-sm"
                @click="openNewImpl(proj)"
              >
                + Aufgabe / Bericht erfassen
              </button>
            </div>

            <div v-if="implementationsFor(proj.id).length === 0" class="text-muted">
              Noch keine Aufgaben oder Arbeitsberichte erfasst.
            </div>

            <div v-else>
              <div
                v-for="item in implementationsFor(proj.id)"
                :key="item.id"
                class="sub-card"
              >
                <div class="flex-between">
                  <div class="flex-gap">
                    <strong>{{ item.title }}</strong>
                    <span class="badge badge-info">{{ item.student_name }}</span>
                    <span
                      class="badge"
                      :class="item.is_done ? 'badge-success' : 'badge-warning'"
                    >
                      {{ item.is_done ? 'Erledigt' : 'Offen' }}
                    </span>
                  </div>
                  <div class="flex-gap">
                    <button
                      type="button"
                      class="btn btn-sm"
                      @click="toggleImplDone(item)"
                    >
                      {{ item.is_done ? 'Wieder öffnen' : 'Als erledigt markieren' }}
                    </button>
                    <button
                      type="button"
                      class="btn btn-sm"
                      @click="openEditImpl(item)"
                    >
                      Bearbeiten
                    </button>
                    <button
                      type="button"
                      class="btn btn-sm btn-danger"
                      @click="deleteImpl(item)"
                    >
                      Löschen
                    </button>
                  </div>
                </div>
                <p style="margin-top: var(--space-2); white-space: pre-line">
                  {{ item.text }}
                </p>
                <div class="text-muted">
                  Lernende/r: {{ item.student_name }}
                  <span v-if="item.supervisor_name">
                    · Betreuer/in: {{ item.supervisor_name }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Evaluations (Zielplanung & Bewertung) -->
          <div class="section-block">
            <div class="flex-between" style="margin-bottom: var(--space-3)">
              <div>
                <h4 style="margin: 0">Zielplanung & Bewertung</h4>
                <span class="text-muted">
                  Selbstplanung Lernende/r und Beurteilung durch Ausbildner/in
                </span>
              </div>
              <button
                type="button"
                class="btn btn-primary btn-sm"
                @click="openNewEval(proj, '')"
              >
                + Neue Bewertung erfassen
              </button>
            </div>

            <div v-if="evaluationsFor(proj.id).length === 0" class="text-muted">
              Noch keine Zielbewertungen vorhanden.
            </div>

            <div v-else>
              <div
                v-for="ev in evaluationsFor(proj.id)"
                :key="ev.id"
                class="sub-card"
              >
                <div class="flex-between">
                  <div class="flex-gap">
                    <strong>Lernziel: {{ ev.goal }}</strong>
                    <span class="badge badge-info">{{ ev.student_name }}</span>
                    <span
                      class="badge"
                      :class="ev.eval_text ? 'badge-success' : 'badge-warning'"
                    >
                      {{ ev.eval_text ? 'Bewertet' : 'In Planung' }}
                    </span>
                  </div>
                  <div class="flex-gap">
                    <button
                      type="button"
                      class="btn btn-sm"
                      @click="openEditEval(ev)"
                    >
                      {{ auth.isTrainer ? 'Bewerten / Bearbeiten' : 'Planung bearbeiten' }}
                    </button>
                    <button
                      v-if="auth.isTrainer || !ev.eval_text"
                      type="button"
                      class="btn btn-sm btn-danger"
                      @click="deleteEval(ev)"
                    >
                      Löschen
                    </button>
                  </div>
                </div>

                <div class="grid-2" style="margin-top: var(--space-3)">
                  <div class="eval-box">
                    <div class="form-label">Planung / Vorgehen (Lernende/r)</div>
                    <p style="white-space: pre-line; margin: 0">
                      {{ ev.planning_text || 'Noch keine Planung eingetragen.' }}
                    </p>
                  </div>
                  <div class="eval-box" :class="{ evaluated: !!ev.eval_text }">
                    <div class="form-label">Beurteilung / Feedback (Ausbildner/in)</div>
                    <p style="white-space: pre-line; margin: 0">
                      {{ ev.eval_text || 'Ausstehend.' }}
                    </p>
                  </div>
                </div>
                <div class="text-muted" style="margin-top: var(--space-2)">
                  Lernende/r: {{ ev.student_name }}
                  <span v-if="ev.supervisor_name">
                    · Ausbildner/in: {{ ev.supervisor_name }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal: Project Create/Edit -->
    <ModalDialog
      :show="showProjectModal"
      :title="editingProject ? 'Projekt bearbeiten' : 'Neues Projekt / Thema / Praktikum'"
      @close="showProjectModal = false"
    >
      <form @submit.prevent="saveProject">
        <div class="form-group">
          <label class="form-label">Titel *</label>
          <input v-model="projTitle" type="text" class="form-control" required />
        </div>

        <div class="form-group">
          <label class="form-label">Übergeordnetes Projekt (optional)</label>
          <select v-model="projParent" class="form-control">
            <option value="">Kein übergeordnetes Projekt (Hauptprojekt)</option>
            <option
              v-for="p in rootProjects"
              :key="p.id"
              :value="p.id"
              :disabled="editingProject && p.id === editingProject.id"
            >
              {{ p.title }}
            </option>
          </select>
        </div>

        <div class="grid-2">
          <div class="form-group">
            <label class="form-label">Startdatum</label>
            <input v-model="projStartDate" type="date" class="form-control" />
          </div>
          <div class="form-group">
            <label class="form-label">Fälligkeitsdatum</label>
            <input v-model="projDueDate" type="date" class="form-control" />
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Beschreibung / Auftrag</label>
          <textarea v-model="projDescription" class="form-control" rows="4" />
        </div>

        <div class="form-group">
          <label class="form-label">Lernziele (ein Ziel pro Zeile)</label>
          <textarea
            v-model="projGoalsText"
            class="form-control"
            rows="4"
            placeholder="z.B. Werkstück nach ISO-Toleranz fertigen"
          />
        </div>

        <div class="flex-between">
          <button type="button" class="btn" @click="showProjectModal = false">
            Abbrechen
          </button>
          <button type="submit" class="btn btn-primary">Speichern</button>
        </div>
      </form>
    </ModalDialog>

    <!-- Modal: Implementation (Aufgabe / Bericht) -->
    <ModalDialog
      :show="showImplModal"
      :title="editingImpl ? 'Arbeitsbericht bearbeiten' : 'Aufgabe / Arbeitsbericht erfassen'"
      @close="showImplModal = false"
    >
      <form @submit.prevent="saveImpl">
        <div v-if="auth.isTrainer && !editingImpl" class="form-group">
          <label class="form-label">Lernende/r *</label>
          <select v-model="implStudentId" class="form-control" required>
            <option v-for="stu in auth.companyStudents" :key="stu.id" :value="stu.id">
              {{ stu.full_name }} ({{ stu.job_title }})
            </option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Titel der Aufgabe / des Berichts *</label>
          <input v-model="implTitle" type="text" class="form-control" required />
        </div>

        <div class="form-group">
          <label class="form-label">Tätigkeitsbericht / Ausführung</label>
          <textarea
            v-model="implText"
            class="form-control"
            rows="6"
            placeholder="Beschreiben Sie die durchgeführten Arbeitsschritte, eingesetzten Maschinen und Messresultate..."
          />
        </div>

        <div class="form-group">
          <label class="flex-gap" style="cursor: pointer">
            <input v-model="implIsDone" type="checkbox" />
            <span>Aufgabe ist vollständig abgeschlossen</span>
          </label>
        </div>

        <div class="flex-between">
          <button type="button" class="btn" @click="showImplModal = false">
            Abbrechen
          </button>
          <button type="submit" class="btn btn-primary">Speichern</button>
        </div>
      </form>
    </ModalDialog>

    <!-- Modal: Evaluation (Zielplanung & Bewertung) -->
    <ModalDialog
      :show="showEvalModal"
      :title="editingEval ? 'Zielplanung & Bewertung bearbeiten' : 'Lernziel planen / bewerten'"
      @close="showEvalModal = false"
    >
      <form @submit.prevent="saveEval">
        <div v-if="auth.isTrainer && !editingEval" class="form-group">
          <label class="form-label">Lernende/r *</label>
          <select v-model="evalStudentId" class="form-control" required>
            <option v-for="stu in auth.companyStudents" :key="stu.id" :value="stu.id">
              {{ stu.full_name }} ({{ stu.job_title }})
            </option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Lernziel *</label>
          <input v-model="evalGoal" type="text" class="form-control" required />
        </div>

        <div class="form-group">
          <label class="form-label">Zugehöriger Arbeitsbericht (optional)</label>
          <select v-model="evalParticipation" class="form-control">
            <option value="">Kein spezifischer Arbeitsbericht</option>
            <option
              v-for="imp in implementationsFor(evalProjectId)"
              :key="imp.id"
              :value="imp.id"
            >
              {{ imp.title }} ({{ imp.student_name }})
            </option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Arbeitsplanung / Massnahmen (Lernende/r)</label>
          <textarea
            v-model="evalPlanningText"
            class="form-control"
            rows="4"
            placeholder="Wie gehe ich vor, um dieses Ziel zu erreichen?"
          />
        </div>

        <div v-if="auth.isTrainer" class="form-group">
          <label class="form-label">Beurteilung & Kompetenznachweis (Ausbildner/in)</label>
          <textarea
            v-model="evalText"
            class="form-control"
            rows="4"
            placeholder="Beurteilung der Arbeitsqualität, Selbstständigkeit und Zielerreichung..."
          />
        </div>

        <div class="flex-between">
          <button type="button" class="btn" @click="showEvalModal = false">
            Abbrechen
          </button>
          <button type="submit" class="btn btn-primary">Speichern</button>
        </div>
      </form>
    </ModalDialog>
  </div>
</template>

<style scoped>
.section-block {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.goal-list {
  list-style: none;
  padding: 0;
  margin: var(--space-2) 0 0 0;
}

.goal-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  padding: 0.55rem 0.75rem;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  margin-bottom: 0.4rem;
  font-size: 0.9rem;
}

.sub-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--space-4);
  margin-bottom: var(--space-3);
  background: var(--color-surface);
}

.eval-box {
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--space-3);
  font-size: 0.88rem;
}

.eval-box.evaluated {
  background: #f0fdf4;
  border-color: #bbf7d0;
}
</style>

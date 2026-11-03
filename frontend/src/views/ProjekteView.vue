<script setup>
import { ref, computed, onMounted, provide } from 'vue'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'
import ModalDialog from '../components/ui/ModalDialog.vue'
import MarkdownEditor from '../components/ui/MarkdownEditor.vue'
import ProjectCard from '../components/project/ProjectCard.vue'
import EditButton from '../components/ui/EditButton.vue'

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
const projPlanningReleased = ref(false)

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
const evalModalFocus = ref('planning') // 'planning' | 'eval'
const evalProjectId = ref(null)
const evalStudentId = ref('')
const evalGoal = ref('')
const evalParticipation = ref('')
const evalPlanningText = ref('')
const evalText = ref('')
const evalReleased = ref(false)

const rootProjects = computed(() =>
  projects.value.filter(
    (p) =>
      !p.parent_project ||
      !projects.value.some((parent) => parent.id === p.parent_project)
  )
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
  return rootProjects.value.filter((p) => {
    if (!treeStatusMatches(p.id)) return false
    if (q && !treeMatchesSearch(p, q)) return false
    return true
  })
})

function childrenOf(projectId) {
  return projects.value.filter((p) => p.parent_project === projectId)
}

function descendantProjects(projectId) {
  const result = []
  const stack = [...childrenOf(projectId)]
  while (stack.length) {
    const p = stack.pop()
    result.push(p)
    stack.push(...childrenOf(p.id))
  }
  return result
}

function projectMatchesSearch(project, q) {
  const impls = implementationsFor(project.id)
  const evals = evaluationsFor(project.id)
  const goalsStr = (project.goals || []).join(' ')
  const implStr = impls.map((i) => `${i.title} ${i.text} ${i.student_name}`).join(' ')
  const evalStr = evals
    .map((e) => `${e.goal} ${e.planning_text} ${e.eval_text} ${e.student_name}`)
    .join(' ')
  const hay =
    `${project.title} ${project.description || ''} ${project.author_name || ''} ${goalsStr} ${implStr} ${evalStr}`.toLowerCase()
  return hay.includes(q)
}

function treeMatchesSearch(project, q) {
  if (projectMatchesSearch(project, q)) return true
  return descendantProjects(project.id).some((p) => projectMatchesSearch(p, q))
}

function treeHasSearchDescendantMatch(project, q) {
  if (!q) return false
  return descendantProjects(project.id).some((p) => projectMatchesSearch(p, q))
}

function implementationsForTree(projectId) {
  const ids = new Set([
    projectId,
    ...descendantProjects(projectId).map((p) => p.id)
  ])
  return implementations.value.filter((i) => {
    if (!ids.has(i.project)) return false
    if (filterStudent.value && i.student !== Number(filterStudent.value)) return false
    return true
  })
}

function treeStatusMatches(projectId) {
  if (!filterStatus.value) return true
  const impls = implementationsForTree(projectId)
  const allDone = impls.length > 0 && impls.every((i) => i.is_done)
  return filterStatus.value === 'done' ? allDone : !allDone
}

function isExpanded(project) {
  if (expandedIds.value[project.id]) return true
  const q = searchQuery.value.trim().toLowerCase()
  return treeHasSearchDescendantMatch(project, q)
}

function toggleExpand(project) {
  expandedIds.value[project.id] = !isExpanded(project)
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
  projPlanningReleased.value = false
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
  projPlanningReleased.value = Boolean(proj.planning_released)
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
      due_date: projDueDate.value || null,
      planning_released: projPlanningReleased.value
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

async function togglePlanningReleased(proj) {
  error.value = ''
  try {
    await apiFetch(`/api/project/${proj.id}`, {
      method: 'PUT',
      body: { planning_released: !proj.planning_released }
    })
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
const activeImplProject = computed(() =>
  projects.value.find((p) => p.id === implProjectId.value) || null
)

function openNewImpl(proj) {
  error.value = ''
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
  error.value = ''
  editingImpl.value = item
  implProjectId.value = item.project
  implStudentId.value = item.student
  implTitle.value = item.title
  implText.value = item.text || ''
  implIsDone.value = item.is_done
  showImplModal.value = true
}

async function saveImpl() {
  error.value = ''
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
    if (implProjectId.value) {
      expandedIds.value[implProjectId.value] = true
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
function openNewEval(proj, prefillGoal = '', focus = 'planning') {
  editingEval.value = null
  evalModalFocus.value = focus
  evalProjectId.value = proj.id
  evalStudentId.value = auth.isStudent
    ? auth.user?.id
    : filterStudent.value || auth.companyStudents[0]?.id || ''
  evalGoal.value = prefillGoal || proj.goals?.[0] || ''
  evalParticipation.value = implementationsFor(proj.id)[0]?.id || ''
  evalPlanningText.value = ''
  evalText.value = ''
  evalReleased.value = false
  showEvalModal.value = true
}

function openEditEval(ev, focus = 'eval') {
  editingEval.value = ev
  evalModalFocus.value = focus
  evalProjectId.value = ev.project
  evalStudentId.value = ev.student
  evalGoal.value = ev.goal
  evalParticipation.value = ev.participation || ''
  evalPlanningText.value = ev.planning_text || ''
  evalText.value = ev.eval_text || ''
  evalReleased.value = Boolean(ev.eval_released)
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
          eval_text: evalText.value,
          eval_released: evalReleased.value
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
          eval_text: evalText.value,
          eval_released: evalReleased.value
        }
      })
    }
    showEvalModal.value = false
    await loadAll()
  } catch (e) {
    error.value = e.message
  }
}

async function toggleEvalReleased(ev) {
  error.value = ''
  try {
    await apiFetch(`/api/evaluation/${ev.id}`, {
      method: 'PUT',
      body: { eval_released: !ev.eval_released }
    })
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

provide('projectCtx', {
  auth,
  childrenOf,
  isExpanded,
  toggleExpand,
  implementationsFor,
  evaluationsFor,
  formatDate,
  openNewProject,
  openEditProject,
  togglePlanningReleased,
  deleteProject,
  openNewImpl,
  openEditImpl,
  toggleImplDone,
  deleteImpl,
  openNewEval,
  openEditEval,
  toggleEvalReleased,
  deleteEval
})
</script>

<template>
  <div>
    <!-- FULL-PAGE ARBEITSBERICHT EDITOR (Phase 2) -->
    <form
      v-if="showImplModal"
      class="editor-page"
      @submit.prevent="saveImpl"
    >
      <div class="page-header">
        <div class="flex-gap">
          <h1 class="page-title">
            {{ editingImpl ? 'Arbeitsbericht bearbeiten' : 'Neuer Arbeitsbericht' }}
          </h1>
          <span v-if="activeImplProject" class="badge badge-info">
            {{ activeImplProject.title }}
          </span>
        </div>

        <div class="editor-header-actions">
          <label class="editor-toggle-pill">
            <input v-model="implIsDone" type="checkbox" />
            <span>Aufgabe abgeschlossen</span>
          </label>
          <button type="button" class="btn" @click="showImplModal = false">
            Abbrechen
          </button>
          <button type="submit" class="btn btn-primary">
            Speichern
          </button>
        </div>
      </div>

      <div v-if="error" class="alert alert-error">{{ error }}</div>

      <div class="editor-card">
        <div class="editor-meta-bar">
          <div class="editor-meta-grid">
            <div class="form-group">
              <label class="form-label">Titel der Aufgabe / des Arbeitsberichts *</label>
              <input
                v-model="implTitle"
                type="text"
                class="form-control"
                placeholder="z.B. Fertigung und Vermessung Lagergehäuse"
                required
              />
            </div>

            <div v-if="auth.isTrainer && !editingImpl" class="form-group">
              <label class="form-label">Lernende/r *</label>
              <select v-model="implStudentId" class="form-control" required>
                <option v-for="stu in auth.companyStudents" :key="stu.id" :value="stu.id">
                  {{ stu.full_name }} ({{ stu.job_title }})
                </option>
              </select>
            </div>
          </div>

          <div
            v-if="activeImplProject && (activeImplProject.description || (activeImplProject.goals && activeImplProject.goals.length))"
            style="margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--color-border); font-size: 0.85rem"
          >
            <div class="text-muted">
              <strong>Projektauftrag:</strong> {{ activeImplProject.description || '–' }}
            </div>
            <div v-if="activeImplProject.goals && activeImplProject.goals.length" class="text-muted" style="margin-top: 4px">
              <strong>Lernziele:</strong> {{ activeImplProject.goals.join(' · ') }}
            </div>
          </div>
        </div>

        <MarkdownEditor
          v-model="implText"
          :full-page="true"
          :owner-id="Number(implStudentId || auth.user?.id)"
          placeholder="Beschreiben Sie die durchgeführten Arbeitsschritte, eingesetzten Maschinen, Schnittwerte und Messresultate. Fügen Sie Fotos oder PDF-Protokolle direkt über die Werkzeugleiste ein..."
        />
      </div>
    </form>

    <!-- STANDARD PROJECTS OVERVIEW -->
    <div v-else>
      <div class="page-header">
        <div>
          <h1 class="page-title">Projekte, Themen und Praktika</h1>
          <p class="page-subtitle">
            Aufgaben, Lernziele, Arbeitsberichte und Kompetenzbewertungen (Neueste zuerst)
          </p>
        </div>
        <div v-if="auth.isTrainer" class="flex-gap">
          <EditButton
            size="lg"
            show-label
            icon="folder-plus"
            variant="primary"
            label="Neues Projekt / Praktikum"
            @click="openNewProject(null)"
          />
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
        <ProjectCard
          v-for="proj in filteredProjects"
          :key="proj.id"
          :project="proj"
        />
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

        <div class="form-group">
          <label class="flex-gap" style="cursor: pointer">
            <input v-model="projPlanningReleased" type="checkbox" />
            <span>Planung für beteiligte Lernende freigeben</span>
          </label>
        </div>

        <div class="flex-between">
          <button type="button" class="btn" @click="showProjectModal = false">
            Abbrechen
          </button>
          <button type="submit" class="btn btn-primary">Speichern</button>
        </div>
      </form>
    </ModalDialog>

    <!-- Modal: Evaluation (Phase 1 Zielplanung & Phase 3 Bewertung durch Berufsbildner/in) -->
    <ModalDialog
      :show="showEvalModal"
      :title="
        evalModalFocus === 'planning'
          ? 'Phase 1: Zielplanung & Vorgaben (Berufsbildner/in)'
          : 'Phase 3: Kompetenzbewertung (Berufsbildner/in)'
      "
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
          <label class="form-label">Zugehöriger Arbeitsbericht aus Phase 2 (optional)</label>
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
          <label class="form-label">
            Phase 1: Planungsvorgabe / Erwartung (Berufsbildner/in)
          </label>
          <textarea
            v-model="evalPlanningText"
            class="form-control"
            rows="4"
            placeholder="Vorgaben, Hilfsmittel und Qualitätskriterien des Berufsbildners für dieses Lernziel..."
          />
        </div>

        <div class="form-group">
          <label class="form-label">
            Phase 3: Beurteilung & Kompetenznachweis (Berufsbildner/in)
          </label>
          <textarea
            v-model="evalText"
            class="form-control"
            rows="4"
            placeholder="Beurteilung der Arbeitsqualität, Selbstständigkeit und Zielerreichung nach der Ausführung..."
          />
        </div>

        <div class="form-group">
          <label class="flex-gap" style="cursor: pointer">
            <input v-model="evalReleased" type="checkbox" />
            <span>Bewertung für Lernende/n freigeben</span>
          </label>
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

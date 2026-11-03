<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'
import MarkdownEditor from '../components/ui/MarkdownEditor.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const isEdit = computed(() => Boolean(route.params.id))
const projectId = computed(() => (route.params.id ? Number(route.params.id) : null))

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const successMsg = ref('')

// Main project fields
const title = ref('')
const startDate = ref(new Date().toISOString().slice(0, 10))
const dueDate = ref('')
const description = ref('')
const documentObj = ref(null)
const pendingFile = ref(null)
const assignedStudents = ref([])
const goals = ref([])
const newGoalText = ref('')
const tasks = ref([])
const isPublished = ref(false)

async function loadProject() {
  if (!isEdit.value) {
    // Pre-select all company students if creating new
    assignedStudents.value = auth.companyStudents.map((s) => s.id)
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await apiFetch(`/api/project/${projectId.value}`)
    title.value = data.title || ''
    startDate.value = data.start_date || ''
    dueDate.value = data.due_date || ''
    description.value = data.description || ''
    documentObj.value = data.document || null
    assignedStudents.value = [...(data.assigned_students || [])]
    goals.value = [...(data.goals || [])]
    isPublished.value = Boolean(data.is_published)
    tasks.value = (data.tasks || []).map((t) => ({
      id: t.id,
      title: t.title || '',
      description: t.description || '',
      document: t.document || null,
      document_id: t.document_id || null,
      pendingFile: null,
      start_date: t.start_date || '',
      due_date: t.due_date || ''
    }))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(loadProject)

function addGoal() {
  const g = newGoalText.value.trim()
  if (g && !goals.value.includes(g)) {
    goals.value.push(g)
  }
  newGoalText.value = ''
}

function removeGoal(idx) {
  goals.value.splice(idx, 1)
}

function addTask() {
  tasks.value.push({
    id: null,
    title: '',
    description: '',
    document: null,
    document_id: null,
    pendingFile: null,
    start_date: startDate.value || '',
    due_date: dueDate.value || ''
  })
}

function removeTask(idx) {
  tasks.value.splice(idx, 1)
}

function onMainFileChange(e) {
  pendingFile.value = e.target.files?.[0] || null
}

function removeMainDocument() {
  documentObj.value = null
  pendingFile.value = null
}

function onTaskFileChange(task, e) {
  task.pendingFile = e.target.files?.[0] || null
}

function removeTaskDocument(task) {
  task.document = null
  task.document_id = null
  task.pendingFile = null
}

async function uploadFileAsDocument(file, docTitle) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('name', docTitle || file.name)
  fd.append('type', 'projekt')
  fd.append('owner', String(auth.user?.id))
  fd.append('is_done', 'true')
  return await apiFetch('/api/documents', {
    method: 'POST',
    body: fd
  })
}

async function savePlanning() {
  error.value = ''
  successMsg.value = ''

  if (!title.value.trim()) {
    error.value = 'Bitte einen Projekttitel eingeben.'
    return
  }

  const hasMainText = Boolean(description.value.trim())
  const hasMainDoc = Boolean(documentObj.value?.id || pendingFile.value)
  if (!hasMainText && !hasMainDoc) {
    error.value =
      'Beim Projekt muss mindestens ein Beschreibungstext oder ein Dokument hinterlegt sein.'
    return
  }

  for (let i = 0; i < tasks.value.length; i++) {
    const t = tasks.value[i]
    if (!t.title.trim()) {
      error.value = `Bitte einen Titel für Aufgabe ${i + 1} eingeben.`
      return
    }
    const hasTaskText = Boolean((t.description || '').trim())
    const hasTaskDoc = Boolean(t.document?.id || t.document_id || t.pendingFile)
    if (!hasTaskText && !hasTaskDoc) {
      error.value = `Bei Aufgabe "${t.title}" muss mindestens ein Text oder ein Dokument hinterlegt sein.`
      return
    }
  }

  saving.value = true
  try {
    let mainDocId = documentObj.value?.id || null
    if (pendingFile.value) {
      const uploaded = await uploadFileAsDocument(
        pendingFile.value,
        `Projektplan: ${title.value.trim()}`
      )
      mainDocId = uploaded.id
      documentObj.value = uploaded
      pendingFile.value = null
    }

    const preparedTasks = []
    for (const t of tasks.value) {
      let tDocId = t.document?.id || t.document_id || null
      if (t.pendingFile) {
        const uploadedTaskDoc = await uploadFileAsDocument(
          t.pendingFile,
          `Aufgabe: ${t.title.trim()}`
        )
        tDocId = uploadedTaskDoc.id
        t.document = uploadedTaskDoc
        t.document_id = uploadedTaskDoc.id
        t.pendingFile = null
      }
      preparedTasks.push({
        id: t.id || null,
        title: t.title.trim(),
        description: (t.description || '').trim(),
        document_id: tDocId,
        start_date: t.start_date || startDate.value || null,
        due_date: t.due_date || dueDate.value || null
      })
    }

    const payload = {
      title: title.value.trim(),
      description: description.value.trim(),
      document_id: mainDocId,
      start_date: startDate.value || null,
      due_date: dueDate.value || null,
      assigned_students: assignedStudents.value,
      goals: goals.value,
      tasks: preparedTasks,
      is_published: isPublished.value
    }

    if (isEdit.value) {
      const saved = await apiFetch(`/api/project/${projectId.value}`, {
        method: 'PUT',
        body: payload
      })
      router.push(`/projekte/${saved.id}`)
    } else {
      const created = await apiFetch('/api/project', {
        method: 'POST',
        body: payload
      })
      router.push(`/projekte/${created.id}`)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

async function deleteProject() {
  if (!isEdit.value) return
  if (!confirm(`Projekt "${title.value}" inklusive aller Aufgaben wirklich löschen?`)) return
  try {
    await apiFetch(`/api/project/${projectId.value}`, { method: 'DELETE' })
    router.push('/projekte')
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <div class="flex-gap" style="margin-bottom: 4px">
          <router-link
            :to="isEdit ? `/projekte/${projectId}` : '/projekte'"
            class="btn btn-sm"
          >
            ← Zurück
          </router-link>
          <span class="badge badge-info">Planung (Berufsbildner/in)</span>
        </div>
        <h1 class="page-title">
          {{ isEdit ? `Projekt planen: ${title || '...'}` : 'Neues Projekt planen' }}
        </h1>
        <p class="page-subtitle">
          Auftrag, Dokumente, Zeitraum, Lernende, Lernziele und (Sub-)Aufgaben festlegen
        </p>
      </div>

      <div v-if="isEdit" class="flex-gap">
        <router-link :to="`/projekte/${projectId}/auswertung`" class="btn">
          Zur Auswertung →
        </router-link>
        <button type="button" class="btn btn-danger" @click="deleteProject">
          Projekt löschen
        </button>
      </div>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>
    <div v-if="successMsg" class="alert alert-success">{{ successMsg }}</div>

    <div v-if="loading" class="card">Lade Projektdaten...</div>

    <form v-else @submit.prevent="savePlanning">
      <!-- 1. Basisdaten & Zeitraum -->
      <div class="card">
        <div class="card-header">
          <h3 style="margin: 0">1. Projektdaten & Zeitraum</h3>
        </div>

        <div class="form-group">
          <label class="form-label">Projekttitel *</label>
          <input
            v-model="title"
            type="text"
            class="form-control"
            placeholder="z.B. Basisausbildung Konventionelle Fertigung"
            required
          />
        </div>

        <div class="grid-2">
          <div class="form-group" style="margin-bottom: 0">
            <label class="form-label">Startdatum</label>
            <input v-model="startDate" type="date" class="form-control" />
          </div>
          <div class="form-group" style="margin-bottom: 0">
            <label class="form-label">End- / Abgabedatum</label>
            <input v-model="dueDate" type="date" class="form-control" />
          </div>
        </div>
      </div>

      <!-- 2. Projektbeschreibung (Text und/oder Dokument) -->
      <div class="card">
        <div class="card-header">
          <div>
            <h3 style="margin: 0">2. Projektauftrag (Text und/oder Dokument)</h3>
            <span class="text-muted">
              Es kann sowohl ein Text als auch ein Dokument hinterlegt werden; mindestens eines davon ist erforderlich.
            </span>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Projekttext / Beschreibung (optional wenn Dokument vorhanden)</label>
          <MarkdownEditor v-model="description" :rows="6" />
        </div>

        <div class="form-group" style="margin-bottom: 0">
          <label class="form-label">Projektdokument (optional wenn Text vorhanden)</label>
          <div v-if="documentObj" class="attached-doc">
            <div class="flex-gap">
              <strong>📄 {{ documentObj.name }}</strong>
              <span class="text-muted">({{ documentObj.filename }})</span>
              <a
                :href="`/api/documents/${documentObj.id}/file`"
                target="_blank"
                rel="noopener"
                class="btn btn-sm"
              >
                Öffnen
              </a>
            </div>
            <button type="button" class="btn btn-sm btn-danger" @click="removeMainDocument">
              Dokument entfernen
            </button>
          </div>
          <div v-else>
            <input type="file" class="form-control" @change="onMainFileChange" />
            <div v-if="pendingFile" class="text-muted" style="margin-top: 4px">
              Ausgewählt zum Hochladen: <strong>{{ pendingFile.name }}</strong>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. Lernende & Ziele zuweisen -->
      <div class="grid-2">
        <div class="card">
          <div class="card-header">
            <h3 style="margin: 0">3. Lernende zuweisen</h3>
          </div>
          <div v-if="auth.companyStudents.length === 0" class="text-muted">
            Keine Lernenden im Betrieb gefunden.
          </div>
          <div v-else class="student-check-list">
            <label
              v-for="stu in auth.companyStudents"
              :key="stu.id"
              class="student-check-item"
            >
              <input
                v-model="assignedStudents"
                type="checkbox"
                :value="stu.id"
              />
              <div>
                <strong>{{ stu.full_name }}</strong>
                <div class="text-muted">{{ stu.job_title }}</div>
              </div>
            </label>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3 style="margin: 0">4. Ziele zuweisen</h3>
          </div>

          <div class="flex-gap" style="margin-bottom: var(--space-3)">
            <input
              v-model="newGoalText"
              type="text"
              class="form-control"
              style="flex: 1"
              placeholder="Neues Lernziel eingeben..."
              @keydown.enter.prevent="addGoal"
            />
            <button type="button" class="btn" @click="addGoal">+ Hinzufügen</button>
          </div>

          <div v-if="goals.length === 0" class="text-muted">
            Noch keine Lernziele erfasst.
          </div>
          <div v-else class="goal-edit-list">
            <div v-for="(g, idx) in goals" :key="idx" class="goal-edit-row">
              <input
                v-model="goals[idx]"
                type="text"
                class="form-control"
                style="flex: 1"
              />
              <button
                type="button"
                class="btn btn-sm btn-danger"
                @click="removeGoal(idx)"
              >
                ✕
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 5. (Sub-)Aufgaben zuweisen -->
      <div class="card">
        <div class="card-header">
          <div>
            <h3 style="margin: 0">5. (Sub-)Aufgaben zuweisen ({{ tasks.length }})</h3>
            <span class="text-muted">
              Hat das Projekt Aufgaben, reichen Lernende pro Aufgabe ein Dokument/Text ein. Ohne Aufgaben erfolgt eine einzelne Abgabe fürs Gesamtprojekt.
            </span>
          </div>
          <button type="button" class="btn" @click="addTask">
            + Aufgabe hinzufügen
          </button>
        </div>

        <div v-if="tasks.length === 0" class="text-muted">
          Keine Unteraufgaben definiert – Lernende geben ein einzelnes Projektdokument / einen Gesamtbericht ab.
        </div>

        <div v-else class="task-list">
          <div
            v-for="(task, idx) in tasks"
            :key="task.id || 'new-' + idx"
            class="task-editor-box"
          >
            <div class="flex-between" style="margin-bottom: var(--space-3)">
              <strong>Aufgabe {{ idx + 1 }}</strong>
              <button
                type="button"
                class="btn btn-sm btn-danger"
                @click="removeTask(idx)"
              >
                Aufgabe entfernen
              </button>
            </div>

            <div class="grid-2">
              <div class="form-group">
                <label class="form-label">Titel der Aufgabe *</label>
                <input
                  v-model="task.title"
                  type="text"
                  class="form-control"
                  placeholder="z.B. Aufgabe 1: Werkstück fräsen"
                  required
                />
              </div>
              <div class="grid-2">
                <div class="form-group">
                  <label class="form-label">Startdatum</label>
                  <input v-model="task.start_date" type="date" class="form-control" />
                </div>
                <div class="form-group">
                  <label class="form-label">Fällig bis</label>
                  <input v-model="task.due_date" type="date" class="form-control" />
                </div>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Aufgabentext / Beschreibung</label>
              <textarea
                v-model="task.description"
                class="form-control"
                rows="3"
                placeholder="Beschreibung der Aufgabe..."
              />
            </div>

            <div class="form-group" style="margin-bottom: 0">
              <label class="form-label">Aufgabendokument (optional wenn Text vorhanden)</label>
              <div v-if="task.document" class="attached-doc">
                <div class="flex-gap">
                  <strong>📄 {{ task.document.name }}</strong>
                  <a
                    :href="`/api/documents/${task.document.id}/file`"
                    target="_blank"
                    rel="noopener"
                    class="btn btn-sm"
                  >
                    Öffnen
                  </a>
                </div>
                <button
                  type="button"
                  class="btn btn-sm btn-danger"
                  @click="removeTaskDocument(task)"
                >
                  Entfernen
                </button>
              </div>
              <div v-else>
                <input
                  type="file"
                  class="form-control"
                  @change="(e) => onTaskFileChange(task, e)"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 6. Freigabe & Speichern -->
      <div class="card publish-bar">
        <label class="publish-toggle">
          <input v-model="isPublished" type="checkbox" />
          <div>
            <strong>Freigabe zur Anzeige an die Lernenden</strong>
            <div class="text-muted">
              Sobald freigegeben, sehen die zugewiesenen Lernenden das Projekt (Planung ist für Lernende Read-Only) und können ihre Durchführung einreichen.
            </div>
          </div>
        </label>

        <div class="flex-gap">
          <router-link
            :to="isEdit ? `/projekte/${projectId}` : '/projekte'"
            class="btn"
          >
            Abbrechen
          </router-link>
          <button type="submit" class="btn btn-primary" :disabled="saving">
            {{ saving ? 'Speichert...' : 'Planung speichern' }}
          </button>
        </div>
      </div>
    </form>
  </div>
</template>

<style scoped>
.attached-doc {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.student-check-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.student-check-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0.6rem var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.student-check-item:hover {
  background: var(--color-surface-muted);
}

.goal-edit-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.goal-edit-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.task-editor-box {
  padding: var(--space-4);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
}

.publish-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.publish-toggle {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  cursor: pointer;
}

.publish-toggle input {
  margin-top: 4px;
}
</style>

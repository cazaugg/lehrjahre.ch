<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'
import MarkdownEditor from '../components/ui/MarkdownEditor.vue'
import DocumentViewer from '../components/ui/DocumentViewer.vue'
import ProjectStudentList from '../components/ui/ProjectStudentList.vue'
import ProjectStudentReview from '../components/ui/ProjectStudentReview.vue'
import LernzielLabel from '../components/ui/LernzielLabel.vue'
import { isMarkdownEditable } from '../utils/documents'

const route = useRoute()
const auth = useAuthStore()

const projectId = computed(() => Number(route.params.id))

const project = ref(null)
const loading = ref(false)
const savingTargetId = ref(null)
const error = ref('')
const successMsg = ref('')

// Selected student for trainer read-only inspection of Durchführung & Auswertung
const selectedStudentId = ref(null)

// Local draft state for student submissions keyed by target project/task ID
const drafts = ref({})

// Full-page Markdown editor for the current submission target
const editingSubmissionTarget = ref(null)
const editorContent = ref('')
const editorLoading = ref(false)

const SUBMISSION_FILE_ACCEPT =
  '.pdf,.docx,.xlsx,.zip,.png,.jpg,.jpeg,.webp,.gif,.txt,.csv,.md'

const hasSubtasks = computed(
  () => (project.value?.tasks || []).length > 0
)

// Targets for Durchführung: subtasks if present, otherwise the root project itself
const submissionTargets = computed(() => {
  if (!project.value) return []
  if (hasSubtasks.value) {
    return project.value.tasks.map((t, idx) => ({
      ...t,
      isSubtask: true,
      indexLabel: `Aufgabe ${idx + 1}`
    }))
  }
  return [
    {
      ...project.value,
      isSubtask: false,
      indexLabel: 'Projektabgabe'
    }
  ]
})

const availableStudents = computed(() => {
  if (!project.value) return []
  const assigned = project.value.assigned_student_users || []
  if (assigned.length > 0) return assigned
  return auth.companyStudents
})

const activeStudentId = computed(() => {
  if (auth.isStudent) return auth.user?.id
  return selectedStudentId.value
})

async function loadProject() {
  loading.value = true
  error.value = ''
  editingSubmissionTarget.value = null
  editorContent.value = ''
  try {
    const data = await apiFetch(`/api/project/${projectId.value}`)
    project.value = data
    initDrafts()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(loadProject)
watch(() => route.params.id, () => {
  selectedStudentId.value = null
  loadProject()
})

function getParticipation(targetId, studentId = activeStudentId.value) {
  if (!project.value || !studentId) return null
  return (
    (project.value.participations || []).find(
      (p) => p.project === targetId && p.student === Number(studentId)
    ) || null
  )
}

function toggleStudent(studentId) {
  selectedStudentId.value =
    selectedStudentId.value === studentId ? null : studentId
}

function emptyDraft() {
  return {
    document: null,
    document_id: null,
    pendingFile: null,
    docMode: 'none',
    docContent: '',
    docEdited: false,
    originalDocumentId: null
  }
}

function ensureDraft(targetId) {
  if (!drafts.value[targetId]) {
    drafts.value[targetId] = emptyDraft()
  }
  return drafts.value[targetId]
}

function initDrafts() {
  if (!project.value || !auth.isStudent) {
    drafts.value = {}
    return
  }
  const map = {}
  for (const target of submissionTargets.value) {
    const existing = getParticipation(target.id, auth.user?.id)
    const doc = existing?.document || null
    map[target.id] = {
      document: doc,
      document_id: existing?.document_id || null,
      pendingFile: null,
      docMode: doc ? (isMarkdownEditable(doc) ? 'text' : 'file') : 'none',
      docContent: '',
      docEdited: false,
      originalDocumentId: existing?.document_id || null
    }
  }
  drafts.value = map
}

function onSubmissionFileChange(targetId, event) {
  const file = event.target.files?.[0] || null
  const draft = ensureDraft(targetId)
  draft.pendingFile = file
  if (file) draft.docMode = 'file'
  event.target.value = ''
}

function clearPendingFile(targetId) {
  const draft = ensureDraft(targetId)
  draft.pendingFile = null
  draft.docMode = draft.document
    ? isMarkdownEditable(draft.document)
      ? 'text'
      : 'file'
    : 'none'
}

function removeSubmissionDoc(targetId) {
  const draft = ensureDraft(targetId)
  draft.document = null
  draft.document_id = null
  draft.pendingFile = null
  draft.docContent = ''
  draft.docEdited = false
  draft.docMode = 'none'
}

async function openTextEditor(target) {
  error.value = ''
  editorLoading.value = false
  const draft = ensureDraft(target.id)
  editorContent.value = draft.docContent || ''

  const doc = draft.document
  if (doc && isMarkdownEditable(doc)) {
    if (!editorContent.value) {
      editorLoading.value = true
      try {
        const data = await apiFetch(`/api/documents/${doc.id}`)
        editorContent.value = data?.content || ''
        draft.docContent = editorContent.value
      } catch (e) {
        error.value = e.message
        return
      } finally {
        editorLoading.value = false
      }
    }
  } else if (!doc && !editorContent.value) {
    const existing = getParticipation(target.id, auth.user?.id)
    if (existing?.text) {
      editorContent.value = existing.text
    }
  }

  editingSubmissionTarget.value = target
}

function closeTextEditor() {
  if (editingSubmissionTarget.value) {
    const draft = ensureDraft(editingSubmissionTarget.value.id)
    draft.docMode = draft.pendingFile
      ? 'file'
      : draft.document
        ? isMarkdownEditable(draft.document)
          ? 'text'
          : 'file'
        : 'none'
    draft.docContent = ''
    draft.docEdited = false
  }
  editingSubmissionTarget.value = null
  editorContent.value = ''
  editorLoading.value = false
  error.value = ''
}

async function saveFromEditor(target, releaseNow = false) {
  const draft = ensureDraft(target.id)
  draft.docContent = editorContent.value
  draft.docMode = 'text'
  draft.docEdited = true
  const saved = await saveStudentSubmission(target, releaseNow)
  if (saved) {
    editingSubmissionTarget.value = null
    editorContent.value = ''
  }
}

async function saveStudentSubmission(target, releaseNow = false) {
  error.value = ''
  successMsg.value = ''
  const draft = ensureDraft(target.id)
  const hasDoc = Boolean(draft.document?.id || draft.document_id || draft.pendingFile)
  const textContent = (draft.docContent || '').trim()
  const hasTextDoc = draft.docMode === 'text' && Boolean(textContent)

  if (draft.docMode === 'text' && draft.docEdited && !textContent) {
    error.value = 'Bitte erfassen Sie einen Inhalt für das Textdokument.'
    return false
  }

  if (draft.docMode === 'text' && !draft.docEdited && !hasDoc) {
    error.value = 'Bitte erfassen Sie einen Inhalt für das Textdokument.'
    return false
  }

  if (releaseNow && !hasDoc && !hasTextDoc) {
    error.value = 'Für die Abgabe muss ein Dokument eingereicht werden.'
    return false
  }

  if (
    releaseNow &&
    !confirm(
      'Möchten Sie diese Abgabe verbindlich freigeben? Nach der Freigabe kann nichts mehr geändert werden.'
    )
  ) {
    return false
  }

  savingTargetId.value = target.id
  let createdDocId = null
  try {
    let docId = draft.document?.id || draft.document_id || null
    const docName = `Abgabe: ${target.title}`

    if (draft.docMode === 'text' && textContent) {
      const existingDoc = draft.document
      if (existingDoc && isMarkdownEditable(existingDoc)) {
        const updated = await apiFetch(`/api/documents/${existingDoc.id}`, {
          method: 'PUT',
          body: { name: docName, content: textContent }
        })
        docId = updated.id
      } else {
        const created = await apiFetch('/api/documents', {
          method: 'POST',
          body: {
            name: docName,
            description: '',
            content: textContent,
            type: 'projekt',
            owner: auth.user?.id,
            is_done: true,
            is_template: false
          }
        })
        docId = created.id
        createdDocId = created.id
      }
    } else if (draft.docMode === 'file' && draft.pendingFile) {
      const fd = new FormData()
      fd.append('file', draft.pendingFile)
      fd.append('name', docName)
      fd.append('type', 'projekt')
      fd.append('owner', String(auth.user?.id))
      fd.append('is_done', 'true')
      const uploaded = await apiFetch('/api/documents', {
        method: 'POST',
        body: fd
      })
      docId = uploaded.id
      createdDocId = uploaded.id
    } else if (draft.docMode === 'none') {
      docId = null
    }

    const existing = getParticipation(target.id, auth.user?.id)
    const payload = {
      title: target.title,
      // Keep legacy text only when no document replaces it.
      text: docId ? '' : existing?.text || '',
      document_id: docId,
      is_done: releaseNow
    }
    if (existing) {
      await apiFetch(`/api/implementation/${existing.id}`, {
        method: 'PUT',
        body: payload
      })
    } else {
      await apiFetch('/api/implementation', {
        method: 'POST',
        body: {
          project: target.id,
          ...payload
        }
      })
    }

    const oldDocId = draft.originalDocumentId
    if (oldDocId && oldDocId !== docId) {
      try {
        await apiFetch(`/api/documents/${oldDocId}`, { method: 'DELETE' })
      } catch {
        // The old document is already unlinked; an orphaned file is not fatal.
      }
    }

    await loadProject()
    successMsg.value = releaseNow
      ? 'Abgabe erfolgreich eingereicht und freigegeben.'
      : 'Entwurf gespeichert.'
    return true
  } catch (e) {
    if (createdDocId) {
      try {
        await apiFetch(`/api/documents/${createdDocId}`, { method: 'DELETE' })
      } catch {
        // Best-effort cleanup after a failed participation save.
      }
    }
    error.value = e.message
    return false
  } finally {
    savingTargetId.value = null
  }
}

async function undoStudentSubmission(part) {
  error.value = ''
  successMsg.value = ''
  if (
    !confirm(
      `Freigabe der Abgabe von ${part.student_name} wirklich rückgängig machen?`
    )
  )
    return
  try {
    await apiFetch(`/api/implementation/${part.id}`, {
      method: 'PUT',
      body: { is_done: false }
    })
    await loadProject()
    successMsg.value =
      'Freigabe wurde rückgängig gemacht. Der/die Lernende kann die Abgabe wieder bearbeiten.'
  } catch (e) {
    error.value = e.message
  }
}

// Evaluations for the active student
const studentEvaluations = computed(() => {
  if (!project.value || !activeStudentId.value) return []
  return (project.value.evaluations || []).filter(
    (e) => e.student === Number(activeStudentId.value)
  )
})

const overallEval = computed(() =>
  studentEvaluations.value.find(
    (e) => e.project === project.value?.id && e.target_type === 'project'
  )
)

function taskEvalFor(taskId) {
  return studentEvaluations.value.find(
    (e) => e.project === taskId && e.target_type === 'task'
  )
}

function goalEvalFor(goalText) {
  return studentEvaluations.value.find(
    (e) =>
      e.project === project.value?.id &&
      (e.target_type === 'goal' || !e.target_type) &&
      e.goal === goalText
  )
}

const hasVisibleEvaluation = computed(() => {
  if (!project.value) return false
  return Boolean(
    project.value.global_eval_text ||
      studentEvaluations.value.length > 0 ||
      project.value.is_completed
  )
})

function formatScore(ev) {
  if (!ev || ev.score_value === null || ev.score_value === undefined) return null
  if (ev.score_type === 'percent') return `${ev.score_value} %`
  return `Note ${ev.score_value}`
}

function formatDate(d) {
  if (!d) return '–'
  return new Date(d).toLocaleDateString('de-CH')
}
</script>

<template>
  <div>
    <form
      v-if="editingSubmissionTarget"
      class="editor-page"
      @submit.prevent="saveFromEditor(editingSubmissionTarget, false)"
    >
      <div class="page-header">
        <div>
          <div class="flex-gap" style="margin-bottom: 6px">
            <button type="button" class="btn btn-sm" @click="closeTextEditor">
              ← Zurück zur Abgabe
            </button>
            <span class="badge badge-info">
              {{ editingSubmissionTarget.indexLabel }}
            </span>
          </div>
          <h1 class="page-title">Abgabe: {{ editingSubmissionTarget.title }}</h1>
          <p class="page-subtitle">Textdokument für die Projektdurchführung</p>
        </div>
        <div class="editor-header-actions">
          <button type="button" class="btn" @click="closeTextEditor">
            Abbrechen
          </button>
          <button
            type="submit"
            class="btn"
            :disabled="savingTargetId === editingSubmissionTarget.id"
          >
            Zwischenspeichern
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="savingTargetId === editingSubmissionTarget.id"
            @click="saveFromEditor(editingSubmissionTarget, true)"
          >
            Abgeben / Freigeben
          </button>
        </div>
      </div>

      <div v-if="error" class="alert alert-error">{{ error }}</div>

      <div v-if="editorLoading" class="card">Dokument wird geladen...</div>
      <div v-else class="editor-card">
        <MarkdownEditor
          v-model="editorContent"
          :full-page="true"
          :owner-id="auth.user?.id"
          attachment-type="projekt"
          placeholder="Ausgeführte Arbeiten, Erkenntnisse, Messresultate..."
        />
      </div>
    </form>

    <template v-else>
      <div v-if="loading" class="card">Lade Projekt...</div>
      <div v-else-if="error && !project" class="alert alert-error">{{ error }}</div>

      <div v-else-if="project">
      <!-- Page Header -->
      <div class="page-header">
        <div>
          <div class="flex-gap" style="margin-bottom: 6px">
            <router-link to="/projekte" class="btn btn-sm">
              ← Alle Projekte
            </router-link>
            <span
              class="badge"
              :class="
                project.is_completed
                  ? 'badge-success'
                  : project.is_published
                    ? 'badge-info'
                    : 'badge-neutral'
              "
            >
              {{
                project.is_completed
                  ? 'Abgeschlossen'
                  : project.is_published
                    ? 'Freigegeben'
                    : 'Entwurf (Nicht freigegeben)'
              }}
            </span>
          </div>
          <h1 class="page-title">{{ project.title }}</h1>
          <p class="page-subtitle">
            Zeitraum: {{ formatDate(project.start_date) }} bis {{ formatDate(project.due_date) }}
            <span v-if="project.author_name"> · Berufsbildner/in: {{ project.author_name }}</span>
          </p>
        </div>

        <div v-if="project.can_manage" class="flex-gap">
          <router-link :to="`/projekte/${project.id}/planung`" class="btn">
            Planung bearbeiten
          </router-link>
          <router-link :to="`/projekte/${project.id}/auswertung`" class="btn btn-primary">
            Auswertung öffnen
          </router-link>
        </div>
      </div>

      <div v-if="error" class="alert alert-error">{{ error }}</div>
      <div v-if="successMsg" class="alert alert-success">{{ successMsg }}</div>

      <!-- ===================================================== -->
      <!-- ABSCHNITT 1: PLANUNG (Read-Only)                      -->
      <!-- ===================================================== -->
      <div class="card">
        <div class="card-header">
          <div>
            <h2 class="section-heading">1. Planung & Auftrag</h2>
            <span class="text-muted">Vorgaben, Lernziele und Aufgaben (Schreibgeschützt)</span>
          </div>
        </div>

        <!-- Zugewiesene Lernende -->
        <div
          v-if="
            !auth.isTrainer &&
            project.assigned_student_users &&
            project.assigned_student_users.length > 0
          "
          class="detail-item"
        >
          <div class="detail-label">Zugewiesene Lernende</div>
          <div class="flex-gap" style="margin-top: 4px">
            <span
              v-for="stu in project.assigned_student_users"
              :key="stu.id"
              class="badge badge-info"
            >
              {{ stu.full_name }} ({{ stu.job_title }})
            </span>
          </div>
        </div>

        <!-- Projektbeschreibung (Text) -->
        <div v-if="project.description" class="detail-item">
          <div class="detail-label">Projektbeschreibung</div>
          <div class="readonly-text-box">
            <MarkdownEditor :model-value="project.description" :readonly="true" />
          </div>
        </div>

        <!-- Projektdokument -->
        <div v-if="project.document" class="detail-item">
          <div class="detail-label">Projektdokument</div>
          <div class="doc-link-bar">
            <DocumentViewer :document="project.document" />
          </div>
        </div>

        <!-- Lernziele -->
        <div v-if="(project.goals || []).length > 0" class="detail-item">
          <div class="detail-label">Zugewiesene Ziele</div>
          <ul class="clean-list">
            <li v-for="(g, idx) in project.goals" :key="idx" class="goal-line">
              🎯 <LernzielLabel :goal="g" />
            </li>
          </ul>
        </div>

        <!-- (Sub-)Aufgaben Übersicht in der Planung -->
        <div v-if="hasSubtasks" class="detail-item">
          <div class="detail-label">Zugeordnete Aufgaben ({{ project.tasks.length }})</div>
          <div class="task-overview-list">
            <div
              v-for="(task, idx) in project.tasks"
              :key="task.id"
              class="task-overview-item"
            >
              <div class="flex-between">
                <strong>Aufgabe {{ idx + 1 }}: {{ task.title }}</strong>
                <span class="text-muted">
                  {{ formatDate(task.start_date) }} – {{ formatDate(task.due_date) }}
                </span>
              </div>
              <p
                v-if="task.description"
                style="white-space: pre-line; margin: 6px 0 0 0"
              >
                {{ task.description }}
              </p>
              <div v-if="task.document" class="doc-link-bar" style="margin-top: 8px">
                <DocumentViewer :document="task.document" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Lernende: Abgabe & Auswertung pro Lernende/r -->
      <ProjectStudentList
        v-if="auth.isTrainer"
        :project="project"
        :students="availableStudents"
        :selected-student-id="selectedStudentId"
        @toggle="toggleStudent"
      >
        <template #body="{ student }">
          <ProjectStudentReview
            :project="project"
            :student="student"
            @undo-release="undoStudentSubmission"
          />
        </template>
      </ProjectStudentList>

      <template v-if="!auth.isTrainer">
        <!-- ===================================================== -->
        <!-- ABSCHNITT 2: DURCHFÜHRUNG                             -->
        <!-- ===================================================== -->
        <div class="card">
        <div class="card-header">
          <div>
            <h2 class="section-heading">2. Durchführung & Abgabe</h2>
            <span class="text-muted">
              <template v-if="hasSubtasks">
                Pro zugeordneter Aufgabe wird ein Dokument eingereicht (Textdokument oder Datei).
              </template>
              <template v-else>
                Da dieses Projekt keine Unteraufgaben hat, wird eine einzelne Projektabgabe als Dokument eingereicht.
              </template>
            </span>
          </div>
        </div>

        <div class="submission-list">
          <div
            v-for="target in submissionTargets"
            :key="target.id"
            class="submission-box"
          >
            <div class="flex-between" style="margin-bottom: var(--space-3)">
              <div>
                <span class="badge badge-neutral" style="margin-right: 6px">
                  {{ target.indexLabel }}
                </span>
                <strong>{{ target.title }}</strong>
              </div>

              <div>
                <span
                  v-if="getParticipation(target.id)?.is_done"
                  class="badge badge-success"
                >
                  Abgegeben & gesperrt
                </span>
                <span v-else class="badge badge-warning">
                  Offen / In Bearbeitung
                </span>
              </div>
            </div>

            <!-- FALL A: Lernende/r & noch NICHT abgegeben & Projekt nicht abgeschlossen -> Editierbar -->
            <div
              v-if="
                auth.isStudent &&
                !getParticipation(target.id)?.is_done &&
                !project.is_completed
              "
            >
              <div class="form-group">
                <label class="form-label">Dokument / Abgabe</label>

                <!-- Selected file, not uploaded yet -->
                <div v-if="drafts[target.id]?.pendingFile" class="doc-link-bar">
                  <span>
                    📄 <strong>{{ drafts[target.id].pendingFile.name }}</strong>
                    <span class="text-muted">
                      · wird beim Speichern hochgeladen
                      <template v-if="drafts[target.id].document">
                        und ersetzt das bisherige Dokument
                      </template>
                    </span>
                  </span>
                  <button
                    type="button"
                    class="btn btn-sm"
                    @click="clearPendingFile(target.id)"
                  >
                    Auswahl entfernen
                  </button>
                </div>

                <!-- Existing document -->
                <template v-else-if="drafts[target.id]?.document">
                  <div class="doc-link-bar">
                    <DocumentViewer :document="drafts[target.id].document">
                      <template #actions>
                        <button
                          v-if="isMarkdownEditable(drafts[target.id].document)"
                          type="button"
                          class="btn btn-sm"
                          @click="openTextEditor(target)"
                        >
                          Bearbeiten
                        </button>
                        <label v-else class="btn btn-sm">
                          Ersetzen
                          <input
                            type="file"
                            :accept="SUBMISSION_FILE_ACCEPT"
                            style="display: none"
                            @change="(e) => onSubmissionFileChange(target.id, e)"
                          />
                        </label>
                        <button
                          type="button"
                          class="btn btn-sm btn-danger"
                          @click="removeSubmissionDoc(target.id)"
                        >
                          Entfernen
                        </button>
                      </template>
                    </DocumentViewer>
                  </div>
                </template>

                <!-- No document yet -->
                <div v-else class="submission-doc-actions">
                  <button
                    type="button"
                    class="btn btn-primary"
                    @click="openTextEditor(target)"
                  >
                    Textdokument erstellen
                  </button>
                  <label class="btn">
                    Datei hochladen
                    <input
                      type="file"
                      :accept="SUBMISSION_FILE_ACCEPT"
                      style="display: none"
                      @change="(e) => onSubmissionFileChange(target.id, e)"
                    />
                  </label>
                </div>
              </div>

              <div class="flex-between" style="margin-top: var(--space-3)">
                <span class="text-muted">
                  Nach der Abgabe/Freigabe kann nichts mehr geändert werden.
                </span>
                <div class="flex-gap">
                  <button
                    type="button"
                    class="btn"
                    :disabled="savingTargetId === target.id"
                    @click="saveStudentSubmission(target, false)"
                  >
                    Zwischenspeichern
                  </button>
                  <button
                    type="button"
                    class="btn btn-primary"
                    :disabled="savingTargetId === target.id"
                    @click="saveStudentSubmission(target, true)"
                  >
                    Abgeben / Freigeben
                  </button>
                </div>
              </div>
            </div>

            <!-- FALL B: Read-Only (Bereits abgegeben ODER Ansicht für Berufsbildner/in) -->
            <div v-else>
              <div v-if="!getParticipation(target.id)" class="text-muted">
                Noch keine Durchführung / Abgabe vorhanden.
              </div>
              <div v-else>
                <div
                  v-if="getParticipation(target.id).text"
                  class="detail-item"
                >
                  <div class="detail-label">Eingereichter Text</div>
                  <div class="readonly-text-box" style="white-space: pre-line">
                    {{ getParticipation(target.id).text }}
                  </div>
                </div>

                <div
                  v-if="getParticipation(target.id).document"
                  class="detail-item"
                >
                  <div class="detail-label">Eingereichtes Dokument</div>
                  <div class="doc-link-bar">
                    <DocumentViewer :document="getParticipation(target.id).document" />
                  </div>
                </div>

                <!-- Berufsbildner kann die Freigabe rückgängig machen -->
                <div
                  v-if="
                    project.can_manage &&
                    getParticipation(target.id).is_done &&
                    !project.is_completed
                  "
                  style="margin-top: var(--space-3)"
                >
                  <button
                    type="button"
                    class="btn btn-sm"
                    @click="undoStudentSubmission(getParticipation(target.id))"
                  >
                    ↩ Freigabe rückgängig machen (Zur Bearbeitung öffnen)
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ===================================================== -->
      <!-- ABSCHNITT 3: AUSWERTUNG (Read-Only)                   -->
      <!-- ===================================================== -->
      <div class="card">
        <div class="card-header">
          <div>
            <h2 class="section-heading">3. Auswertung & Bewertung</h2>
            <span class="text-muted">
              Beurteilung durch den/die Berufsbildner/in (Schreibgeschützt)
            </span>
          </div>
          <router-link
            v-if="project.can_manage"
            :to="`/projekte/${project.id}/auswertung`"
            class="btn btn-sm btn-primary"
          >
            Auswertung bearbeiten
          </router-link>
        </div>

        <div v-if="!hasVisibleEvaluation" class="text-muted">
          Die Auswertung wurde noch nicht freigegeben.
        </div>

        <div v-else>
          <!-- Globaler Auswertungstext -->
          <div v-if="project.global_eval_text" class="detail-item">
            <div class="detail-label">Auswertungstext global</div>
            <div class="readonly-text-box" style="white-space: pre-line">
              {{ project.global_eval_text }}
            </div>
          </div>

          <!-- Auswertung fürs gesamte Projekt (pro Student) -->
          <div v-if="overallEval" class="detail-item">
            <div class="flex-between" style="margin-bottom: 4px">
              <div class="detail-label">Beurteilung Gesamtprojekt</div>
              <span v-if="formatScore(overallEval)" class="badge badge-success">
                Bewertung Gesamtprojekt: {{ formatScore(overallEval) }}
              </span>
            </div>
            <div class="readonly-text-box" style="white-space: pre-line">
              {{ overallEval.eval_text || 'Keine Textbemerkung.' }}
            </div>
          </div>

          <!-- Auswertung pro Aufgabe -->
          <div v-if="hasSubtasks" class="detail-item">
            <div class="detail-label" style="margin-bottom: 6px">
              Auswertung pro Aufgabe
            </div>
            <div class="task-overview-list">
              <div
                v-for="(task, idx) in project.tasks"
                :key="'eval-task-' + task.id"
                class="task-overview-item"
              >
                <div class="flex-between">
                  <strong>Aufgabe {{ idx + 1 }}: {{ task.title }}</strong>
                  <span
                    v-if="formatScore(taskEvalFor(task.id))"
                    class="badge badge-success"
                  >
                    {{ formatScore(taskEvalFor(task.id)) }}
                  </span>
                </div>
                <p
                  style="white-space: pre-line; margin: 6px 0 0 0"
                  :class="{ 'text-muted': !taskEvalFor(task.id)?.eval_text }"
                >
                  {{
                    taskEvalFor(task.id)?.eval_text ||
                    'Noch keine Einzelbemerkung zu dieser Aufgabe.'
                  }}
                </p>
              </div>
            </div>
          </div>

          <!-- Auswertung pro Ziel -->
          <div v-if="(project.goals || []).length > 0" class="detail-item">
            <div class="detail-label" style="margin-bottom: 6px">
              Auswertung der Lernziele
            </div>
            <div class="task-overview-list">
              <div
                v-for="(g, idx) in project.goals"
                :key="'eval-goal-' + idx"
                class="task-overview-item"
              >
                <strong>🎯 <LernzielLabel :goal="g" /></strong>
                <p
                  style="white-space: pre-line; margin: 6px 0 0 0"
                  :class="{ 'text-muted': !goalEvalFor(g)?.eval_text }"
                >
                  {{ goalEvalFor(g)?.eval_text || 'Noch keine Rückmeldung zu diesem Ziel.' }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
      </template>
    </div>
    </template>
  </div>
</template>

<style scoped>
.section-heading {
  margin: 0;
  font-size: 1.15rem;
}

.readonly-text-box {
  padding: var(--space-3);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.doc-link-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.clean-list {
  list-style: none;
  padding: 0;
  margin: 4px 0 0 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.clean-list li {
  padding: 0.5rem 0.75rem;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
}

.task-overview-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: 4px;
}

.task-overview-item {
  padding: var(--space-3);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.submission-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.submission-box {
  padding: var(--space-4);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.submission-doc-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>

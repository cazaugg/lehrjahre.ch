<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { apiFetch } from '../../api'
import { useAuthStore } from '../../stores/auth'
import ModalDialog from './ModalDialog.vue'
import MarkdownEditor from './MarkdownEditor.vue'
import DocumentViewer from './DocumentViewer.vue'
import EditButton from './EditButton.vue'
import { getDocumentDownloadUrl } from '../../utils/documents'

const props = defineProps({
  documentType: { type: String, default: '' },
  documentTypes: { type: Array, default: null },
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  ownerId: { type: Number, default: null },
  allowTemplates: { type: Boolean, default: true },
  preferTextEditor: { type: Boolean, default: false }
})

const auth = useAuthStore()
const documents = ref([])
const loading = ref(false)
const error = ref('')

const documentTypeLabels = {
  zeugnis: 'Zeugnis',
  kursnachweis: 'Kursnachweis',
  ausbildungsgespraech: 'Ausbildungsgespräch',
  lernjournal: 'Lernjournal',
  wissen: 'Wissen',
  vertrag: 'Vertrag',
  bewerbung: 'Bewerbung',
  profilbild: 'Profilbild',
  sonstiges: 'Sonstiges'
}

const types = computed(() => {
  if (props.documentTypes && props.documentTypes.length > 0) {
    return props.documentTypes
  }
  return props.documentType ? [props.documentType] : []
})

const hasMultipleTypes = computed(() => types.value.length > 1)

const canCreate = computed(() => {
  const activeTypes = types.value
  if (activeTypes.includes('lernjournal')) {
    return auth.isStudent
  }
  if (
    activeTypes.every((t) =>
      ['ausbildungsgespraech', 'vertrag', 'bewerbung'].includes(t)
    )
  ) {
    return auth.isTrainer
  }
  return true
})

function canEditDoc(doc) {
  if (!doc) return false
  if (doc.is_template) return auth.isTrainer
  if (doc.type === 'lernjournal') {
    return auth.isStudent && doc.owner === auth.user?.id
  }
  if (['ausbildungsgespraech', 'vertrag', 'bewerbung'].includes(doc.type)) {
    return auth.isTrainer
  }
  if (['zeugnis', 'kursnachweis'].includes(doc.type)) {
    return auth.isTrainer || doc.owner === auth.user?.id
  }
  return auth.isTrainer || doc.owner === auth.user?.id
}

function canDeleteDoc(doc) {
  if (!doc) return false
  if (doc.is_template) return auth.isTrainer
  if (doc.type === 'lernjournal') {
    return auth.isStudent && doc.owner === auth.user?.id
  }
  if (
    ['zeugnis', 'kursnachweis', 'ausbildungsgespraech', 'vertrag', 'bewerbung'].includes(
      doc.type
    )
  ) {
    return auth.isTrainer
  }
  return auth.isTrainer || doc.owner === auth.user?.id
}

// Feedback state for Lernjournal Rückmeldung (Supervisor)
const editingFeedbackDocId = ref(null)
const feedbackDraft = ref('')

function startEditFeedback(doc) {
  expandedIds.value[doc.id] = true
  editingFeedbackDocId.value = doc.id
  feedbackDraft.value = doc.feedback || ''
}

function cancelEditFeedback() {
  editingFeedbackDocId.value = null
  feedbackDraft.value = ''
}

async function saveFeedback(doc) {
  error.value = ''
  try {
    await apiFetch(`/api/documents/${doc.id}`, {
      method: 'PUT',
      body: { feedback: feedbackDraft.value }
    })
    editingFeedbackDocId.value = null
    await loadDocuments()
  } catch (e) {
    error.value = e.message
  }
}

async function deleteFeedback(doc) {
  if (!confirm('Rückmeldung zu diesem Lernjournal-Eintrag wirklich löschen?')) return
  error.value = ''
  try {
    await apiFetch(`/api/documents/${doc.id}`, {
      method: 'PUT',
      body: { feedback: '' }
    })
    if (editingFeedbackDocId.value === doc.id) {
      editingFeedbackDocId.value = null
    }
    await loadDocuments()
  } catch (e) {
    error.value = e.message
  }
}

function typeLabel(type) {
  return documentTypeLabels[type] || type
}

// Filter & Search state
const searchQuery = ref('')
const filterStudent = ref('')
const filterType = ref('')
const filterStatus = ref('')
const expandedIds = ref({})

// Editor / Modal state
const showModal = ref(false)
const editingDoc = ref(null)
const mode = ref('file') // 'file' | 'text'

const showFullPageEditor = computed(
  () => showModal.value && mode.value === 'text'
)
const showFileModal = computed(
  () => showModal.value && mode.value === 'file'
)

const formName = ref('')
const formDescription = ref('')
const formContent = ref('')
const formOwner = ref('')
const formType = ref('')
const formIsDone = ref(false)
const formIsTemplate = ref(false)
const selectedFile = ref(null)

const templatesLoading = ref(false)
const showTemplatePicker = ref(false)
const allTemplates = ref([])

// Templates usable in the current document-type context
const availableTemplates = computed(() => {
  const activeTypes = types.value
  return allTemplates.value.filter(
    (tpl) => activeTypes.length === 0 || activeTypes.includes(tpl.type)
  )
})

async function openTemplatePicker() {
  error.value = ''
  showTemplatePicker.value = true
  templatesLoading.value = true
  try {
    allTemplates.value = await apiFetch(
      '/api/documents?is_template=true&include_content=true'
    )
  } catch (e) {
    error.value = e.message
    showTemplatePicker.value = false
  } finally {
    templatesLoading.value = false
  }
}

function useTemplate(tpl) {
  showTemplatePicker.value = false
  openCreate('text', tpl)
}


const filteredDocs = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return documents.value
    .filter((d) => !d.is_template)
    .filter((d) => {
      if (props.ownerId && d.owner !== props.ownerId) return false
      if (filterStudent.value && d.owner !== Number(filterStudent.value)) return false
      if (filterType.value && d.type !== filterType.value) return false
      if (filterStatus.value === 'done' && !d.is_done) return false
      if (filterStatus.value === 'open' && d.is_done) return false
      if (q) {
        const hay = `${d.name} ${d.description || ''} ${d.owner_name || ''} ${d.author_name || ''} ${d.content || ''}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
})

function isTextDocument(doc) {
  if (!doc) return true
  if (doc.content) return true
  const fn = (doc.filename || '').toLowerCase()
  return fn.endsWith('.md') || fn.endsWith('.txt')
}

function toggleExpand(id) {
  expandedIds.value[id] = !expandedIds.value[id]
}

async function loadDocuments() {
  loading.value = true
  error.value = ''
  try {
    const results = await Promise.all(
      types.value.map(async (type) => {
        const params = new URLSearchParams({
          type,
          include_content: 'true'
        })
        if (props.ownerId) {
          params.set('owner', String(props.ownerId))
        }
        return apiFetch(`/api/documents?${params.toString()}`)
      })
    )
    documents.value = results
      .flat()
      .sort((a, b) => {
        const diff =
          new Date(b.updated_date || 0) - new Date(a.updated_date || 0)
        return diff !== 0 ? diff : b.id - a.id
      })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

watch(
  () => [types.value.join(','), props.ownerId],
  () => {
    showModal.value = false
    loadDocuments()
  }
)
onMounted(loadDocuments)

function openCreate(initialMode = null, fromTemplate = null) {
  error.value = ''
  editingDoc.value = null
  mode.value = initialMode || (props.preferTextEditor ? 'text' : 'file')
  formOwner.value =
    props.ownerId ||
    (auth.isStudent
      ? auth.user?.id
      : filterStudent.value || auth.companyStudents[0]?.id || auth.user?.id)
  formType.value = filterType.value || types.value[0] || ''

  if (fromTemplate) {
    mode.value = 'text'
    formName.value = fromTemplate.name.replace(/^Vorlage:?\s*/i, '')
    formDescription.value = fromTemplate.description || ''
    formContent.value = fromTemplate.content || ''
    formType.value = fromTemplate.type || formType.value
  } else {
    formName.value = ''
    formDescription.value = ''
    formContent.value = ''
  }
  formIsDone.value = false
  formIsTemplate.value = false
  selectedFile.value = null
  showModal.value = true
}

function openEdit(doc) {
  error.value = ''
  editingDoc.value = doc
  mode.value = isTextDocument(doc) ? 'text' : 'file'
  formName.value = doc.name
  formDescription.value = doc.description || ''
  formContent.value = doc.content || ''
  formOwner.value = doc.owner
  formType.value = doc.type || ''
  formIsDone.value = doc.is_done
  formIsTemplate.value = doc.is_template
  selectedFile.value = null
  showModal.value = true
}

function closeEditor() {
  showModal.value = false
}

function onFileChange(event) {
  const file = event.target.files?.[0] || null
  selectedFile.value = file
  if (file && !formName.value) {
    formName.value = file.name
  }
}

async function saveDocument() {
  error.value = ''
  try {
    const ownerToSave = Number(formOwner.value || auth.user?.id)
    if (editingDoc.value) {
      const payload = {
        name: formName.value,
        description: formDescription.value,
        is_done: formIsDone.value,
        is_template: formIsTemplate.value
      }
      if (mode.value === 'text') {
        payload.content = formContent.value
      }
      await apiFetch(`/api/documents/${editingDoc.value.id}`, {
        method: 'PUT',
        body: payload
      })
      expandedIds.value[editingDoc.value.id] = true
    } else if (mode.value === 'file') {
      if (!selectedFile.value) {
        error.value = 'Bitte wählen Sie eine Datei zum Hochladen aus.'
        return
      }
      const fd = new FormData()
      fd.append('file', selectedFile.value)
      fd.append('name', formName.value || selectedFile.value.name)
      fd.append('description', formDescription.value)
      fd.append('type', formType.value)
      fd.append('owner', String(ownerToSave))
      fd.append('is_done', String(formIsDone.value))
      fd.append('is_template', String(formIsTemplate.value))

      const created = await apiFetch('/api/documents', {
        method: 'POST',
        body: fd
      })
      expandedIds.value[created.id] = true
    } else {
      const created = await apiFetch('/api/documents', {
        method: 'POST',
        body: {
          name: formName.value,
          description: formDescription.value,
          content: formContent.value,
          type: formType.value,
          owner: ownerToSave,
          is_done: formIsDone.value,
          is_template: formIsTemplate.value
        }
      })
      expandedIds.value[created.id] = true
    }
    showModal.value = false
    await loadDocuments()
  } catch (e) {
    error.value = e.message
  }
}

async function toggleDone(doc) {
  try {
    await apiFetch(`/api/documents/${doc.id}`, {
      method: 'PUT',
      body: { is_done: !doc.is_done }
    })
    await loadDocuments()
  } catch (e) {
    error.value = e.message
  }
}

async function deleteDocument(doc) {
  if (!confirm(`Dokument "${doc.name}" wirklich löschen?`)) return
  try {
    await apiFetch(`/api/documents/${doc.id}`, { method: 'DELETE' })
    await loadDocuments()
  } catch (e) {
    error.value = e.message
  }
}

function formatDate(iso) {
  if (!iso) return '–'
  return new Date(iso).toLocaleDateString('de-CH')
}
</script>

<template>
  <div>
    <!-- FULL-PAGE TEXT / MARKDOWN EDITOR VIEW -->
    <form
      v-if="showFullPageEditor"
      class="editor-page"
      @submit.prevent="saveDocument"
    >
      <div class="page-header">
        <div class="flex-gap">
          <h1 class="page-title">
            {{ editingDoc ? 'Dokument bearbeiten' : 'Neues Textdokument' }}
          </h1>
          <span v-if="formType" class="badge badge-type">
            {{ typeLabel(formType) }}
          </span>
        </div>

        <div class="editor-header-actions">
          <label class="editor-toggle-pill">
            <input v-model="formIsDone" type="checkbox" />
            <span>Abgeschlossen / visiert</span>
          </label>
          <label
            v-if="auth.isTrainer && allowTemplates"
            class="editor-toggle-pill"
          >
            <input v-model="formIsTemplate" type="checkbox" />
            <span>Als Vorlage</span>
          </label>
          <button type="button" class="btn" @click="closeEditor">
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
              <label class="form-label">Titel / Dokumentname *</label>
              <input
                v-model="formName"
                type="text"
                class="form-control"
                placeholder="z.B. Lernjournal KW 45 – Fräsen & Messtechnik"
                required
              />
            </div>

            <div class="form-group">
              <label class="form-label">Kurzbeschreibung / Bemerkung</label>
              <input
                v-model="formDescription"
                type="text"
                class="form-control"
                placeholder="Kurze Zusammenfassung oder Zeitraum..."
              />
            </div>

            <div v-if="!editingDoc && hasMultipleTypes" class="form-group">
              <label class="form-label">Dokumenttyp *</label>
              <select v-model="formType" class="form-control" required>
                <option v-for="type in types" :key="type" :value="type">
                  {{ typeLabel(type) }}
                </option>
              </select>
            </div>

            <div
              v-if="auth.isTrainer && !editingDoc && !ownerId && !formIsTemplate"
              class="form-group"
            >
              <label class="form-label">Zugehörige/r Lernende/r *</label>
              <select v-model="formOwner" class="form-control" required>
                <option v-for="stu in auth.companyStudents" :key="stu.id" :value="stu.id">
                  {{ stu.full_name }} ({{ stu.job_title }})
                </option>
              </select>
            </div>
          </div>
        </div>

        <MarkdownEditor
          v-model="formContent"
          :full-page="true"
          :owner-id="Number(formOwner || auth.user?.id)"
          :is-template="formIsTemplate"
          placeholder="Schreiben Sie hier Ihren Bericht, Ihr Protokoll oder Ihren Lernjournaleintrag..."
        />
      </div>
    </form>

    <!-- STANDARD DOCUMENT OVERVIEW -->
    <div v-else>
      <div class="page-header">
        <div>
          <h1 class="page-title">{{ title }}</h1>
          <p v-if="subtitle" class="page-subtitle">{{ subtitle }}</p>
        </div>
        <div v-if="canCreate" class="flex-gap">
          <EditButton
            v-if="!preferTextEditor"
            size="lg"
            show-label
            label="Datei hochladen"
            icon="upload"
            variant="primary"
            @click="openCreate('file')"
          />
          <EditButton
            size="lg"
            show-label
            label="Textdokument erfassen"
            icon="file-plus"
            :variant="preferTextEditor ? 'primary' : 'default'"
            @click="openCreate('text')"
          />
          <EditButton
            v-if="allowTemplates"
            size="lg"
            show-label
            label="Vorlage laden"
            icon="copy"
            @click="openTemplatePicker"
          />
        </div>
      </div>

      <div v-if="error" class="alert alert-error">{{ error }}</div>

      <!-- Search & Filter Bar -->
      <div class="filter-bar">
        <input
          v-model="searchQuery"
          type="search"
          class="form-control filter-search"
          placeholder="Dokumente durchsuchen (Titel, Lernende/r, Inhalt)..."
        />

        <select
          v-if="auth.isTrainer && !ownerId"
          v-model="filterStudent"
          class="form-control filter-select"
        >
          <option value="">Alle Lernenden</option>
          <option v-for="stu in auth.companyStudents" :key="stu.id" :value="stu.id">
            {{ stu.full_name }}
          </option>
        </select>

        <select
          v-if="hasMultipleTypes"
          v-model="filterType"
          class="form-control filter-select"
        >
          <option value="">Alle Typen</option>
          <option v-for="type in types" :key="type" :value="type">
            {{ typeLabel(type) }}
          </option>
        </select>

        <select v-model="filterStatus" class="form-control filter-select">
          <option value="">Alle Status</option>
          <option value="open">In Bearbeitung</option>
          <option value="done">Abgeschlossen</option>
        </select>

        <span class="text-muted">{{ filteredDocs.length }} Einträge (Neueste zuerst)</span>
      </div>

      <!-- Documents List (Collapsed by default, expand on click) -->
      <div v-if="loading" class="card">Lade Dokumente...</div>
      <div v-else-if="filteredDocs.length === 0" class="card empty-state">
        Keine passenden Dokumente gefunden.
      </div>
      <div v-else>
        <div v-for="doc in filteredDocs" :key="doc.id" class="collapsible-card">
          <div class="collapsible-header" @click="toggleExpand(doc.id)">
            <div class="flex-gap">
              <span class="expand-indicator">{{ expandedIds[doc.id] ? '▾' : '▸' }}</span>
              <div>
                <div class="flex-gap">
                  <strong>{{ doc.name }}</strong>
                  <span v-if="hasMultipleTypes" class="badge badge-type">
                    {{ typeLabel(doc.type) }}
                  </span>
                  <span v-if="doc.owner_name" class="badge badge-info">
                    {{ doc.owner_name }}
                  </span>
                  <span class="badge" :class="doc.is_done ? 'badge-success' : 'badge-warning'">
                    {{ doc.is_done ? 'Abgeschlossen' : 'In Bearbeitung' }}
                  </span>
                  <span
                    v-if="doc.type === 'lernjournal' && doc.feedback"
                    class="badge badge-success"
                  >
                    Rückmeldung vorhanden
                  </span>
                </div>
                <div class="text-muted" style="margin-top: 2px">
                  Aktualisiert am {{ formatDate(doc.updated_date) }}
                  <span v-if="doc.description"> · {{ doc.description }}</span>
                </div>
              </div>
            </div>

            <div class="flex-gap" @click.stop>
              <EditButton
                label="Dokument herunterladen"
                icon="download"
                :href="getDocumentDownloadUrl(doc.id)"
                target="_self"
              />
              <EditButton
                v-if="doc.type === 'lernjournal' && auth.isTrainer"
                :label="doc.feedback ? 'Rückmeldung bearbeiten' : 'Rückmeldung erfassen'"
                icon="edit"
                variant="primary"
                @click="startEditFeedback(doc)"
              />
              <EditButton
                v-if="canEditDoc(doc)"
                :label="doc.is_done ? 'Als offen markieren' : 'Abschliessen'"
                :icon="doc.is_done ? 'undo' : 'check'"
                :variant="doc.is_done ? 'default' : 'success'"
                @click="toggleDone(doc)"
              />
              <EditButton
                v-if="canEditDoc(doc)"
                label="Dokument bearbeiten"
                icon="edit"
                @click="openEdit(doc)"
              />
              <EditButton
                v-if="canDeleteDoc(doc)"
                label="Dokument löschen"
                icon="delete"
                variant="danger"
                @click="deleteDocument(doc)"
              />
            </div>
          </div>

          <div v-if="expandedIds[doc.id]" class="collapsible-body">
            <div class="expanded-doc-layout">
              <div class="expanded-doc-main">
                <div
                  v-if="doc.author_name && doc.author_name !== doc.owner_name"
                  class="text-muted"
                  style="margin-bottom: var(--space-2)"
                >
                  Erstellt von {{ doc.author_name }}
                </div>

                <DocumentViewer
                  :document="doc"
                  :always-open="true"
                  :show-header="false"
                  :show-download="false"
                />
              </div>

              <!-- Lernjournal Rückmeldung Section -->
              <div
                v-if="doc.type === 'lernjournal'"
                class="expanded-doc-side feedback-section"
              >
                <div class="flex-between" style="margin-bottom: var(--space-2)">
                  <div class="flex-gap">
                    <strong>Rückmeldung (Vorgesetzte/r)</strong>
                    <span v-if="doc.feedback_author_name" class="text-muted">
                      · {{ doc.feedback_author_name }}
                    </span>
                  </div>
                  <div v-if="auth.isTrainer && editingFeedbackDocId !== doc.id" class="flex-gap">
                    <EditButton
                      :label="doc.feedback ? 'Rückmeldung bearbeiten' : 'Rückmeldung erfassen'"
                      icon="edit"
                      variant="primary"
                      @click="startEditFeedback(doc)"
                    />
                    <EditButton
                      v-if="doc.feedback"
                      label="Rückmeldung löschen"
                      icon="delete"
                      variant="danger"
                      @click="deleteFeedback(doc)"
                    />
                  </div>
                </div>

                <form
                  v-if="auth.isTrainer && editingFeedbackDocId === doc.id"
                  @submit.prevent="saveFeedback(doc)"
                >
                  <div class="form-group">
                    <textarea
                      v-model="feedbackDraft"
                      class="form-control"
                      rows="3"
                      placeholder="Rückmeldung zum Lernjournal-Eintrag verfassen..."
                    />
                  </div>
                  <div class="flex-gap">
                    <button type="submit" class="btn btn-primary btn-sm">
                      Rückmeldung speichern
                    </button>
                    <button type="button" class="btn btn-sm" @click="cancelEditFeedback">
                      Abbrechen
                    </button>
                  </div>
                </form>
                <p
                  v-else-if="doc.feedback"
                  style="margin: 0; white-space: pre-line"
                >
                  {{ doc.feedback }}
                </p>
                <p v-else class="text-muted" style="margin: 0">
                  Noch keine Rückmeldung vorhanden.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Binary File Upload / Metadata Modal -->
      <ModalDialog
        :show="showFileModal"
        :title="editingDoc ? 'Datei-Angaben bearbeiten' : 'Datei hochladen'"
        width="640px"
        @close="showModal = false"
      >
        <form @submit.prevent="saveDocument">
          <div v-if="!editingDoc" class="tabs" style="margin-bottom: var(--space-4)">
            <button
              type="button"
              class="tab-btn active"
            >
              Datei-Upload (PDF, Bild, Office)
            </button>
            <button
              type="button"
              class="tab-btn"
              @click="mode = 'text'"
            >
              Text / Bericht im Vollbild-Editor schreiben →
            </button>
          </div>

          <div
            v-if="!editingDoc && hasMultipleTypes"
            class="form-group"
          >
            <label class="form-label">Dokumenttyp *</label>
            <select v-model="formType" class="form-control" required>
              <option v-for="type in types" :key="type" :value="type">
                {{ typeLabel(type) }}
              </option>
            </select>
          </div>

          <div
            v-if="auth.isTrainer && !editingDoc && !ownerId && !formIsTemplate"
            class="form-group"
          >
            <label class="form-label">Zugehörige/r Lernende/r *</label>
            <select v-model="formOwner" class="form-control" required>
              <option v-for="stu in auth.companyStudents" :key="stu.id" :value="stu.id">
                {{ stu.full_name }} ({{ stu.job_title }})
              </option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Titel / Dokumentname *</label>
            <input v-model="formName" type="text" class="form-control" required />
          </div>

          <div class="form-group">
            <label class="form-label">Kurzbeschreibung / Bemerkung</label>
            <input v-model="formDescription" type="text" class="form-control" />
          </div>

          <div v-if="!editingDoc" class="form-group">
            <label class="form-label">Datei auswählen *</label>
            <input type="file" class="form-control" required @change="onFileChange" />
          </div>

          <div class="flex-gap" style="margin-bottom: var(--space-4)">
            <label class="flex-gap" style="cursor: pointer">
              <input v-model="formIsDone" type="checkbox" />
              <span>Als abgeschlossen / visiert markieren</span>
            </label>

            <label
              v-if="auth.isTrainer && allowTemplates"
              class="flex-gap"
              style="cursor: pointer"
            >
              <input v-model="formIsTemplate" type="checkbox" />
              <span>Als Vorlage für alle Lernenden speichern</span>
            </label>
          </div>

          <div class="flex-between">
            <button type="button" class="btn" @click="showModal = false">Abbrechen</button>
            <button type="submit" class="btn btn-primary">Speichern</button>
          </div>
        </form>
      </ModalDialog>

      <!-- Template Picker Modal -->
      <ModalDialog
        :show="showTemplatePicker"
        title="Vorlage laden"
        width="640px"
        @close="showTemplatePicker = false"
      >
        <div v-if="templatesLoading" class="card">Lade Vorlagen...</div>
        <div v-else-if="availableTemplates.length === 0" class="card empty-state">
          Keine passenden Vorlagen vorhanden. Vorlagen werden in der Sektion
          «Vorlagen» erstellt und gelten firmenweit.
        </div>
        <div v-else class="template-list">
          <div
            v-for="tpl in availableTemplates"
            :key="tpl.id"
            class="template-item"
          >
            <div>
              <strong>{{ tpl.name }}</strong>
              <div class="text-muted" style="margin-top: 2px">
                <span class="badge badge-type">{{ typeLabel(tpl.type) }}</span>
                {{ tpl.description || 'Vorlage als Markdown-Dokument übernehmen' }}
              </div>
            </div>
            <EditButton
              label="Vorlage verwenden"
              icon="copy"
              variant="primary"
              @click="useTemplate(tpl)"
            />
          </div>
        </div>
      </ModalDialog>
    </div>
  </div>
</template>

<style scoped>
.badge-type {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.template-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  padding: 0.6rem 0.75rem;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
}

.feedback-section {
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}
</style>

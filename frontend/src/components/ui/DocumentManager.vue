<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { apiFetch } from '../../api'
import { useAuthStore } from '../../stores/auth'
import ModalDialog from './ModalDialog.vue'
import MarkdownEditor from './MarkdownEditor.vue'

const props = defineProps({
  documentType: { type: String, required: true },
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

// Filter & Search state
const searchQuery = ref('')
const filterStudent = ref('')
const filterStatus = ref('')
const expandedIds = ref({})

// Modal state
const showModal = ref(false)
const editingDoc = ref(null)
const mode = ref('file') // 'file' | 'text'

const formName = ref('')
const formDescription = ref('')
const formContent = ref('')
const formOwner = ref('')
const formIsDone = ref(false)
const formIsTemplate = ref(false)
const selectedFile = ref(null)

const templates = computed(() => documents.value.filter((d) => d.is_template))

const filteredDocs = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return documents.value
    .filter((d) => !d.is_template)
    .filter((d) => {
      if (props.ownerId && d.owner !== props.ownerId) return false
      if (filterStudent.value && d.owner !== Number(filterStudent.value)) return false
      if (filterStatus.value === 'done' && !d.is_done) return false
      if (filterStatus.value === 'open' && d.is_done) return false
      if (q) {
        const hay = `${d.name} ${d.description || ''} ${d.owner_name || ''} ${d.author_name || ''} ${d.content || ''}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
})

function toggleExpand(id) {
  expandedIds.value[id] = !expandedIds.value[id]
}

async function loadDocuments() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({
      type: props.documentType,
      include_content: 'true'
    })
    if (props.ownerId) {
      params.set('owner', String(props.ownerId))
    }
    documents.value = await apiFetch(`/api/documents?${params.toString()}`)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

watch(() => [props.documentType, props.ownerId], loadDocuments)
onMounted(loadDocuments)

function openCreate(initialMode = null, fromTemplate = null) {
  editingDoc.value = null
  mode.value = initialMode || (props.preferTextEditor ? 'text' : 'file')
  formOwner.value =
    props.ownerId ||
    (auth.isStudent
      ? auth.user?.id
      : filterStudent.value || auth.companyStudents[0]?.id || auth.user?.id)

  if (fromTemplate) {
    mode.value = 'text'
    formName.value = fromTemplate.name.replace(/^Vorlage:?\s*/i, '')
    formDescription.value = fromTemplate.description || ''
    formContent.value = fromTemplate.content || ''
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
  editingDoc.value = doc
  mode.value = 'text'
  formName.value = doc.name
  formDescription.value = doc.description || ''
  formContent.value = doc.content || ''
  formOwner.value = doc.owner
  formIsDone.value = doc.is_done
  formIsTemplate.value = doc.is_template
  selectedFile.value = null
  showModal.value = true
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
      await apiFetch(`/api/documents/${editingDoc.value.id}`, {
        method: 'PUT',
        body: {
          name: formName.value,
          description: formDescription.value,
          content: formContent.value,
          is_done: formIsDone.value,
          is_template: formIsTemplate.value
        }
      })
    } else if (mode.value === 'file') {
      if (!selectedFile.value) {
        error.value = 'Bitte wählen Sie eine Datei zum Hochladen aus.'
        return
      }
      const fd = new FormData()
      fd.append('file', selectedFile.value)
      fd.append('name', formName.value || selectedFile.value.name)
      fd.append('description', formDescription.value)
      fd.append('type', props.documentType)
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
          type: props.documentType,
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
    <div class="page-header">
      <div>
        <h1 class="page-title">{{ title }}</h1>
        <p v-if="subtitle" class="page-subtitle">{{ subtitle }}</p>
      </div>
      <div class="flex-gap">
        <button
          v-if="!preferTextEditor"
          type="button"
          class="btn btn-primary"
          @click="openCreate('file')"
        >
          + Datei hochladen
        </button>
        <button
          type="button"
          class="btn"
          :class="{ 'btn-primary': preferTextEditor }"
          @click="openCreate('text')"
        >
          + Textdokument erfassen
        </button>
      </div>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>

    <!-- Templates Banner -->
    <div
      v-if="allowTemplates && templates.length > 0"
      class="card"
      style="background: var(--color-surface-muted)"
    >
      <div class="flex-between">
        <strong>Verfügbare Vorlagen</strong>
        <span class="text-muted">Direkt als neues Dokument übernehmen</span>
      </div>
      <div class="flex-gap" style="margin-top: var(--space-2)">
        <div v-for="tpl in templates" :key="tpl.id" class="template-pill">
          <span>{{ tpl.name }}</span>
          <button
            type="button"
            class="btn btn-sm btn-primary"
            @click="openCreate('text', tpl)"
          >
            Vorlage verwenden
          </button>
          <button
            v-if="auth.isTrainer"
            type="button"
            class="btn btn-sm"
            @click="openEdit(tpl)"
          >
            Bearbeiten
          </button>
        </div>
      </div>
    </div>

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
                <span v-if="doc.owner_name" class="badge badge-info">
                  {{ doc.owner_name }}
                </span>
                <span class="badge" :class="doc.is_done ? 'badge-success' : 'badge-warning'">
                  {{ doc.is_done ? 'Abgeschlossen' : 'In Bearbeitung' }}
                </span>
              </div>
              <div class="text-muted" style="margin-top: 2px">
                Aktualisiert am {{ formatDate(doc.updated_date) }}
                <span v-if="doc.description"> · {{ doc.description }}</span>
              </div>
            </div>
          </div>

          <div class="flex-gap" @click.stop>
            <a
              :href="`/api/documents/${doc.id}/file`"
              target="_blank"
              rel="noopener"
              class="btn btn-sm"
            >
              Datei öffnen
            </a>
          </div>
        </div>

        <div v-if="expandedIds[doc.id]" class="collapsible-body">
          <div class="flex-between" style="margin-bottom: var(--space-3)">
            <div class="text-muted">
              Dateipfad: <code>/data/documents/{{ doc.path }}</code>
              <span v-if="doc.author_name"> · Erstellt von {{ doc.author_name }}</span>
            </div>
            <div class="flex-gap">
              <button type="button" class="btn btn-sm" @click="toggleDone(doc)">
                {{ doc.is_done ? 'Als offen markieren' : 'Abschliessen' }}
              </button>
              <button type="button" class="btn btn-sm" @click="openEdit(doc)">
                Bearbeiten
              </button>
              <button
                type="button"
                class="btn btn-sm btn-danger"
                @click="deleteDocument(doc)"
              >
                Löschen
              </button>
            </div>
          </div>

          <div v-if="doc.content">
            <MarkdownEditor :model-value="doc.content" :readonly="true" />
          </div>
          <div v-else class="text-muted">
            Binärdatei ({{ doc.filename }}). Klicken Sie oben rechts auf «Datei öffnen», um das Dokument anzusehen.
          </div>
        </div>
      </div>
    </div>

    <!-- Create / Edit Modal -->
    <ModalDialog
      :show="showModal"
      :title="editingDoc ? 'Dokument bearbeiten' : 'Neues Dokument'"
      width="720px"
      @close="showModal = false"
    >
      <form @submit.prevent="saveDocument">
        <div v-if="!editingDoc" class="tabs" style="margin-bottom: var(--space-4)">
          <button
            type="button"
            class="tab-btn"
            :class="{ active: mode === 'file' }"
            @click="mode = 'file'"
          >
            Datei-Upload (PDF, Bild, Office)
          </button>
          <button
            type="button"
            class="tab-btn"
            :class="{ active: mode === 'text' }"
            @click="mode = 'text'"
          >
            Text / Protokoll schreiben
          </button>
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

        <div v-if="!editingDoc && mode === 'file'" class="form-group">
          <label class="form-label">Datei auswählen *</label>
          <input type="file" class="form-control" required @change="onFileChange" />
        </div>

        <div v-if="mode === 'text' || editingDoc" class="form-group">
          <label class="form-label">
            Inhalt (wird im Firmenordner unter /data/documents gespeichert)
          </label>
          <MarkdownEditor v-model="formContent" :rows="10" />
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
  </div>
</template>

<style scoped>
.template-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0.4rem 0.75rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
}
</style>

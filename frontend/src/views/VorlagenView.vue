<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'
import MarkdownEditor from '../components/ui/MarkdownEditor.vue'
import DocumentViewer from '../components/ui/DocumentViewer.vue'
import EditButton from '../components/ui/EditButton.vue'

const auth = useAuthStore()
const templates = ref([])
const loading = ref(false)
const error = ref('')
const expandedIds = ref({})

const documentTypeLabels = {
  zeugnis: 'Zeugnis',
  kursnachweis: 'Kursnachweis',
  ausbildungsgespraech: 'Ausbildungsgespräch',
  lernjournal: 'Lernjournal',
  wissen: 'Wissen',
  vertrag: 'Vertrag',
  bewerbung: 'Bewerbung',
  profilbild: 'Profilbild',
  projekt: 'Projekt',
  sonstiges: 'Sonstiges'
}

// Templates only make sense as markdown/document blueprints.
const templateTypes = [
  'ausbildungsgespraech',
  'zeugnis',
  'kursnachweis',
  'wissen',
  'vertrag',
  'bewerbung',
  'projekt',
  'sonstiges'
]

const searchQuery = ref('')

const filteredTemplates = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return templates.value
  return templates.value.filter((t) =>
    `${t.name} ${t.description || ''} ${t.type}`
      .toLowerCase()
      .includes(q)
  )
})

function typeLabel(type) {
  return documentTypeLabels[type] || type
}

function canManage() {
  return auth.isTrainer
}

async function loadTemplates() {
  loading.value = true
  error.value = ''
  try {
    templates.value = await apiFetch('/api/documents?is_template=true&include_content=true')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(loadTemplates)

// Editor state
const showEditor = ref(false)
const editingDoc = ref(null)
const formName = ref('')
const formDescription = ref('')
const formContent = ref('')
const formType = ref('sonstiges')

function openCreate() {
  error.value = ''
  editingDoc.value = null
  formName.value = ''
  formDescription.value = ''
  formContent.value = ''
  formType.value = 'sonstiges'
  showEditor.value = true
}

function openEdit(doc) {
  error.value = ''
  editingDoc.value = doc
  formName.value = doc.name
  formDescription.value = doc.description || ''
  formContent.value = doc.content || ''
  formType.value = doc.type || 'sonstiges'
  showEditor.value = true
}

function closeEditor() {
  showEditor.value = false
  editingDoc.value = null
}

async function saveTemplate() {
  error.value = ''
  try {
    if (editingDoc.value) {
      await apiFetch(`/api/documents/${editingDoc.value.id}`, {
        method: 'PUT',
        body: {
          name: formName.value,
          description: formDescription.value,
          content: formContent.value
        }
      })
      expandedIds.value[editingDoc.value.id] = true
    } else {
      const created = await apiFetch('/api/documents', {
        method: 'POST',
        body: {
          name: formName.value,
          description: formDescription.value,
          content: formContent.value,
          type: formType.value,
          owner: auth.user?.id,
          is_done: true,
          is_template: true
        }
      })
      expandedIds.value[created.id] = true
    }
    showEditor.value = false
    editingDoc.value = null
    await loadTemplates()
  } catch (e) {
    error.value = e.message
  }
}

async function deleteTemplate(doc) {
  if (!confirm(`Vorlage "${doc.name}" wirklich löschen?`)) return
  try {
    await apiFetch(`/api/documents/${doc.id}`, { method: 'DELETE' })
    await loadTemplates()
  } catch (e) {
    error.value = e.message
  }
}

function toggleExpand(id) {
  expandedIds.value[id] = !expandedIds.value[id]
}

function formatDate(iso) {
  if (!iso) return '–'
  return new Date(iso).toLocaleDateString('de-CH')
}
</script>

<template>
  <div>
    <!-- FULL-PAGE TEMPLATE EDITOR -->
    <form v-if="showEditor" class="editor-page" @submit.prevent="saveTemplate">
      <div class="page-header">
        <div class="flex-gap">
          <h1 class="page-title">
            {{ editingDoc ? 'Vorlage bearbeiten' : 'Neue Vorlage erstellen' }}
          </h1>
          <span class="badge badge-type">
            {{ editingDoc ? typeLabel(editingDoc.type) : 'Vorlage' }}
          </span>
        </div>

        <div class="editor-header-actions">
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
              <label class="form-label">Titel *</label>
              <input
                v-model="formName"
                type="text"
                class="form-control"
                placeholder="z.B. Vorlage Bildungsbericht / Ausbildungsgespräch"
                required
              />
            </div>

            <div class="form-group">
              <label class="form-label">Kurzbeschreibung</label>
              <input
                v-model="formDescription"
                type="text"
                class="form-control"
                placeholder="Wofür ist diese Vorlage gedacht..."
              />
            </div>

            <div v-if="!editingDoc" class="form-group">
              <label class="form-label">Dokumenttyp *</label>
              <select v-model="formType" class="form-control" required>
                <option v-for="type in templateTypes" :key="type" :value="type">
                  {{ typeLabel(type) }}
                </option>
              </select>
            </div>
          </div>
        </div>

        <p class="text-muted" style="margin-top: var(--space-2)">
          Die Vorlage wird firmenweit sichtbar und kann im Dokumentbereich über
          «Vorlage laden» als neues Dokument übernommen werden.
        </p>

        <MarkdownEditor
          v-model="formContent"
          :full-page="true"
          :owner-id="auth.user?.id"
          :is-template="true"
          :attachment-type="formType || 'sonstiges'"
          placeholder="Verfassen Sie hier die Vorlage im Markdown-Format (Struktur, Platzhalter, Hinweise)..."
        />
      </div>
    </form>

    <!-- TEMPLATE OVERVIEW -->
    <div v-else>
      <div class="page-header">
        <div>
          <h1 class="page-title">Vorlagen</h1>
          <p class="page-subtitle">
            Firmeneigene Markdown-Vorlagen – als Ausgangslage für neue Dokumente über «Vorlage laden» im Dokumentbereich
          </p>
        </div>
        <div v-if="canManage()" class="flex-gap">
          <EditButton
            size="lg"
            show-label
            label="Neue Vorlage"
            icon="file-plus"
            variant="primary"
            @click="openCreate"
          />
        </div>
      </div>

      <div v-if="error" class="alert alert-error">{{ error }}</div>

      <div class="filter-bar">
        <input
          v-model="searchQuery"
          type="search"
          class="form-control filter-search"
          placeholder="Vorlagen durchsuchen..."
        />
        <span class="text-muted">{{ filteredTemplates.length }} Vorlagen</span>
      </div>

      <div v-if="loading" class="card">Lade Vorlagen...</div>
      <div v-else-if="filteredTemplates.length === 0" class="card empty-state">
        <template v-if="searchQuery">
          Keine Vorlagen gefunden.
        </template>
        <template v-else>
          Noch keine Vorlagen vorhanden.
          <span v-if="canManage()"> Erstellen Sie die erste Vorlage mit «Neue Vorlage».</span>
          <span v-else> Fragen Sie Ihre Vorgesetzten nach firmeneigenen Vorlagen.</span>
        </template>
      </div>
      <div v-else>
        <div v-for="tpl in filteredTemplates" :key="tpl.id" class="collapsible-card">
          <div class="collapsible-header" @click="toggleExpand(tpl.id)">
            <div class="flex-gap">
              <span class="expand-indicator">{{ expandedIds[tpl.id] ? '▾' : '▸' }}</span>
              <div>
                <div class="flex-gap">
                  <strong>{{ tpl.name }}</strong>
                  <span class="badge badge-type">
                    {{ typeLabel(tpl.type) }}
                  </span>
                  <span v-if="tpl.author_name" class="badge badge-info">
                    {{ tpl.author_name }}
                  </span>
                </div>
                <div class="text-muted" style="margin-top: 2px">
                  Aktualisiert am {{ formatDate(tpl.updated_date) }}
                  <span v-if="tpl.description"> · {{ tpl.description }}</span>
                </div>
              </div>
            </div>

            <div class="flex-gap" @click.stop>
              <EditButton
                v-if="canManage()"
                label="Vorlage bearbeiten"
                icon="edit"
                @click="openEdit(tpl)"
              />
              <EditButton
                v-if="canManage()"
                label="Vorlage löschen"
                icon="delete"
                variant="danger"
                @click="deleteTemplate(tpl)"
              />
            </div>
          </div>

          <div v-if="expandedIds[tpl.id]" class="collapsible-body">
            <DocumentViewer
              :document="tpl"
              :always-open="true"
              :show-header="false"
              :show-download="false"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.badge-type {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
</style>

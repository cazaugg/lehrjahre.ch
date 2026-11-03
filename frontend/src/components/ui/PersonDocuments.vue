<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { apiFetch } from '../../api'
import { useAuthStore } from '../../stores/auth'
import EditButton from './EditButton.vue'
import ModalDialog from './ModalDialog.vue'

const props = defineProps({
  personId: { type: Number, required: true },
  role: { type: String, required: true },
  canEdit: { type: Boolean, default: false }
})

const auth = useAuthStore()
const vertragDocs = ref([])
const bewerbungDocs = ref([])
const error = ref('')

// Upload / Edit modal state
const showModal = ref(false)
const editingDoc = ref(null)
const formType = ref('vertrag')
const formName = ref('')
const formDescription = ref('')
const selectedFile = ref(null)

const canView = computed(
  () =>
    props.role === 'lernender' &&
    (auth.user?.id === props.personId ||
      props.canEdit ||
      auth.isSubordinate(props.personId))
)

const groups = computed(() => {
  const all = [
    { type: 'vertrag', label: 'Lehrvertrag', docs: vertragDocs.value },
    { type: 'bewerbung', label: 'Bewerbung', docs: bewerbungDocs.value }
  ]
  if (props.canEdit) return all
  return all.filter((group) => group.docs.length > 0)
})

async function loadDocuments() {
  if (!canView.value) return
  try {
    const [vertrag, bewerbung] = await Promise.all([
      apiFetch(`/api/documents?type=vertrag&owner=${props.personId}`),
      apiFetch(`/api/documents?type=bewerbung&owner=${props.personId}`)
    ])
    vertragDocs.value = vertrag.filter((doc) => !doc.is_template)
    bewerbungDocs.value = bewerbung.filter((doc) => !doc.is_template)
  } catch {
    vertragDocs.value = []
    bewerbungDocs.value = []
  }
}

function openUpload(type = 'vertrag') {
  error.value = ''
  editingDoc.value = null
  formType.value = type
  formName.value = ''
  formDescription.value = ''
  selectedFile.value = null
  showModal.value = true
}

function openEdit(doc) {
  error.value = ''
  editingDoc.value = doc
  formType.value = doc.type
  formName.value = doc.name
  formDescription.value = doc.description || ''
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

async function saveDoc() {
  error.value = ''
  try {
    if (editingDoc.value) {
      await apiFetch(`/api/documents/${editingDoc.value.id}`, {
        method: 'PUT',
        body: {
          name: formName.value,
          description: formDescription.value
        }
      })
    } else {
      if (!selectedFile.value) {
        error.value = 'Bitte eine Datei auswählen.'
        return
      }
      const fd = new FormData()
      fd.append('file', selectedFile.value)
      fd.append('name', formName.value || selectedFile.value.name)
      fd.append('description', formDescription.value)
      fd.append('type', formType.value)
      fd.append('owner', String(props.personId))
      fd.append('is_done', 'true')
      await apiFetch('/api/documents', {
        method: 'POST',
        body: fd
      })
    }
    showModal.value = false
    await loadDocuments()
  } catch (e) {
    error.value = e.message
  }
}

async function deleteDoc(doc) {
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

watch(() => props.personId, loadDocuments)
onMounted(loadDocuments)
</script>

<template>
  <div v-if="canView && (groups.length || canEdit)" class="person-documents">
    <div class="flex-between" style="margin-bottom: var(--space-3)">
      <h4 style="margin: 0">Dokumente (Lehrvertrag & Bewerbung)</h4>
      <div v-if="canEdit" class="flex-gap">
        <EditButton
          label="Lehrvertrag / Bewerbung hochladen"
          icon="upload"
          variant="primary"
          show-label
          @click="openUpload('vertrag')"
        />
      </div>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>

    <div v-for="group in groups" :key="group.type" class="document-group">
      <div class="document-group-title">{{ group.label }}</div>
      <div v-if="group.docs.length === 0" class="text-muted" style="font-size: 0.85rem">
        Kein Dokument hinterlegt.
      </div>
      <div v-for="doc in group.docs" :key="doc.id" class="document-row">
        <div>
          <a :href="`/api/documents/${doc.id}/file`" target="_blank" rel="noopener">
            {{ doc.name }}
          </a>
          <span v-if="doc.description" class="text-muted"> · {{ doc.description }}</span>
        </div>
        <div class="flex-gap">
          <span class="text-muted">{{ formatDate(doc.updated_date) }}</span>
          <template v-if="canEdit">
            <EditButton
              label="Dokument bearbeiten"
              icon="edit"
              @click="openEdit(doc)"
            />
            <EditButton
              label="Dokument löschen"
              icon="delete"
              variant="danger"
              @click="deleteDoc(doc)"
            />
          </template>
        </div>
      </div>
    </div>

    <ModalDialog
      :show="showModal"
      :title="editingDoc ? 'Dokument bearbeiten' : 'Lehrvertrag / Bewerbung hochladen'"
      @close="showModal = false"
    >
      <form @submit.prevent="saveDoc">
        <div v-if="!editingDoc" class="form-group">
          <label class="form-label">Dokumenttyp *</label>
          <select v-model="formType" class="form-control" required>
            <option value="vertrag">Lehrvertrag</option>
            <option value="bewerbung">Bewerbung</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Titel / Dokumentname *</label>
          <input v-model="formName" type="text" class="form-control" required />
        </div>

        <div class="form-group">
          <label class="form-label">Bemerkung</label>
          <input v-model="formDescription" type="text" class="form-control" />
        </div>

        <div v-if="!editingDoc" class="form-group">
          <label class="form-label">Datei auswählen *</label>
          <input type="file" class="form-control" required @change="onFileChange" />
        </div>

        <div class="flex-between">
          <button type="button" class="btn" @click="showModal = false">
            Abbrechen
          </button>
          <button type="submit" class="btn btn-primary">Speichern</button>
        </div>
      </form>
    </ModalDialog>
  </div>
</template>

<style scoped>
.person-documents {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.document-group {
  margin-bottom: var(--space-3);
}

.document-group-title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--color-text-muted);
  margin-bottom: var(--space-1);
}

.document-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  padding: 0.35rem 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 0.9rem;
}

.document-row:last-child {
  border-bottom: none;
}
</style>

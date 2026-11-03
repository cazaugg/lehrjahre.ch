<script setup>
import { ref, computed, watch, defineAsyncComponent, h } from 'vue'
import 'katex/dist/katex.min.css'
import { renderMarkdown } from '../../utils/markdown'
import { apiFetch } from '../../api'
import { useAuthStore } from '../../stores/auth'
import ModalDialog from './ModalDialog.vue'

const EditorLoading = {
  render: () => h('div', { class: 'md-editor-loading' }, 'Editor wird geladen…')
}

const MarkdownSourceEditor = defineAsyncComponent({
  loader: () => import('./MarkdownSourceEditor.vue'),
  loadingComponent: EditorLoading,
  delay: 150
})

const props = defineProps({
  modelValue: { type: String, default: '' },
  readonly: { type: Boolean, default: false },
  placeholder: { type: String, default: 'Inhalt im Markdown-Format eingeben...' },
  rows: { type: Number, default: 14 },
  fullPage: { type: Boolean, default: false },
  ownerId: { type: [Number, String], default: null },
  attachmentType: { type: String, default: 'sonstiges' },
  isTemplate: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue'])

const auth = useAuthStore()
const sourceEditorRef = ref(null)
const quickImageInputRef = ref(null)

// 'split' | 'edit' | 'preview'
const viewMode = ref(props.fullPage ? 'split' : 'edit')
watch(
  () => props.fullPage,
  (isFull) => {
    if (isFull && viewMode.value === 'edit') {
      viewMode.value = 'split'
    }
  }
)

const renderedHtml = computed(() => renderMarkdown(props.modelValue))

// Word, character, and line statistics
const stats = computed(() => {
  const text = (props.modelValue || '').trim()
  const chars = (props.modelValue || '').length
  const words = text ? text.split(/\s+/).length : 0
  const lines = props.modelValue ? props.modelValue.split('\n').length : 1
  return { words, chars, lines }
})

// File upload & linking state
const uploading = ref(false)
const uploadError = ref('')

// Attachment / Document Picker Modal state
const showAttachmentModal = ref(false)
const attachmentTab = ref('upload') // 'upload' | 'existing'
const modalFile = ref(null)
const modalTitle = ref('')
const modalInsertMode = ref('auto') // 'auto' | 'image' | 'link'

// Existing documents state
const existingDocs = ref([])
const loadingExisting = ref(false)
const existingSearch = ref('')
const existingFilter = ref('all') // 'all' | 'image' | 'doc'

const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.gif']

function isImageFilename(filename) {
  if (!filename) return false
  const lower = filename.toLowerCase()
  return IMAGE_EXTENSIONS.some((ext) => lower.endsWith(ext))
}

function cleanDisplayTitle(filename) {
  if (!filename) return 'Dokument'
  return filename.replace(/\.[^/.]+$/, '').replace(/[_-]+/g, ' ').trim() || filename
}

function formatSnippet(doc, mode = 'auto') {
  const url = `/api/documents/${doc.id}/file`
  const label = (doc.name || doc.filename || 'Dokument').replace(/[\[\]]/g, '')
  const asImage =
    mode === 'image' || (mode === 'auto' && isImageFilename(doc.filename))
  if (asImage) {
    return `![${label}](${url})`
  }
  return `[${label}](${url})`
}

function insertAtCursor(snippet) {
  if (sourceEditorRef.value && typeof sourceEditorRef.value.insertText === 'function') {
    sourceEditorRef.value.insertText(snippet)
  } else {
    const base = props.modelValue || ''
    const sep = base && !base.endsWith('\n') ? '\n\n' : ''
    emit('update:modelValue', `${base}${sep}${snippet}`)
  }
}

async function uploadSingleFile(file, customName = '') {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('name', (customName || cleanDisplayTitle(file.name)).trim())
  fd.append('description', 'Eingefügt im Markdown-Editor')
  fd.append('type', props.attachmentType || 'sonstiges')
  const targetOwner = props.ownerId || auth.user?.id
  if (targetOwner) {
    fd.append('owner', String(targetOwner))
  }
  fd.append('is_done', 'true')
  fd.append('is_template', String(Boolean(props.isTemplate)))

  return apiFetch('/api/documents', {
    method: 'POST',
    body: fd
  })
}

async function handleFilesUploadAndInsert(files, customTitle = '', mode = 'auto') {
  if (!files || files.length === 0) return
  uploading.value = true
  uploadError.value = ''
  try {
    const snippets = []
    for (const file of files) {
      const created = await uploadSingleFile(
        file,
        files.length === 1 ? customTitle : ''
      )
      snippets.push(formatSnippet(created, mode))
    }
    if (viewMode.value === 'preview') {
      viewMode.value = props.fullPage ? 'split' : 'edit'
    }
    insertAtCursor(snippets.join('\n\n'))
  } catch (e) {
    uploadError.value = e.message || 'Fehler beim Hochladen der Datei.'
  } finally {
    uploading.value = false
  }
}

function triggerQuickImageUpload() {
  uploadError.value = ''
  quickImageInputRef.value?.click()
}

async function onQuickImageSelected(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (files.length > 0) {
    await handleFilesUploadAndInsert(files, '', 'image')
  }
}

function openAttachmentPicker(initialTab = 'upload') {
  uploadError.value = ''
  attachmentTab.value = initialTab
  modalFile.value = null
  modalTitle.value = ''
  modalInsertMode.value = 'auto'
  showAttachmentModal.value = true
  if (initialTab === 'existing') {
    loadExistingDocuments()
  }
}

watch(attachmentTab, (tab) => {
  if (tab === 'existing' && existingDocs.value.length === 0) {
    loadExistingDocuments()
  }
})

function onModalFileChange(event) {
  const file = event.target.files?.[0] || null
  modalFile.value = file
  if (file && !modalTitle.value) {
    modalTitle.value = cleanDisplayTitle(file.name)
  }
  if (file) {
    modalInsertMode.value = isImageFilename(file.name) ? 'image' : 'link'
  }
}

async function submitModalUpload() {
  if (!modalFile.value) {
    uploadError.value = 'Bitte wählen Sie eine Datei aus.'
    return
  }
  await handleFilesUploadAndInsert(
    [modalFile.value],
    modalTitle.value,
    modalInsertMode.value
  )
  if (!uploadError.value) {
    showAttachmentModal.value = false
  }
}

async function loadExistingDocuments() {
  loadingExisting.value = true
  uploadError.value = ''
  try {
    const params = new URLSearchParams()
    if (props.ownerId) {
      params.set('owner', String(props.ownerId))
    }
    const query = params.toString() ? `?${params.toString()}` : ''
    existingDocs.value = (await apiFetch(`/api/documents${query}`)) || []
  } catch (e) {
    uploadError.value = e.message
  } finally {
    loadingExisting.value = false
  }
}

const filteredExistingDocs = computed(() => {
  const q = existingSearch.value.trim().toLowerCase()
  return existingDocs.value.filter((doc) => {
    const isImg = isImageFilename(doc.filename)
    if (existingFilter.value === 'image' && !isImg) return false
    if (existingFilter.value === 'doc' && isImg) return false
    if (q) {
      const hay = `${doc.name || ''} ${doc.filename || ''} ${doc.description || ''} ${doc.type || ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

function insertExistingDocument(doc, mode = 'auto') {
  if (viewMode.value === 'preview') {
    viewMode.value = props.fullPage ? 'split' : 'edit'
  }
  insertAtCursor(formatSnippet(doc, mode))
  showAttachmentModal.value = false
}

const typeLabels = {
  zeugnis: 'Zeugnis',
  kursnachweis: 'Kursnachweis',
  ausbildungsgespraech: 'Ausbildungsgespräch',
  lernjournal: 'Lernjournal',
  wissen: 'Wissen',
  vertrag: 'Vertrag',
  bewerbung: 'Bewerbung',
  profilbild: 'Profilbild',
  sonstiges: 'Anhang / Datei'
}

function formatDate(iso) {
  if (!iso) return '–'
  return new Date(iso).toLocaleDateString('de-CH')
}
</script>

<template>
  <div
    class="markdown-editor"
    :class="{
      'is-full-page': fullPage && !readonly,
      'is-readonly': readonly
    }"
  >
    <!-- Hidden file input for 1-click image upload -->
    <input
      v-if="!readonly"
      ref="quickImageInputRef"
      type="file"
      accept=".png,.jpg,.jpeg,.webp,.gif"
      multiple
      style="display: none"
      @change="onQuickImageSelected"
    />

    <!-- Top Editor Toolbar -->
    <div v-if="!readonly" class="md-toolbar">
      <div class="md-toolbar-actions">
        <button
          type="button"
          class="btn btn-sm md-action-btn"
          :disabled="uploading"
          title="Bild vom Computer auswählen, hochladen und im Text einfügen"
          @click="triggerQuickImageUpload"
        >
          <svg
            viewBox="0 0 24 24"
            width="14"
            height="14"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
          </svg>
          <span>Bild einfügen</span>
        </button>

        <button
          type="button"
          class="btn btn-sm md-action-btn"
          :disabled="uploading"
          title="PDF, Office-Dokument oder Bild hochladen und verlinken"
          @click="openAttachmentPicker('upload')"
        >
          <svg
            viewBox="0 0 24 24"
            width="14"
            height="14"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
          </svg>
          <span>Dokument hochladen</span>
        </button>

        <button
          type="button"
          class="btn btn-sm md-action-btn"
          :disabled="uploading"
          title="Bereits vorhandenes Dokument oder Bild suchen und im Text verlinken"
          @click="openAttachmentPicker('existing')"
        >
          <svg
            viewBox="0 0 24 24"
            width="14"
            height="14"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
          <span>Bestehendes Dokument verlinken</span>
        </button>

        <span v-if="uploading" class="badge badge-info">
          Datei wird hochgeladen…
        </span>
      </div>

      <div class="md-view-switcher" role="group" aria-label="Editor-Ansicht">
        <button
          type="button"
          class="view-mode-btn"
          :class="{ active: viewMode === 'edit' }"
          @click="viewMode = 'edit'"
        >
          Bearbeiten
        </button>
        <button
          type="button"
          class="view-mode-btn"
          :class="{ active: viewMode === 'split' }"
          @click="viewMode = 'split'"
        >
          Geteilte Ansicht
        </button>
        <button
          type="button"
          class="view-mode-btn"
          :class="{ active: viewMode === 'preview' }"
          @click="viewMode = 'preview'"
        >
          Vorschau
        </button>
      </div>
    </div>

    <div v-if="uploadError" class="md-upload-alert">
      <span>{{ uploadError }}</span>
      <button type="button" class="btn btn-sm" @click="uploadError = ''">OK</button>
    </div>

    <!-- Read-only Rendered View -->
    <div v-if="readonly" class="md-preview" v-html="renderedHtml" />

    <!-- Editable Workspace (Edit / Split / Preview) -->
    <div
      v-else
      class="md-workspace"
      :class="`mode-${viewMode}`"
    >
      <div v-show="viewMode === 'edit' || viewMode === 'split'" class="md-editor-pane">
        <MarkdownSourceEditor
          ref="sourceEditorRef"
          :model-value="modelValue"
          :placeholder="placeholder"
          :rows="rows"
          :full-page="fullPage"
          @update:model-value="emit('update:modelValue', $event)"
          @files-dropped="handleFilesUploadAndInsert"
        />
      </div>

      <div v-if="viewMode === 'split' || viewMode === 'preview'" class="md-preview-pane">
        <div v-if="viewMode === 'split'" class="md-preview-header">
          <span>Live-Vorschau</span>
          <span class="text-muted">Formeln ($…$), Bilder & Formatierung</span>
        </div>
        <div
          v-if="modelValue && modelValue.trim()"
          class="md-preview"
          v-html="renderedHtml"
        />
        <div v-else class="md-preview md-preview-empty text-muted">
          Die Vorschau Ihres Berichts erscheint hier automatisch während des Schreibens…
        </div>
      </div>
    </div>

    <!-- Footer with stats and hints -->
    <div v-if="!readonly" class="md-footer">
      <div class="md-stats">
        <span><strong>{{ stats.words }}</strong> Wörter</span>
        <span>·</span>
        <span><strong>{{ stats.chars }}</strong> Zeichen</span>
        <span>·</span>
        <span><strong>{{ stats.lines }}</strong> Zeilen</span>
      </div>
      <div class="text-muted md-hint">
        Tipp: Bilder & Dokumente per Drag & Drop oder Kopieren & Einfügen (Ctrl+V) direkt in den Editor ziehen
      </div>
    </div>

    <!-- Modal: Upload or Link Existing Document -->
    <ModalDialog
      :show="showAttachmentModal"
      title="Bild oder Dokument einfügen & verlinken"
      width="680px"
      @close="showAttachmentModal = false"
    >
      <div class="tabs" style="margin-bottom: var(--space-4)">
        <button
          type="button"
          class="tab-btn"
          :class="{ active: attachmentTab === 'upload' }"
          @click="attachmentTab = 'upload'"
        >
          Neue Datei hochladen
        </button>
        <button
          type="button"
          class="tab-btn"
          :class="{ active: attachmentTab === 'existing' }"
          @click="attachmentTab = 'existing'"
        >
          Bestehendes Dokument verlinken
        </button>
      </div>

      <!-- Tab 1: Upload new file -->
      <div v-if="attachmentTab === 'upload'">
        <div class="form-group">
          <label class="form-label">
            Datei auswählen (PDF, Bild, Word, Excel, CSV, Text, ZIP) *
          </label>
          <input
            type="file"
            class="form-control"
            accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.md,.txt,.csv,.docx,.xlsx,.zip"
            @change="onModalFileChange"
          />
        </div>

        <div class="form-group">
          <label class="form-label">Anzeigename / Beschriftung im Text</label>
          <input
            v-model="modalTitle"
            type="text"
            class="form-control"
            placeholder="z.B. Messprotokoll Werkstück A oder Foto Aufspannung"
          />
        </div>

        <div
          v-if="modalFile && isImageFilename(modalFile.name)"
          class="form-group"
        >
          <label class="form-label">Darstellung im Bericht</label>
          <div class="flex-gap">
            <label class="flex-gap" style="cursor: pointer">
              <input v-model="modalInsertMode" type="radio" value="image" />
              <span>Als eingebettetes Bild anzeigen (`![…]`)</span>
            </label>
            <label class="flex-gap" style="cursor: pointer">
              <input v-model="modalInsertMode" type="radio" value="link" />
              <span>Als Text-Link einfügen (`[…]`)</span>
            </label>
          </div>
        </div>

        <div class="flex-between" style="margin-top: var(--space-4)">
          <button
            type="button"
            class="btn"
            @click="showAttachmentModal = false"
          >
            Abbrechen
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="!modalFile || uploading"
            @click="submitModalUpload"
          >
            {{ uploading ? 'Wird hochgeladen…' : 'Hochladen & im Text einfügen' }}
          </button>
        </div>
      </div>

      <!-- Tab 2: Link existing document -->
      <div v-else>
        <div class="filter-bar" style="margin-bottom: var(--space-3)">
          <input
            v-model="existingSearch"
            type="search"
            class="form-control filter-search"
            placeholder="Dokument oder Bild suchen..."
          />
          <select v-model="existingFilter" class="form-control filter-select">
            <option value="all">Alle Dateien</option>
            <option value="image">Nur Bilder</option>
            <option value="doc">Nur Dokumente</option>
          </select>
        </div>

        <div v-if="loadingExisting" class="text-muted" style="padding: var(--space-4)">
          Dokumente werden geladen…
        </div>
        <div
          v-else-if="filteredExistingDocs.length === 0"
          class="empty-state"
          style="padding: var(--space-5)"
        >
          Keine passenden Dokumente gefunden.
        </div>
        <div v-else class="existing-docs-list">
          <div
            v-for="doc in filteredExistingDocs"
            :key="doc.id"
            class="existing-doc-row"
          >
            <div class="existing-doc-info">
              <div class="flex-gap">
                <strong>{{ doc.name }}</strong>
                <span class="badge badge-neutral">
                  {{ typeLabels[doc.type] || doc.type }}
                </span>
                <span v-if="doc.is_template" class="badge badge-info">Vorlage</span>
              </div>
              <div class="text-muted">
                {{ doc.filename }} · {{ formatDate(doc.updated_date) }}
                <span v-if="doc.owner_name"> · {{ doc.owner_name }}</span>
              </div>
            </div>
            <div class="flex-gap">
              <button
                v-if="isImageFilename(doc.filename)"
                type="button"
                class="btn btn-sm btn-primary"
                @click="insertExistingDocument(doc, 'image')"
              >
                Als Bild einfügen
              </button>
              <button
                type="button"
                class="btn btn-sm"
                :class="{ 'btn-primary': !isImageFilename(doc.filename) }"
                @click="insertExistingDocument(doc, 'link')"
              >
                Als Link einfügen
              </button>
            </div>
          </div>
        </div>
      </div>
    </ModalDialog>
  </div>
</template>

<style scoped>
.markdown-editor {
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.markdown-editor.is-readonly {
  border-color: var(--color-border);
  border-radius: var(--radius-sm);
}

.markdown-editor.is-full-page {
  min-height: 640px;
  box-shadow: var(--shadow-sm);
}

.md-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: 0.55rem var(--space-4);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-muted);
}

.md-toolbar-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.md-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-weight: 600;
}

.md-view-switcher {
  display: inline-flex;
  background: var(--color-surface-subtle);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 2px;
  gap: 2px;
}

.view-mode-btn {
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 600;
  padding: 0.25rem 0.65rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.12s ease;
}

.view-mode-btn:hover {
  color: var(--color-text);
}

.view-mode-btn.active {
  background: var(--color-primary);
  color: #ffffff;
}

.md-upload-alert {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  padding: 0.5rem var(--space-4);
  background: var(--color-danger-bg);
  color: var(--color-danger);
  border-bottom: 1px solid var(--color-danger-border);
  font-size: 0.85rem;
}

.md-workspace {
  display: grid;
  grid-template-columns: 1fr;
  flex: 1;
  min-height: 360px;
}

.markdown-editor.is-full-page .md-workspace {
  min-height: 580px;
}

.md-workspace.mode-split {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

@media (max-width: 1024px) {
  .md-workspace.mode-split {
    grid-template-columns: 1fr;
  }
}

.md-editor-pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.md-workspace.mode-split .md-editor-pane {
  border-right: 1px solid var(--color-border);
}

.md-preview-pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--color-surface);
  max-height: 75vh;
  overflow-y: auto;
}

.md-preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.42rem var(--space-4);
  background: var(--color-surface-muted);
  border-bottom: 1px solid var(--color-border);
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--color-text-muted);
  position: sticky;
  top: 0;
  z-index: 2;
}

.md-editor-loading {
  padding: var(--space-4);
  color: var(--color-text-muted);
}

.md-preview {
  padding: var(--space-5);
  min-height: 120px;
  line-height: 1.65;
}

.md-preview-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 240px;
  text-align: center;
  font-style: italic;
}

.md-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: 0.45rem var(--space-4);
  background: var(--color-surface-muted);
  border-top: 1px solid var(--color-border);
  font-size: 0.78rem;
}

.md-stats {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  color: var(--color-text-muted);
}

.md-hint {
  font-size: 0.76rem;
}

.existing-docs-list {
  max-height: 360px;
  overflow-y: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.existing-doc-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  padding: 0.65rem var(--space-3);
  border-bottom: 1px solid var(--color-border);
}

.existing-doc-row:last-child {
  border-bottom: none;
}

.existing-doc-row:hover {
  background: var(--color-surface-muted);
}

.existing-doc-info {
  min-width: 0;
  flex: 1;
}

.md-preview :deep(h1),
.md-preview :deep(h2),
.md-preview :deep(h3),
.md-preview :deep(h4),
.md-preview :deep(h5),
.md-preview :deep(h6) {
  margin-top: var(--space-4);
  margin-bottom: var(--space-2);
  line-height: 1.3;
}

.md-preview :deep(h1:first-child),
.md-preview :deep(h2:first-child),
.md-preview :deep(h3:first-child) {
  margin-top: 0;
}

.md-preview :deep(p) {
  margin: 0 0 var(--space-3);
}

.md-preview :deep(ul),
.md-preview :deep(ol) {
  margin: 0 0 var(--space-3) var(--space-5);
  padding: 0;
}

.md-preview :deep(li) {
  margin-bottom: 0.25rem;
}

.md-preview :deep(li > p) {
  margin-bottom: var(--space-1);
}

.md-preview :deep(a) {
  color: var(--color-primary);
  text-decoration: underline;
  font-weight: 600;
}

.md-preview :deep(blockquote) {
  margin: 0 0 var(--space-3);
  padding: var(--space-2) var(--space-4);
  border-left: 3px solid var(--color-primary);
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.md-preview :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-border);
  margin: var(--space-4) 0;
}

.md-preview :deep(code) {
  background: var(--color-surface-muted);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  font-family: var(--font-mono);
}

.md-preview :deep(pre) {
  margin: 0 0 var(--space-3);
  padding: var(--space-3);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow-x: auto;
}

.md-preview :deep(pre code) {
  padding: 0;
  background: transparent;
  border-radius: 0;
  font-size: 0.85rem;
}

.md-preview :deep(table) {
  width: 100%;
  margin: 0 0 var(--space-3);
  border-collapse: collapse;
}

.md-preview :deep(th),
.md-preview :deep(td) {
  padding: 0.45rem 0.65rem;
  border: 1px solid var(--color-border);
  text-align: left;
}

.md-preview :deep(th) {
  background: var(--color-surface-muted);
}

.md-preview :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  margin: var(--space-2) 0;
}

.md-preview :deep(.katex) {
  font-size: 1.05em;
}

.md-preview :deep(.katex-display) {
  overflow-x: auto;
  overflow-y: hidden;
  padding: var(--space-2) 0;
}

/* Let the full-page editor fill the available height instead of enforcing
   a fixed minimum that would make the content area scroll. */
@media (min-width: 821px) {
  .markdown-editor.is-full-page {
    flex: 1;
    min-height: 0;
  }

  .markdown-editor.is-full-page .md-workspace {
    min-height: 0;
  }

  .markdown-editor.is-full-page .md-preview-pane {
    max-height: none;
  }
}
</style>

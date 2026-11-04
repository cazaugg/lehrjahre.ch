<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { apiFetch } from '../../api'
import { getDocumentFileUrl, getDocumentKind } from '../../utils/documents'
import MarkdownEditor from './MarkdownEditor.vue'
import DocxPreview from './DocxPreview.vue'
import PdfPreview from './PdfPreview.vue'

const props = defineProps({
  document: { type: Object, required: true }
})

const kind = computed(() => getDocumentKind(props.document))
const fileUrl = computed(() => getDocumentFileUrl(props.document.id))

const content = ref(props.document.content || '')
const loading = ref(false)
const error = ref('')

async function loadContent() {
  if (kind.value !== 'markdown' || content.value) return
  loading.value = true
  error.value = ''
  try {
    const data = await apiFetch(`/api/documents/${props.document.id}`)
    content.value = data?.content || ''
  } catch (e) {
    error.value = e.message || 'Das Dokument konnte nicht geladen werden.'
  } finally {
    loading.value = false
  }
}

onMounted(loadContent)

watch(
  () => [props.document.id, props.document.content],
  () => {
    content.value = props.document.content || ''
    error.value = ''
    loadContent()
  }
)
</script>

<template>
  <div class="document-preview">
    <div v-if="loading" class="card document-preview-status">
      Dokument wird geladen …
    </div>

    <div v-else-if="error" class="alert alert-error">
      {{ error }}
    </div>

    <template v-else>
      <MarkdownEditor
        v-if="kind === 'markdown'"
        :model-value="content"
        :readonly="true"
      />

      <PdfPreview
        v-else-if="kind === 'pdf'"
        :doc-id="document.id"
        :filename="document.filename"
        :updated-date="document.updated_date"
      />

      <DocxPreview
        v-else-if="kind === 'docx'"
        :doc-id="document.id"
        :filename="document.filename"
        :updated-date="document.updated_date"
      />

      <img
        v-else-if="kind === 'image'"
        :src="fileUrl"
        :alt="document.name || 'Dokument'"
        class="document-preview-image"
      />

      <div v-else class="document-preview-unavailable">
        <strong>Keine Vorschau verfügbar.</strong>
        <span>
          Für diesen Dateityp kann keine Vorschau angezeigt werden. Bitte
          verwenden Sie die Download-Schaltfläche.
        </span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.document-preview-status {
  padding: var(--space-4);
}

.document-preview-image {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 0 auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.document-preview-unavailable {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-4);
  color: var(--color-text-muted);
  background: var(--color-surface-muted);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
}
</style>

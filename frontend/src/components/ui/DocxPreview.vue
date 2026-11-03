<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  docId: { type: Number, required: true },
  filename: { type: String, default: '' },
  updatedDate: { type: String, default: '' }
})

const container = ref(null)
const loading = ref(true)
const error = ref('')

const fileUrl = computed(() => `/api/documents/${props.docId}/file`)
const cacheKey = computed(() => `${props.docId}:${props.updatedDate || ''}`)

// Small LRU cache so collapsing and reopening a document does not download it again.
const bufferCache = new Map()
const MAX_CACHED_DOCUMENTS = 3

let controller = null
let runId = 0

function getCachedBuffer(key) {
  const value = bufferCache.get(key)
  if (!value) return null
  bufferCache.delete(key)
  bufferCache.set(key, value)
  return value
}

function cacheBuffer(key, value) {
  bufferCache.set(key, value)
  while (bufferCache.size > MAX_CACHED_DOCUMENTS) {
    bufferCache.delete(bufferCache.keys().next().value)
  }
}

function sanitizePreview() {
  const root = container.value
  if (!root) return

  root
    .querySelectorAll('script, iframe, object, embed')
    .forEach((element) => element.remove())

  root.querySelectorAll('a').forEach((link) => {
    const href = (link.getAttribute('href') || '').trim()
    if (/^javascript:/i.test(href)) {
      link.removeAttribute('href')
      return
    }
    link.setAttribute('target', '_blank')
    link.setAttribute('rel', 'noopener noreferrer')
  })
}

async function loadPreview() {
  const currentRun = ++runId
  controller?.abort()
  controller = new AbortController()

  loading.value = true
  error.value = ''

  try {
    let data = getCachedBuffer(cacheKey.value)
    if (!data) {
      const response = await fetch(fileUrl.value, {
        credentials: 'same-origin',
        signal: controller.signal
      })
      if (!response.ok) {
        throw new Error(`Datei konnte nicht geladen werden (${response.status}).`)
      }
      data = await response.arrayBuffer()
      cacheBuffer(cacheKey.value, data)
    }

    const { renderAsync } = await import('docx-preview')
    if (currentRun !== runId || !container.value) return

    await renderAsync(data, container.value, container.value, {
      className: 'docx',
      inWrapper: true,
      hideWrapperOnPrint: true,
      breakPages: true,
      renderHeaders: true,
      renderFooters: true,
      renderFootnotes: true,
      renderEndnotes: true,
      ignoreLastRenderedPageBreak: false,
      ignoreWidth: false,
      ignoreHeight: false,
      useBase64URL: true
    })

    if (currentRun !== runId) return
    sanitizePreview()
  } catch (e) {
    if (e.name !== 'AbortError' && currentRun === runId) {
      error.value = e.message || 'Die Word-Vorschau konnte nicht erstellt werden.'
    }
  } finally {
    if (currentRun === runId) loading.value = false
  }
}

watch(() => [props.docId, props.updatedDate], loadPreview)
onMounted(loadPreview)
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="docx-preview-block">
    <div v-if="loading" class="card docx-status">
      Word-Dokument wird geladen …
    </div>

    <div v-else-if="error" class="alert alert-error">
      {{ error }}
      <a
        :href="fileUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="btn btn-sm"
        style="margin-left: var(--space-3)"
      >
        Datei öffnen
      </a>
    </div>

    <div
      ref="container"
      v-show="!loading && !error"
      class="docx-preview-container"
    />
  </div>
</template>

<style scoped>
.docx-preview-block {
  margin-top: var(--space-3);
}

.docx-status {
  padding: var(--space-4);
}

.docx-preview-container {
  max-height: 75vh;
  overflow: auto;
  padding: var(--space-4);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.docx-preview-container :deep(.docx-wrapper) {
  background: transparent;
  padding: 0;
}

.docx-preview-container :deep(.docx-wrapper > section.docx) {
  margin-bottom: var(--space-4);
  box-shadow: var(--shadow-md);
}

.docx-preview-container :deep(.docx-wrapper > section.docx:last-child) {
  margin-bottom: 0;
}
</style>

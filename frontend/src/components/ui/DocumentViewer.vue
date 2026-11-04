<script setup>
import { computed, ref, watch } from 'vue'
import { getDocumentDownloadUrl } from '../../utils/documents'
import EditButton from './EditButton.vue'
import DocumentPreview from './DocumentPreview.vue'

const props = defineProps({
  document: { type: Object, required: true },
  alwaysOpen: { type: Boolean, default: false },
  showHeader: { type: Boolean, default: true },
  showDownload: { type: Boolean, default: true }
})

const open = ref(false)

const isOpen = computed(() => props.alwaysOpen || open.value)
const downloadUrl = computed(() => getDocumentDownloadUrl(props.document.id))

watch(
  () => props.document.id,
  () => {
    open.value = false
  }
)

function toggle() {
  if (props.alwaysOpen) return
  open.value = !open.value
}

function formatDate(iso) {
  if (!iso) return '–'
  return new Date(iso).toLocaleDateString('de-CH')
}
</script>

<template>
  <div
    class="document-viewer"
    :class="{
      'is-open': isOpen,
      'is-static': alwaysOpen
    }"
  >
    <div v-if="showHeader" class="document-viewer-header">
      <div class="document-viewer-info">
        <button
          type="button"
          class="document-viewer-name"
          :class="{ 'is-static': alwaysOpen }"
          :aria-expanded="isOpen"
          @click="toggle"
        >
          <svg
            viewBox="0 0 24 24"
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <span class="document-viewer-title">{{ document.name }}</span>
          <span v-if="document.filename" class="document-viewer-filename">
            {{ document.filename }}
          </span>
        </button>

        <div
          v-if="$slots.meta || document.description || document.updated_date"
          class="document-viewer-meta"
        >
          <slot name="meta">
            <span v-if="document.description">{{ document.description }}</span>
            <span v-if="document.updated_date">
              <span v-if="document.description"> · </span>
              Aktualisiert am {{ formatDate(document.updated_date) }}
            </span>
          </slot>
        </div>
      </div>

      <div class="document-viewer-actions">
        <slot name="actions" />
        <EditButton
          v-if="!alwaysOpen"
          :label="isOpen ? 'Vorschau schliessen' : 'Vorschau'"
          icon="eye"
          @click="toggle"
        />
        <EditButton
          v-if="showDownload"
          label="Dokument herunterladen"
          icon="download"
          :href="downloadUrl"
          target="_self"
        />
      </div>
    </div>

    <div v-if="isOpen" class="document-viewer-preview">
      <DocumentPreview :document="document" />
    </div>
  </div>
</template>

<style scoped>
.document-viewer {
  min-width: 0;
  width: 100%;
}

.document-viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.document-viewer-info {
  min-width: 0;
  flex: 1;
}

.document-viewer-name {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.4rem;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--color-primary);
  font: inherit;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.document-viewer-name.is-static {
  color: var(--color-text);
  cursor: default;
}

.document-viewer-name:not(.is-static):hover .document-viewer-title {
  text-decoration: underline;
}

.document-viewer-title {
  overflow-wrap: anywhere;
}

.document-viewer-filename {
  color: var(--color-text-muted);
  font-size: 0.82rem;
  font-weight: 400;
  overflow-wrap: anywhere;
}

.document-viewer-meta {
  margin-top: 2px;
  color: var(--color-text-muted);
  font-size: 0.85rem;
}

.document-viewer-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.document-viewer-preview {
  margin-top: var(--space-3);
  min-width: 0;
}
</style>

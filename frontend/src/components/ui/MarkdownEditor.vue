<script setup>
import { ref, computed, defineAsyncComponent, h } from 'vue'
import 'katex/dist/katex.min.css'
import { renderMarkdown } from '../../utils/markdown'

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
  rows: { type: Number, default: 10 }
})

const emit = defineEmits(['update:modelValue'])
const previewMode = ref(false)

const renderedHtml = computed(() => renderMarkdown(props.modelValue))
</script>

<template>
  <div class="markdown-editor">
    <div v-if="!readonly" class="md-toolbar">
      <span class="text-muted">
        Markdown unterstützt (`# Titel`, `**Fett**`, `- Liste`, `$…$` Formeln)
      </span>
      <button type="button" class="btn btn-sm" @click="previewMode = !previewMode">
        {{ previewMode ? 'Bearbeiten' : 'Vorschau' }}
      </button>
    </div>

    <div v-if="readonly || previewMode" class="md-preview" v-html="renderedHtml" />
    <MarkdownSourceEditor
      v-else
      :model-value="modelValue"
      :placeholder="placeholder"
      :rows="rows"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>

<style scoped>
.markdown-editor {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  overflow: hidden;
}

.md-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-muted);
}

.md-editor-loading {
  padding: var(--space-4);
  color: var(--color-text-muted);
}

.md-preview {
  padding: var(--space-4);
  min-height: 120px;
}

.md-preview :deep(h1),
.md-preview :deep(h2),
.md-preview :deep(h3),
.md-preview :deep(h4),
.md-preview :deep(h5),
.md-preview :deep(h6) {
  margin-top: var(--space-3);
  margin-bottom: var(--space-2);
  line-height: 1.3;
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
}

.md-preview :deep(blockquote) {
  margin: 0 0 var(--space-3);
  padding: var(--space-2) var(--space-4);
  border-left: 3px solid var(--color-border-strong);
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
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
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--color-border);
  text-align: left;
}

.md-preview :deep(th) {
  background: var(--color-surface-muted);
}

.md-preview :deep(img) {
  max-width: 100%;
}

.md-preview :deep(.katex) {
  font-size: 1.05em;
}

.md-preview :deep(.katex-display) {
  overflow-x: auto;
  overflow-y: hidden;
  padding: var(--space-2) 0;
}
</style>

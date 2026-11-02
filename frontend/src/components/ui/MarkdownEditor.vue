<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  readonly: { type: Boolean, default: false },
  placeholder: { type: String, default: 'Inhalt im Markdown-Format eingeben...' },
  rows: { type: Number, default: 10 }
})

const emit = defineEmits(['update:modelValue'])
const previewMode = ref(false)

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

const renderedHtml = computed(() => {
  const lines = escapeHtml(props.modelValue).split('\n')
  const html = []
  let inList = false

  for (const rawLine of lines) {
    const line = rawLine.trimEnd()
    if (line.startsWith('### ')) {
      if (inList) { html.push('</ul>'); inList = false }
      html.push(`<h4>${line.slice(4)}</h4>`)
    } else if (line.startsWith('## ')) {
      if (inList) { html.push('</ul>'); inList = false }
      html.push(`<h3>${line.slice(3)}</h3>`)
    } else if (line.startsWith('# ')) {
      if (inList) { html.push('</ul>'); inList = false }
      html.push(`<h2>${line.slice(2)}</h2>`)
    } else if (line.startsWith('- ') || line.startsWith('* ')) {
      if (!inList) { html.push('<ul>'); inList = true }
      html.push(`<li>${line.slice(2)}</li>`)
    } else if (line.trim() === '') {
      if (inList) { html.push('</ul>'); inList = false }
      html.push('<br/>')
    } else {
      if (inList) { html.push('</ul>'); inList = false }
      const formatted = line
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/`(.+?)`/g, '<code>$1</code>')
      html.push(`<p>${formatted}</p>`)
    }
  }
  if (inList) html.push('</ul>')
  return html.join('\n')
})
</script>

<template>
  <div class="md-editor">
    <div v-if="!readonly" class="md-toolbar">
      <span class="text-muted">Markdown unterstützt (`# Titel`, `**Fett**`, `- Liste`)</span>
      <button type="button" class="btn btn-sm" @click="previewMode = !previewMode">
        {{ previewMode ? 'Bearbeiten' : 'Vorschau' }}
      </button>
    </div>

    <div v-if="readonly || previewMode" class="md-preview" v-html="renderedHtml" />
    <textarea
      v-else
      class="form-control md-textarea"
      :rows="rows"
      :placeholder="placeholder"
      :value="modelValue"
      @input="emit('update:modelValue', $event.target.value)"
    />
  </div>
</template>

<style scoped>
.md-editor {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.md-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-muted);
}

.md-textarea {
  border: none;
  border-radius: 0;
  font-family: var(--font-mono);
  font-size: 0.875rem;
}

.md-textarea:focus {
  box-shadow: none;
}

.md-preview {
  padding: var(--space-4);
  min-height: 120px;
}

.md-preview :deep(h2),
.md-preview :deep(h3),
.md-preview :deep(h4) {
  margin-top: var(--space-3);
  margin-bottom: var(--space-2);
}

.md-preview :deep(ul) {
  margin: 0 0 var(--space-3) var(--space-5);
  padding: 0;
}

.md-preview :deep(code) {
  background: var(--color-surface-muted);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  font-family: var(--font-mono);
}
</style>

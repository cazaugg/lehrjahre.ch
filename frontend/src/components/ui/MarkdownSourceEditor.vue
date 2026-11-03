<script setup>
import { ref, computed } from 'vue'
import { MdEditor } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import './mdEditorConfig'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  rows: { type: Number, default: 10 },
  fullPage: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'files-dropped'])

const editorRef = ref(null)

const toolbars = [
  'bold',
  'italic',
  'strikeThrough',
  '-',
  'title',
  'quote',
  'unorderedList',
  'orderedList',
  'task',
  '-',
  'codeRow',
  'code',
  'table',
  'link',
  'katex',
  '=',
  'revoke',
  'next'
]

const editorStyle = computed(() => {
  if (props.fullPage) {
    return { height: '100%' }
  }
  const rows = Math.max(10, props.rows)
  return { height: `${Math.round(rows * 1.9 + 2)}rem` }
})

function insertText(snippet) {
  if (!snippet) return
  if (editorRef.value && typeof editorRef.value.insert === 'function') {
    editorRef.value.insert(() => ({
      targetValue: snippet,
      select: false,
      deviationStart: 0,
      deviationEnd: 0
    }))
    editorRef.value.focus?.()
  } else {
    const base = props.modelValue || ''
    const sep = base && !base.endsWith('\n') ? '\n\n' : ''
    emit('update:modelValue', `${base}${sep}${snippet}`)
  }
}

function handlePaste(event) {
  const files = event.clipboardData?.files
  if (files && files.length > 0) {
    event.preventDefault()
    event.stopPropagation()
    emit('files-dropped', Array.from(files))
  }
}

function handleDrop(event) {
  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    event.preventDefault()
    event.stopPropagation()
    emit('files-dropped', Array.from(files))
  }
}

defineExpose({
  insertText
})
</script>

<template>
  <div
    class="markdown-source-wrap"
    :class="{ 'is-full-page': fullPage }"
    @paste.capture="handlePaste"
    @drop.capture="handleDrop"
  >
    <MdEditor
      ref="editorRef"
      class="markdown-source-editor"
      :model-value="modelValue"
      :placeholder="placeholder"
      :preview="false"
      :no-upload-img="true"
      :no-mermaid="true"
      :no-echarts="true"
      :no-highlight="true"
      :no-katex="true"
      :no-prettier="true"
      :footers="[]"
      :toolbars="toolbars"
      language="de-DE"
      :style="editorStyle"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>

<style scoped>
.markdown-source-wrap {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.markdown-source-wrap.is-full-page {
  height: 100%;
  min-height: 580px;
}

.markdown-source-editor {
  border: none !important;
  border-radius: 0;
  flex: 1;
  min-height: 0;
}

@media (min-width: 821px) {
  .markdown-source-wrap.is-full-page {
    min-height: 0;
  }
}
</style>

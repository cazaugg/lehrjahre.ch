<script setup>
import { computed } from 'vue'
import { MdEditor } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import './mdEditorConfig'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  rows: { type: Number, default: 10 }
})

const emit = defineEmits(['update:modelValue'])

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
  'link',
  'table',
  '=',
  'revoke',
  'next'
]

const editorHeight = computed(() => {
  const rows = Math.max(8, props.rows)
  return `${Math.round(rows * 1.9 + 2)}rem`
})
</script>

<template>
  <MdEditor
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
    :style="{ height: editorHeight }"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>

<style scoped>
.markdown-source-editor {
  border: none !important;
  border-radius: 0;
}
</style>

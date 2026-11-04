<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  docId: { type: Number, required: true },
  filename: { type: String, default: '' },
  updatedDate: { type: String, default: '' }
})

const loaded = ref(false)
const fileUrl = computed(() => `/api/documents/${props.docId}/file`)

let fallbackTimer = null

function startFallbackTimer() {
  clearTimeout(fallbackTimer)
  fallbackTimer = setTimeout(() => {
    loaded.value = true
  }, 2500)
}

onMounted(startFallbackTimer)
onBeforeUnmount(() => clearTimeout(fallbackTimer))

watch(
  () => [props.docId, props.updatedDate],
  () => {
    loaded.value = false
    startFallbackTimer()
  }
)
</script>

<template>
  <div class="pdf-preview-block">
    <div v-if="!loaded" class="card pdf-status">
      PDF wird geladen …
    </div>

    <iframe
      :src="fileUrl"
      class="pdf-frame"
      title="PDF-Vorschau"
      loading="lazy"
      @load="loaded = true"
    />
  </div>
</template>

<style scoped>
.pdf-preview-block {
  margin-top: var(--space-3);
}

.pdf-status {
  padding: var(--space-4);
}

.pdf-frame {
  width: 100%;
  height: 75vh;
  min-height: 460px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}
</style>

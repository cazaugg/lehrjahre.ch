<script setup>
import { computed, ref, watch } from 'vue'
import { apiFetch } from '../../api'

/**
 * Rendert ein Projekt-Ziel: Freitext bleibt plain; String in der Form
 * «LZ_6957» (aus dem Lernziel-Picker) wird via /api/lehrplan/lz/<id> aufgelöst
 * und als Deep-Link zur Lehrplan-Seite dargestellt.
 */
const props = defineProps({
  goal: { type: String, default: '' }
})

const LZ_RE = /^\s*(LZ_\d+)\s*$/

const isLernzielId = computed(() => LZ_RE.test(props.goal))
const lzId = computed(() => (isLernzielId.value ? props.goal.trim().match(LZ_RE)[1] : null))

const info = ref(null)
const failed = ref(false)

let cache
try {
  // Modulweiter Cache über alle Instanzen (Detail, Auswertung, Review …).
  cache = globalThis.__lernzielInfoCache || (globalThis.__lernzielInfoCache = new Map())
} catch {
  cache = new Map()
}

watch(
  lzId,
  async (id) => {
    if (!id) {
      info.value = null
      return
    }
    if (cache.has(id)) {
      info.value = cache.get(id)
      failed.value = !info.value
      return
    }
    try {
      const data = await apiFetch(`/api/lehrplan/lz/${encodeURIComponent(id)}`)
      info.value = data
      cache.set(id, data)
      failed.value = false
    } catch {
      cache.set(id, null)
      info.value = null
      failed.value = true
    }
  },
  { immediate: true }
)
</script>

<template>
  <router-link
    v-if="info"
    :to="`/lehrplan/${info.code}?highlight=lz-${info.lz_id}`"
    class="lernziel-label"
    title="Im Lehrplan anzeigen"
  >
    <span class="lz-code">{{ info.lz_id }}</span>
    <span class="lz-desc">{{ info.description }}</span>
    <span class="lz-ctx">{{ info.lk_id }} · {{ info.lernort }}</span>
  </router-link>
  <template v-else>{{ goal }}</template>
</template>

<style scoped>
.lernziel-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: inherit;
  text-decoration: none;
}

.lernziel-label:hover {
  text-decoration: none;
}

.lz-code {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--color-primary);
}

.lernziel-label:hover .lz-code {
  text-decoration: underline;
}

.lz-desc {
  font-size: 0.87rem;
  color: var(--color-text);
  font-weight: 400;
}

.lz-ctx {
  font-size: 0.72rem;
  color: var(--color-text-light);
  font-family: var(--font-mono);
}
</style>

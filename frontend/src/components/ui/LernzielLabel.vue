<script setup>
import { computed, ref, watch } from 'vue'
import { apiFetch } from '../../api'

/**
 * Rendert ein Projekt-Ziel: Freitext bleibt plain; String in der Form
 * «LZ_6957» bzw. «LK:MEM 06 01 (BE)» (aus dem Lernziel-Picker) wird via
 * /api/lehrplan/lz/<id> aufgelöst und als Deep-Link zur Lehrplan-Seite
 * dargestellt. Ohne «LK:»-Präfix gilt die Kompaktform der LK-IDs
 * (z.B. «KR b2 01») als Lernkriterium ID (Altbestand des Pickers).
 */
const props = defineProps({
  goal: { type: String, default: '' },
  /** 🎯-Symbol vor dem Ziel (fliesst mit, statt als separates Inline-Element). */
  icon: { type: Boolean, default: false }
})

const LZ_RE = /^\s*(LZ_\d+(?:_\d+)*)\s*$/
const LK_PREFIX_RE = /^\s*LK:(.+?)\s*$/
// Altformat: nackte LK-ID (Kompaktform «XX y9 …»).
const LK_SHAPE_RE = /^\s*([A-Za-z]{2,3} [a-z]?[0-9].*)\s*$/

const isLernzielId = computed(() => LZ_RE.test(props.goal))
const lzId = computed(() => (isLernzielId.value ? props.goal.trim().match(LZ_RE)[1] : null))

const lkId = computed(() => {
  const g = props.goal
  const prefixed = g.match(LK_PREFIX_RE)
  if (prefixed) return prefixed[1]
  const bare = g.match(LK_SHAPE_RE)
  return bare ? bare[1].trim() : null
})

const viewId = computed(() => {
  if (lzId.value) return lzId.value
  return lkId.value ? 'str:' + lkId.value : null
})

const info = ref(null)
const failed = ref(false)

let cache
try {
  // Modulweiter Cache über alle Instanzen (Detail, Auswertung, Review …).
  cache = globalThis.__lernzielInfoCache || (globalThis.__lernzielInfoCache = new Map())
} catch {
  cache = new Map()
}

async function load(id) {
  if (cache.has(id)) {
    info.value = cache.get(id)
    failed.value = !info.value
    return
  }
  const lookupId = id.startsWith('str:') ? id.slice(4) : id
  try {
    const data = await apiFetch(`/api/lehrplan/lz/${encodeURIComponent(lookupId)}`)
    info.value = data
    cache.set(id, data)
    failed.value = false
  } catch {
    cache.set(id, null)
    info.value = null
    failed.value = true
  }
}

watch(
  viewId,
  async (id) => {
    if (!id) {
      info.value = null
      return
    }
    await load(id)
  },
  { immediate: true }
)

/** Anzeige-Code (LZ- oder LK-ID) und Kontextzeile je nach Zielart. */
const code = computed(() =>
  info.value?.kind === 'lk' ? info.value.lk_id : info.value?.lz_id
)

const ctxLine = computed(() =>
  info.value?.kind === 'lk' ? info.value.lernort : `${info.value?.lk_id} · ${info.value?.lernort}`
)

/** Vollständiger Zieltext für den Tooltip (Zeilenumbruch klemmt auf 2 Zeilen). */
const fullText = computed(() => `${code.value} · ${info.value?.description ?? ''}`)

const hlTarget = computed(() => {
  const d = info.value
  if (d?.kind === 'lk') {
    // sectionId() im Lehrplan ersetzt Punkte/Leerzeichen durch Unterstriche.
    const norm = String(d.lk_id).replace(/[.\s]+/g, '_')
    return { path: `/lehrplan/${d.code}`, query: { highlight: 'lk-' + norm } }
  }
  return { path: `/lehrplan/${d?.code}`, query: { highlight: 'lz-' + d?.lz_id }
  }
})
</script>

<template>
  <router-link
    v-if="info"
    :to="hlTarget"
    class="lernziel-label"
    :title="fullText + ' – im Lehrplan anzeigen'"
  >
    <span v-if="icon" class="goal-icon goal-icon-inner">🎯</span>
    <span class="lz-code"><span class="lz-code-text">{{ code }}</span></span>
    <span class="lz-desc">{{ info.description }}</span>
    <span class="lz-ctx">{{ ctxLine }}</span>
  </router-link>
  <template v-else>
    <span v-if="icon" class="goal-icon goal-icon-inner">🎯</span>{{ goal }}
  </template>
</template>

<style scoped>
/* Code, Text und Kontext fliessen inline und brechen auf max. 2 Zeilen um. */
.lernziel-label {
  display: -webkit-inline-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  color: inherit;
  text-decoration: none;
  line-height: 1.35;
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

.lz-code::after {
  content: ' · ';
  font-weight: 400;
  color: var(--color-text-light);
}

.lernziel-label:hover .lz-code-text {
  text-decoration: underline;
}

.lz-desc {
  font-size: 0.87rem;
  color: var(--color-text);
  font-weight: 400;
}

.lz-desc::after {
  content: ' · ';
  color: var(--color-text-light);
}

.lz-ctx {
  font-size: 0.72rem;
  color: var(--color-text-light);
  font-family: var(--font-mono);
}

/* Das Symbol sitzt innerhalb des Labels: etwas luftiger als der Text. */
.goal-icon-inner {
  font-size: 0.88rem;
  margin-right: 0.3em;
}
</style>

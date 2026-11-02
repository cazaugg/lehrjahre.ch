<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { apiFetch } from '../../api'
import { useAuthStore } from '../../stores/auth'

const props = defineProps({
  personId: { type: Number, required: true },
  role: { type: String, required: true }
})

const auth = useAuthStore()
const vertragDocs = ref([])
const bewerbungDocs = ref([])

const canView = computed(
  () =>
    props.role === 'lernender' &&
    (auth.isTrainer || auth.user?.id === props.personId)
)

const groups = computed(() =>
  [
    { label: 'Lehrvertrag', docs: vertragDocs.value },
    { label: 'Bewerbung', docs: bewerbungDocs.value }
  ].filter((group) => group.docs.length > 0)
)

async function loadDocuments() {
  if (!canView.value) return
  try {
    const [vertrag, bewerbung] = await Promise.all([
      apiFetch(`/api/documents?type=vertrag&owner=${props.personId}`),
      apiFetch(`/api/documents?type=bewerbung&owner=${props.personId}`)
    ])
    vertragDocs.value = vertrag.filter((doc) => !doc.is_template)
    bewerbungDocs.value = bewerbung.filter((doc) => !doc.is_template)
  } catch {
    vertragDocs.value = []
    bewerbungDocs.value = []
  }
}

function formatDate(iso) {
  if (!iso) return '–'
  return new Date(iso).toLocaleDateString('de-CH')
}

watch(() => props.personId, loadDocuments)
onMounted(loadDocuments)
</script>

<template>
  <div v-if="groups.length" class="person-documents">
    <h4>Dokumente</h4>
    <div v-for="group in groups" :key="group.label" class="document-group">
      <div class="document-group-title">{{ group.label }}</div>
      <div v-for="doc in group.docs" :key="doc.id" class="document-row">
        <a :href="`/api/documents/${doc.id}/file`" target="_blank" rel="noopener">
          {{ doc.name }}
        </a>
        <span class="text-muted">{{ formatDate(doc.updated_date) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.person-documents {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.document-group {
  margin-bottom: var(--space-3);
}

.document-group-title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--color-text-muted);
  margin-bottom: var(--space-1);
}

.document-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  padding: 0.35rem 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 0.9rem;
}

.document-row:last-child {
  border-bottom: none;
}
</style>

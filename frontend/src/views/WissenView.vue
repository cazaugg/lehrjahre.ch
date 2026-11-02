<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiFetch } from '../api'
import ModalDialog from '../components/ui/ModalDialog.vue'
import MarkdownEditor from '../components/ui/MarkdownEditor.vue'

const nodes = ref([])
const error = ref('')

// Search & Filter
const searchQuery = ref('')
const filterTopic = ref('')
const expandedIds = ref({})
const editingNodeId = ref(null)

// Edit form state
const editTitle = ref('')
const editDescription = ref('')
const editContent = ref('')

// Create Modal
const showCreateModal = ref(false)
const createParentId = ref('')
const createTitle = ref('')
const createDescription = ref('')
const createContent = ref('')

const topics = computed(() => nodes.value.filter((n) => !n.parent_id))

const topicMap = computed(() => {
  const m = {}
  for (const t of topics.value) {
    m[t.id] = t.title
  }
  return m
})

const filteredNodes = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return nodes.value.filter((n) => {
    if (filterTopic.value) {
      const tid = Number(filterTopic.value)
      if (n.id !== tid && n.parent_id !== tid) return false
    }
    if (q) {
      const hay = `${n.title} ${n.description || ''} ${n.content || ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

async function loadKnowledge() {
  error.value = ''
  try {
    nodes.value = await apiFetch('/api/knowledge')
  } catch (e) {
    error.value = e.message
  }
}

onMounted(loadKnowledge)

function toggleExpand(node) {
  expandedIds.value[node.id] = !expandedIds.value[node.id]
}

function startEdit(node) {
  editingNodeId.value = node.id
  editTitle.value = node.title
  editDescription.value = node.description || ''
  editContent.value = node.content || ''
  expandedIds.value[node.id] = true
}

function openCreate(parentId = '') {
  createParentId.value = parentId || ''
  createTitle.value = ''
  createDescription.value = ''
  createContent.value = ''
  showCreateModal.value = true
}

async function createNode() {
  error.value = ''
  try {
    const created = await apiFetch('/api/knowledge', {
      method: 'POST',
      body: {
        parent_id: createParentId.value || null,
        title: createTitle.value,
        description: createDescription.value,
        content:
          createContent.value ||
          `# ${createTitle.value}\n\n${createDescription.value}`
      }
    })
    showCreateModal.value = false
    expandedIds.value[created.id] = true
    await loadKnowledge()
  } catch (e) {
    error.value = e.message
  }
}

async function saveEdit(node) {
  error.value = ''
  try {
    await apiFetch(`/api/knowledge/${node.id}`, {
      method: 'PUT',
      body: {
        title: editTitle.value,
        description: editDescription.value,
        content: editContent.value
      }
    })
    editingNodeId.value = null
    await loadKnowledge()
  } catch (e) {
    error.value = e.message
  }
}

async function deleteNode(node) {
  if (
    !confirm(
      `Eintrag "${node.title}" inklusive zugehöriger Datei wirklich löschen?`
    )
  )
    return
  try {
    await apiFetch(`/api/knowledge/${node.id}`, {
      method: 'DELETE'
    })
    await loadKnowledge()
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">Wissen & Notizen</h1>
        <p class="page-subtitle">
          Nachschlagewerk, Fachnotizen und Formelsammlung (Neueste zuerst)
        </p>
      </div>
      <div class="flex-gap">
        <button type="button" class="btn" @click="openCreate('')">
          + Neues Thema
        </button>
        <button
          type="button"
          class="btn btn-primary"
          @click="openCreate(topics[0]?.id || '')"
        >
          + Neue Seite
        </button>
      </div>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>

    <!-- Filter & Search Bar -->
    <div class="filter-bar">
      <input
        v-model="searchQuery"
        type="search"
        class="form-control filter-search"
        placeholder="Themen, Seiten oder Fachbegriffe durchsuchen..."
      />

      <select v-model="filterTopic" class="form-control filter-select">
        <option value="">Alle Themenbereiche</option>
        <option v-for="t in topics" :key="t.id" :value="t.id">
          Thema: {{ t.title }}
        </option>
      </select>

      <span class="text-muted">{{ filteredNodes.length }} Einträge</span>
    </div>

    <!-- Collapsible List of Knowledge Entries -->
    <div v-if="filteredNodes.length === 0" class="card empty-state">
      Keine passenden Wissenseinträge gefunden.
    </div>

    <div v-else>
      <div
        v-for="node in filteredNodes"
        :key="node.id"
        class="collapsible-card"
      >
        <div class="collapsible-header" @click="toggleExpand(node)">
          <div class="flex-gap">
            <span class="expand-indicator">
              {{ expandedIds[node.id] ? '▾' : '▸' }}
            </span>
            <div>
              <div class="flex-gap">
                <strong>{{ node.title }}</strong>
                <span
                  class="badge"
                  :class="node.parent_id ? 'badge-info' : 'badge-success'"
                >
                  {{
                    node.parent_id
                      ? `Seite in: ${topicMap[node.parent_id] || 'Thema'}`
                      : 'Hauptthema'
                  }}
                </span>
              </div>
              <div v-if="node.description" class="text-muted" style="margin-top: 2px">
                {{ node.description }}
              </div>
            </div>
          </div>

          <div class="flex-gap" @click.stop>
            <button
              v-if="!node.parent_id"
              type="button"
              class="btn btn-sm"
              @click="openCreate(node.id)"
            >
              + Unterseite
            </button>
          </div>
        </div>

        <div v-if="expandedIds[node.id]" class="collapsible-body">
          <div v-if="editingNodeId === node.id">
            <div class="form-group">
              <label class="form-label">Titel *</label>
              <input v-model="editTitle" type="text" class="form-control" required />
            </div>
            <div class="form-group">
              <label class="form-label">Kurzbeschreibung</label>
              <input v-model="editDescription" type="text" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Seiteninhalt (Markdown)</label>
              <MarkdownEditor v-model="editContent" :rows="12" />
            </div>
            <div class="flex-between">
              <button type="button" class="btn" @click="editingNodeId = null">
                Abbrechen
              </button>
              <button
                type="button"
                class="btn btn-primary"
                @click="saveEdit(node)"
              >
                Änderungen speichern
              </button>
            </div>
          </div>

          <div v-else>
            <div class="flex-between" style="margin-bottom: var(--space-3)">
              <div v-if="node.document" class="text-muted">
                Gespeichert unter: <code>/data/documents/{{ node.document.path }}</code>
              </div>
              <div class="flex-gap">
                <button
                  type="button"
                  class="btn btn-sm"
                  @click="startEdit(node)"
                >
                  Bearbeiten
                </button>
                <button
                  type="button"
                  class="btn btn-sm btn-danger"
                  @click="deleteNode(node)"
                >
                  Löschen
                </button>
              </div>
            </div>

            <MarkdownEditor :model-value="node.content" :readonly="true" />
          </div>
        </div>
      </div>
    </div>

    <!-- Modal: Create Topic or Page -->
    <ModalDialog
      :show="showCreateModal"
      :title="createParentId ? 'Neue Wissensseite erstellen' : 'Neues Wissensthema erstellen'"
      width="680px"
      @close="showCreateModal = false"
    >
      <form @submit.prevent="createNode">
        <div class="form-group">
          <label class="form-label">Übergeordnetes Thema (optional)</label>
          <select v-model="createParentId" class="form-control">
            <option value="">Kein übergeordnetes Thema (Neues Hauptthema)</option>
            <option v-for="t in topics" :key="t.id" :value="t.id">
              {{ t.title }}
            </option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Titel *</label>
          <input v-model="createTitle" type="text" class="form-control" required />
        </div>

        <div class="form-group">
          <label class="form-label">Kurzbeschreibung</label>
          <input v-model="createDescription" type="text" class="form-control" />
        </div>

        <div class="form-group">
          <label class="form-label">Inhalt (Markdown)</label>
          <MarkdownEditor v-model="createContent" :rows="10" />
        </div>

        <div class="flex-between">
          <button type="button" class="btn" @click="showCreateModal = false">
            Abbrechen
          </button>
          <button type="submit" class="btn btn-primary">Erstellen</button>
        </div>
      </form>
    </ModalDialog>
  </div>
</template>

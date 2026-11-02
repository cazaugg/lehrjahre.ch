<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'
import ModalDialog from '../components/ui/ModalDialog.vue'
import MarkdownEditor from '../components/ui/MarkdownEditor.vue'

const auth = useAuthStore()
const nodes = ref([])
const error = ref('')

// Search & Filter
const searchQuery = ref('')
const filterTopic = ref('')
const filterAuthor = ref('')
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

function canManage(node) {
  return Boolean(node) && node.owner === auth.user?.id
}

const topics = computed(() =>
  nodes.value
    .filter((n) => !n.parent_id)
    .sort((a, b) => a.id - b.id)
)

const ownTopics = computed(() => topics.value.filter((topic) => canManage(topic)))

const availableAuthors = computed(() => {
  const authors = new Map()
  for (const node of nodes.value) {
    if (node.author) {
      authors.set(node.author, node.author_name || 'Unbekannt')
    }
  }
  return [...authors.entries()].sort((a, b) =>
    a[1].localeCompare(b[1], 'de-CH')
  )
})

const groupedTopics = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const selected = filterTopic.value ? Number(filterTopic.value) : null
  const selectedAuthor = filterAuthor.value ? Number(filterAuthor.value) : null
  const matches = (node) =>
    !q ||
    `${node.title} ${node.description || ''} ${node.content || ''}`
      .toLowerCase()
      .includes(q)
  const authorMatches = (node) =>
    !selectedAuthor || node.author === selectedAuthor

  return topics.value
    .filter((topic) => !selected || topic.id === selected)
    .map((topic) => {
      const topicAuthorMatches = authorMatches(topic)
      const topicMatches = matches(topic)
      const pages = nodes.value
        .filter((node) => node.parent_id === topic.id && authorMatches(node))
        .filter((node) => topicAuthorMatches || matches(node))
        .sort((a, b) => a.id - b.id)
      const visible = topicAuthorMatches
        ? topicMatches || pages.length > 0
        : pages.length > 0
      return { ...topic, pages, visible }
    })
    .filter((topic) => topic.visible)
})

const entryCount = computed(() =>
  groupedTopics.value.reduce((sum, topic) => sum + 1 + topic.pages.length, 0)
)

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
          Nachschlagewerk, Fachnotizen und Formelsammlung – nach Themen gruppiert
        </p>
      </div>
      <div class="flex-gap">
        <button type="button" class="btn" @click="openCreate('')">
          + Neues Thema
        </button>
        <button
          type="button"
          class="btn btn-primary"
          @click="openCreate(ownTopics[0]?.id || '')"
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

      <select
        v-if="auth.isTrainer"
        v-model="filterAuthor"
        class="form-control filter-select"
      >
        <option value="">Alle Autoren</option>
        <option v-for="[id, name] in availableAuthors" :key="id" :value="id">
          {{ name }}
        </option>
      </select>

      <span class="text-muted">{{ entryCount }} Einträge</span>
    </div>

    <!-- Subjects with their pages -->
    <div v-if="groupedTopics.length === 0" class="card empty-state">
      Keine passenden Wissenseinträge gefunden.
    </div>

    <div v-else>
      <div
        v-for="topic in groupedTopics"
        :key="topic.id"
        class="collapsible-card"
      >
        <div class="collapsible-header" @click="toggleExpand(topic)">
          <div class="flex-gap">
            <span class="expand-indicator">
              {{ expandedIds[topic.id] ? '▾' : '▸' }}
            </span>
            <div>
              <div class="flex-gap">
                <strong>{{ topic.title }}</strong>
                <span class="badge badge-success">Hauptthema</span>
                <span
                  v-if="auth.isTrainer && topic.author_name"
                  class="badge badge-neutral"
                >
                  {{ topic.author_name }}
                </span>
                <span class="text-muted">{{ topic.pages.length }} Seiten</span>
              </div>
              <div v-if="topic.description" class="text-muted" style="margin-top: 2px">
                {{ topic.description }}
              </div>
            </div>
          </div>

          <div class="flex-gap" @click.stop>
            <button
              type="button"
              class="btn btn-sm"
              @click="openCreate(topic.id)"
            >
              + Unterseite
            </button>
          </div>
        </div>

        <div v-if="expandedIds[topic.id]" class="collapsible-body">
          <div v-if="editingNodeId === topic.id">
            <div class="form-group">
              <label class="form-label">Titel *</label>
              <input v-model="editTitle" type="text" class="form-control" required />
            </div>
            <div class="form-group">
              <label class="form-label">Kurzbeschreibung</label>
              <input v-model="editDescription" type="text" class="form-control" />
            </div>
            <div class="flex-between">
              <button type="button" class="btn" @click="editingNodeId = null">
                Abbrechen
              </button>
              <button
                type="button"
                class="btn btn-primary"
                @click="saveEdit(topic)"
              >
                Änderungen speichern
              </button>
            </div>
          </div>

          <div v-else>
            <div
              v-if="canManage(topic)"
              class="flex-between"
              style="justify-content: flex-end"
            >
              <div class="flex-gap">
                <button
                  type="button"
                  class="btn btn-sm"
                  @click="startEdit(topic)"
                >
                  Bearbeiten
                </button>
                <button
                  type="button"
                  class="btn btn-sm btn-danger"
                  @click="deleteNode(topic)"
                >
                  Löschen
                </button>
              </div>
            </div>
          </div>

          <div class="subject-pages">
            <div v-if="topic.pages.length === 0" class="text-muted">
              Noch keine Seiten in diesem Thema.
            </div>

            <div
              v-for="page in topic.pages"
              :key="page.id"
              class="collapsible-card page-card"
            >
              <div class="collapsible-header" @click="toggleExpand(page)">
                <div class="flex-gap">
                  <span class="expand-indicator">
                    {{ expandedIds[page.id] ? '▾' : '▸' }}
                  </span>
                  <div>
                    <div class="flex-gap">
                      <strong>{{ page.title }}</strong>
                      <span
                        v-if="auth.isTrainer && page.author_name"
                        class="badge badge-neutral"
                      >
                        {{ page.author_name }}
                      </span>
                    </div>
                    <div
                      v-if="page.description"
                      class="text-muted"
                      style="margin-top: 2px"
                    >
                      {{ page.description }}
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="expandedIds[page.id]" class="collapsible-body">
                <div v-if="editingNodeId === page.id">
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
                      @click="saveEdit(page)"
                    >
                      Änderungen speichern
                    </button>
                  </div>
                </div>

                <div v-else>
                  <div
                    v-if="canManage(page)"
                    class="flex-between"
                    style="margin-bottom: var(--space-3); justify-content: flex-end"
                  >
                    <div class="flex-gap">
                      <button
                        type="button"
                        class="btn btn-sm"
                        @click="startEdit(page)"
                      >
                        Bearbeiten
                      </button>
                      <button
                        type="button"
                        class="btn btn-sm btn-danger"
                        @click="deleteNode(page)"
                      >
                        Löschen
                      </button>
                    </div>
                  </div>

                  <MarkdownEditor :model-value="page.content" :readonly="true" />
                </div>
              </div>
            </div>
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
            <option v-for="t in ownTopics" :key="t.id" :value="t.id">
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

<style scoped>
.subject-pages {
  margin-top: var(--space-5);
  padding-left: var(--space-4);
  display: flex;
  flex-direction: column;
}

.page-card {
  box-shadow: none;
}

.page-card:last-child {
  margin-bottom: 0;
}
</style>

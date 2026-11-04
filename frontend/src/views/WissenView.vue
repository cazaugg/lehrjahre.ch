<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'
import MarkdownEditor from '../components/ui/MarkdownEditor.vue'
import DocumentViewer from '../components/ui/DocumentViewer.vue'
import EditButton from '../components/ui/EditButton.vue'
import { getDocumentDownloadUrl } from '../utils/documents'

const auth = useAuthStore()
const nodes = ref([])
const error = ref('')

// Search & Filter
const searchQuery = ref('')
const filterTopic = ref('')
const filterAuthor = ref('')
const expandedIds = ref({})

// Full-Page Editor state
const showEditor = ref(false)
const editingNode = ref(null)
const formParentId = ref('')
const formTitle = ref('')
const formDescription = ref('')
const formContent = ref('')

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

function openCreate(parentId = '') {
  error.value = ''
  editingNode.value = null
  formParentId.value = parentId || ''
  formTitle.value = ''
  formDescription.value = ''
  formContent.value = ''
  showEditor.value = true
}

function startEdit(node) {
  error.value = ''
  editingNode.value = node
  formParentId.value = node.parent_id || ''
  formTitle.value = node.title
  formDescription.value = node.description || ''
  formContent.value = node.content || ''
  showEditor.value = true
}

function closeEditor() {
  showEditor.value = false
  editingNode.value = null
}

async function saveNode() {
  error.value = ''
  try {
    if (editingNode.value) {
      const node = editingNode.value
      await apiFetch(`/api/knowledge/${node.id}`, {
        method: 'PUT',
        body: {
          parent_id: formParentId.value || null,
          title: formTitle.value,
          description: formDescription.value,
          content: formContent.value
        }
      })
      expandedIds.value[node.id] = true
      if (node.parent_id) {
        expandedIds.value[node.parent_id] = true
      }
    } else {
      const created = await apiFetch('/api/knowledge', {
        method: 'POST',
        body: {
          parent_id: formParentId.value || null,
          title: formTitle.value,
          description: formDescription.value,
          content:
            formContent.value ||
            `# ${formTitle.value}\n\n${formDescription.value}`
        }
      })
      expandedIds.value[created.id] = true
      if (created.parent_id) {
        expandedIds.value[created.parent_id] = true
      }
    }
    showEditor.value = false
    editingNode.value = null
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
    <!-- FULL-PAGE KNOWLEDGE EDITOR -->
    <form
      v-if="showEditor"
      class="editor-page"
      @submit.prevent="saveNode"
    >
      <div class="page-header">
        <div class="flex-gap">
          <h1 class="page-title">
            {{
              editingNode
                ? 'Wissenseintrag bearbeiten'
                : formParentId
                  ? 'Neue Wissensseite'
                  : 'Neues Wissensthema'
            }}
          </h1>
          <span class="badge" :class="formParentId ? 'badge-info' : 'badge-success'">
            {{ formParentId ? 'Wissensseite' : 'Hauptthema' }}
          </span>
        </div>

        <div class="editor-header-actions">
          <button type="button" class="btn" @click="closeEditor">
            Abbrechen
          </button>
          <button type="submit" class="btn btn-primary">
            Speichern
          </button>
        </div>
      </div>

      <div v-if="error" class="alert alert-error">{{ error }}</div>

      <div class="editor-card">
        <div class="editor-meta-bar">
          <div class="editor-meta-grid">
            <div class="form-group">
              <label class="form-label">Übergeordnetes Thema (optional)</label>
              <select v-model="formParentId" class="form-control">
                <option value="">Kein übergeordnetes Thema (Hauptthema)</option>
                <option
                  v-for="t in ownTopics"
                  :key="t.id"
                  :value="t.id"
                  :disabled="editingNode && t.id === editingNode.id"
                >
                  {{ t.title }}
                </option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Titel *</label>
              <input
                v-model="formTitle"
                type="text"
                class="form-control"
                placeholder="z.B. Schnittgeschwindigkeiten beim CNC-Fräsen"
                required
              />
            </div>

            <div class="form-group">
              <label class="form-label">Kurzbeschreibung</label>
              <input
                v-model="formDescription"
                type="text"
                class="form-control"
                placeholder="Kurze Zusammenfassung des Themas..."
              />
            </div>
          </div>
        </div>

        <MarkdownEditor
          v-model="formContent"
          :full-page="true"
          :owner-id="auth.user?.id"
          attachment-type="wissen"
          placeholder="Verfassen Sie hier Ihre Fachnotizen, Formelsammlungen ($v_c = \pi \cdot d \cdot n$) und fügen Sie Bilder oder Dokumente ein..."
        />
      </div>
    </form>

    <!-- STANDARD KNOWLEDGE OVERVIEW -->
    <div v-else>
      <div class="page-header">
        <div>
          <h1 class="page-title">Wissen & Notizen</h1>
          <p class="page-subtitle">
            Nachschlagewerk, Fachnotizen und Formelsammlung – nach Themen gruppiert
          </p>
        </div>
        <div class="flex-gap">
          <EditButton
            size="lg"
            show-label
            label="Neues Thema erstellen"
            icon="folder-plus"
            @click="openCreate('')"
          />
          <EditButton
            size="lg"
            show-label
            label="Neue Seite erstellen"
            icon="file-plus"
            variant="primary"
            @click="openCreate(ownTopics[0]?.id || '')"
          />
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
              <EditButton
                label="Unterseite hinzufügen"
                icon="file-plus"
                @click="openCreate(topic.id)"
              />
              <template v-if="canManage(topic)">
                <EditButton
                  label="Thema bearbeiten"
                  icon="edit"
                  @click="startEdit(topic)"
                />
                <EditButton
                  label="Thema löschen"
                  icon="delete"
                  variant="danger"
                  @click="deleteNode(topic)"
                />
              </template>
            </div>
          </div>

          <div v-if="expandedIds[topic.id]" class="collapsible-body">
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

                  <div
                    v-if="page.document || canManage(page)"
                    class="flex-gap"
                    @click.stop
                  >
                    <EditButton
                      v-if="page.document"
                      label="Seite herunterladen"
                      icon="download"
                      :href="getDocumentDownloadUrl(page.document.id)"
                      target="_self"
                    />
                    <template v-if="canManage(page)">
                      <EditButton
                        label="Seite bearbeiten"
                        icon="edit"
                        @click="startEdit(page)"
                      />
                      <EditButton
                        label="Seite löschen"
                        icon="delete"
                        variant="danger"
                        @click="deleteNode(page)"
                      />
                    </template>
                  </div>
                </div>

                <div v-if="expandedIds[page.id]" class="collapsible-body">
                  <DocumentViewer
                    v-if="page.document"
                    :document="{ ...page.document, content: page.content }"
                    :always-open="true"
                    :show-header="false"
                    :show-download="false"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.subject-pages {
  display: flex;
  flex-direction: column;
  padding-left: var(--space-4);
}

.page-card {
  box-shadow: none;
}

.page-card:last-child {
  margin-bottom: 0;
}
</style>

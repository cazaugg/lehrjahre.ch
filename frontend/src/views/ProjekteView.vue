<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const projects = ref([])
const loading = ref(false)
const error = ref('')

const searchQuery = ref('')
const filterStudent = ref('')
const filterStatus = ref('')

async function loadProjects() {
  loading.value = true
  error.value = ''
  try {
    projects.value = (await apiFetch('/api/project')) || []
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(loadProjects)

function projectStatus(proj) {
  if (proj.is_completed) return { key: 'completed', label: 'Abgeschlossen', badge: 'badge-success' }
  if (!proj.is_published) return { key: 'draft', label: 'Entwurf (Nicht freigegeben)', badge: 'badge-neutral' }
  return { key: 'active', label: 'Freigegeben / In Arbeit', badge: 'badge-info' }
}

const filteredProjects = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return projects.value.filter((p) => {
    if (filterStudent.value) {
      const sid = Number(filterStudent.value)
      if (!(p.assigned_students || []).includes(sid)) return false
    }
    if (filterStatus.value) {
      const st = projectStatus(p).key
      if (st !== filterStatus.value) return false
    }
    if (q) {
      const tasksStr = (p.tasks || []).map((t) => `${t.title} ${t.description || ''}`).join(' ')
      const stuStr = (p.assigned_student_users || []).map((u) => u.full_name).join(' ')
      const goalsStr = (p.goals || []).join(' ')
      const hay = `${p.title} ${p.description || ''} ${p.author_name || ''} ${tasksStr} ${stuStr} ${goalsStr}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

function formatDate(d) {
  if (!d) return '–'
  return new Date(d).toLocaleDateString('de-CH')
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">Projekte</h1>
        <p class="page-subtitle">
          Übersicht aller Ausbildungsprojekte, Aufgaben und Bewertungen
        </p>
      </div>
      <div v-if="auth.isTrainer" class="flex-gap">
        <button
          type="button"
          class="btn btn-primary"
          @click="router.push('/projekte/neu/planung')"
        >
          + Neues Projekt planen
        </button>
      </div>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>

    <div class="filter-bar">
      <input
        v-model="searchQuery"
        type="search"
        class="form-control filter-search"
        placeholder="Projekte, Aufgaben oder Lernende suchen..."
      />

      <select
        v-if="auth.isTrainer"
        v-model="filterStudent"
        class="form-control filter-select"
      >
        <option value="">Alle Lernenden</option>
        <option v-for="stu in auth.companyStudents" :key="stu.id" :value="stu.id">
          {{ stu.full_name }}
        </option>
      </select>

      <select v-model="filterStatus" class="form-control filter-select">
        <option value="">Alle Status</option>
        <option v-if="auth.isTrainer" value="draft">Entwurf</option>
        <option value="active">Freigegeben / In Arbeit</option>
        <option value="completed">Abgeschlossen</option>
      </select>

      <span class="text-muted">{{ filteredProjects.length }} Projekte</span>
    </div>

    <div v-if="loading" class="card">Lade Projekte...</div>
    <div v-else-if="filteredProjects.length === 0" class="card empty-state">
      Keine passenden Projekte gefunden.
    </div>

    <div v-else class="project-list">
      <div
        v-for="proj in filteredProjects"
        :key="proj.id"
        class="card project-row"
        @click="router.push(`/projekte/${proj.id}`)"
      >
        <div class="project-row-main">
          <div class="flex-gap">
            <h3 class="project-row-title">{{ proj.title }}</h3>
            <span class="badge" :class="projectStatus(proj).badge">
              {{ projectStatus(proj).label }}
            </span>
          </div>

          <div class="text-muted project-meta">
            <span>Zeitraum: {{ formatDate(proj.start_date) }} – {{ formatDate(proj.due_date) }}</span>
            <span v-if="proj.author_name"> · Verantwortlich: {{ proj.author_name }}</span>
            <span> · {{ (proj.tasks || []).length }} Aufgaben</span>
            <span> · {{ (proj.goals || []).length }} Ziele</span>
          </div>

          <div
            v-if="proj.assigned_student_users && proj.assigned_student_users.length > 0"
            class="flex-gap"
            style="margin-top: var(--space-2)"
          >
            <span class="text-muted">Lernende:</span>
            <span
              v-for="stu in proj.assigned_student_users"
              :key="stu.id"
              class="badge badge-neutral"
            >
              {{ stu.full_name }}
            </span>
          </div>
        </div>

        <div class="flex-gap" @click.stop>
          <router-link :to="`/projekte/${proj.id}`" class="btn btn-sm">
            Projekt öffnen
          </router-link>
          <router-link
            v-if="auth.isTrainer"
            :to="`/projekte/${proj.id}/planung`"
            class="btn btn-sm"
          >
            Planung
          </router-link>
          <router-link
            v-if="auth.isTrainer"
            :to="`/projekte/${proj.id}/auswertung`"
            class="btn btn-sm btn-primary"
          >
            Auswertung
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.project-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.project-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-4);
  margin-bottom: 0;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.project-row:hover {
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-md);
}

.project-row-main {
  flex: 1;
  min-width: 260px;
}

.project-row-title {
  margin: 0;
  font-size: 1.08rem;
}

.project-meta {
  margin-top: 4px;
}
</style>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'
import ModalDialog from '../components/ui/ModalDialog.vue'
import DocumentManager from '../components/ui/DocumentManager.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const activeSection = computed(() => route.params.section || 'vorgesetzte')
const allUsers = ref([])
const relations = ref([])
const error = ref('')
const message = ref('')

// Filter & Search + Collapsible state
const searchQuery = ref('')
const filterJobTitle = ref('')
const expandedIds = ref({})

// Create User Modal
const showUserModal = ref(false)
const newRole = ref('lernender')
const newName = ref('')
const newSurname = ref('')
const newCompanyEmail = ref('')
const newCompanyPhone = ref('')
const newJobTitle = ref('')
const newStartDate = ref('')
const newEndDate = ref('')
const newPassword = ref('Lehrjahre2026!')
const newSupervisorId = ref('')

// Per-student supervisor select map
const addSupervisorSelect = ref({})

const supervisors = computed(() =>
  allUsers.value.filter((u) => u.role === 'ausbildner')
)

const apprentices = computed(() =>
  allUsers.value.filter((u) => u.role === 'lernender')
)

const filteredSupervisors = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return supervisors.value.filter((u) => {
    if (filterJobTitle.value && u.job_title !== filterJobTitle.value) return false
    if (q) {
      const hay = `${u.full_name} ${u.job_title} ${u.company_email || ''} ${u.company_phone || ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

const filteredApprentices = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return apprentices.value.filter((u) => {
    if (filterJobTitle.value && u.job_title !== filterJobTitle.value) return false
    if (q) {
      const hay = `${u.full_name} ${u.job_title} ${u.company_email || ''} ${u.school_address || ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

function supervisorsForStudent(studentId) {
  return relations.value.filter((r) => r.student === studentId)
}

function studentsForSupervisor(supId) {
  return relations.value.filter((r) => r.supervisor === supId)
}

function toggleExpand(userId) {
  expandedIds.value[userId] = !expandedIds.value[userId]
}

async function loadUsers() {
  error.value = ''
  try {
    const res = await apiFetch('/api/user')
    allUsers.value = res.users || []
    relations.value = res.relations || []
    await auth.loadCompanyStudents()
  } catch (e) {
    error.value = e.message
  }
}

onMounted(loadUsers)

function openCreateUser(role = 'lernender') {
  newRole.value = role
  newName.value = ''
  newSurname.value = ''
  newCompanyEmail.value = ''
  newCompanyPhone.value = ''
  newJobTitle.value =
    role === 'lernender'
      ? auth.memProfessions[4] || auth.memProfessions[0] || 'Polymechanikerin / Polymechaniker EFZ'
      : auth.trainerFunctions[1] || 'Berufsbildner'
  newStartDate.value = role === 'lernender' ? '2026-08-10' : ''
  newEndDate.value = role === 'lernender' ? '2030-07-31' : ''
  newPassword.value = 'Lehrjahre2026!'
  newSupervisorId.value = supervisors.value[0]?.id || ''
  showUserModal.value = true
}

async function createUser() {
  error.value = ''
  try {
    const created = await apiFetch('/api/user', {
      method: 'POST',
      body: {
        role: newRole.value,
        name: newName.value,
        surname: newSurname.value,
        company_email: newCompanyEmail.value,
        company_phone: newCompanyPhone.value,
        job_title: newJobTitle.value,
        start_date: newStartDate.value || null,
        end_date: newEndDate.value || null,
        password: newPassword.value,
        supervisor_id: newRole.value === 'lernender' ? newSupervisorId.value : null
      }
    })
    showUserModal.value = false
    expandedIds.value[created.id] = true
    await loadUsers()
    if (created.role === 'lernender') {
      router.push('/personen/lernende')
    }
  } catch (e) {
    error.value = e.message
  }
}

async function saveApprenticeProfile(stu) {
  error.value = ''
  message.value = ''
  try {
    await apiFetch(`/api/user/${stu.id}`, {
      method: 'PUT',
      body: stu
    })
    message.value = `Stammdaten von ${stu.full_name} wurden gespeichert.`
    await loadUsers()
  } catch (e) {
    error.value = e.message
  }
}

async function linkSupervisor(studentId) {
  const supId = addSupervisorSelect.value[studentId]
  if (!supId) return
  try {
    await apiFetch('/api/user/relation', {
      method: 'POST',
      body: {
        supervisor: Number(supId),
        student: studentId
      }
    })
    addSupervisorSelect.value[studentId] = ''
    await loadUsers()
  } catch (e) {
    error.value = e.message
  }
}

async function unlinkSupervisor(relationId) {
  try {
    await apiFetch(`/api/user/relation/${relationId}`, { method: 'DELETE' })
    await loadUsers()
  } catch (e) {
    error.value = e.message
  }
}

function formatDate(d) {
  if (!d) return '–'
  return new Date(d).toLocaleDateString('de-CH')
}
</script>

<template>
  <div>
    <!-- Section 1 & 2 Header -->
    <div v-if="activeSection === 'vorgesetzte' || activeSection === 'lernende'" class="page-header">
      <div>
        <h1 class="page-title">
          <template v-if="activeSection === 'vorgesetzte'">Vorgesetzte & Ausbildner</template>
          <template v-else>Lernende (Stammdaten & Kontakte)</template>
        </h1>
        <p class="page-subtitle">
          <template v-if="activeSection === 'vorgesetzte'">
            Kontaktangaben der Berufsbildner, Fachvorgesetzten, Kursleiter, Lehrer und HR
          </template>
          <template v-else>
            Alle Lernenden im Betrieb (Neueste Lehrstarts zuerst – zum Aufklappen anklicken)
          </template>
        </p>
      </div>
      <div v-if="auth.isAdminOrHr" class="flex-gap">
        <button type="button" class="btn" @click="openCreateUser('ausbildner')">
          + Ausbildner/in erfassen
        </button>
        <button type="button" class="btn btn-primary" @click="openCreateUser('lernender')">
          + Lernende/n erfassen
        </button>
      </div>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>
    <div v-if="message" class="alert alert-success">{{ message }}</div>

    <!-- Section 1: Vorgesetzte (Kontakt) -->
    <div v-if="activeSection === 'vorgesetzte'">
      <div class="filter-bar">
        <input
          v-model="searchQuery"
          type="search"
          class="form-control filter-search"
          placeholder="Ausbildner nach Name, Funktion oder E-Mail suchen..."
        />

        <select v-model="filterJobTitle" class="form-control filter-select">
          <option value="">Alle Funktionen</option>
          <option v-for="fn in auth.trainerFunctions" :key="fn" :value="fn">
            {{ fn }}
          </option>
        </select>

        <span class="text-muted">{{ filteredSupervisors.length }} Personen</span>
      </div>

      <div v-if="filteredSupervisors.length === 0" class="card empty-state">
        Keine passenden Ausbildner gefunden.
      </div>

      <div v-else>
        <div
          v-for="sup in filteredSupervisors"
          :key="sup.id"
          class="collapsible-card"
        >
          <div class="collapsible-header" @click="toggleExpand(sup.id)">
            <div class="flex-gap">
              <span class="expand-indicator">
                {{ expandedIds[sup.id] ? '▾' : '▸' }}
              </span>
              <div class="avatar-circle">
                <img
                  v-if="sup.picture_document"
                  :src="`/api/documents/${sup.picture_document}/file`"
                  alt="Profilbild"
                />
                <span v-else>{{ sup.name[0] }}{{ sup.surname[0] }}</span>
              </div>
              <div>
                <div class="flex-gap">
                  <strong>{{ sup.full_name }}</strong>
                  <span class="badge badge-info">{{ sup.job_title }}</span>
                </div>
                <div class="text-muted" style="margin-top: 2px">
                  {{ sup.company_email }}
                  <span v-if="sup.company_phone"> · {{ sup.company_phone }}</span>
                </div>
              </div>
            </div>

            <div class="flex-gap">
              <span class="badge badge-success">
                {{ studentsForSupervisor(sup.id).length }} betreute Lernende
              </span>
            </div>
          </div>

          <div v-if="expandedIds[sup.id]" class="collapsible-body">
            <div class="contact-grid">
              <div class="contact-card">
                <h4>Betrieb ({{ sup.company }})</h4>
                <div class="text-muted">{{ sup.company_address || '–' }}</div>
                <div>
                  <a v-if="sup.company_email" :href="`mailto:${sup.company_email}`">
                    {{ sup.company_email }}
                  </a>
                </div>
                <div class="text-muted">{{ sup.company_phone || '–' }}</div>
              </div>

              <div class="contact-card">
                <h4>Berufsfachschule / ÜK-Zentrum</h4>
                <div class="text-muted">{{ sup.school_address || '–' }}</div>
                <div>
                  <a v-if="sup.school_email" :href="`mailto:${sup.school_email}`">
                    {{ sup.school_email }}
                  </a>
                </div>
                <div class="text-muted">{{ sup.school_phone || '–' }}</div>
              </div>

              <div class="contact-card">
                <h4>Betreute Lernende</h4>
                <div v-if="studentsForSupervisor(sup.id).length === 0" class="text-muted">
                  Keine direkt zugewiesenen Lernenden.
                </div>
                <div v-else class="flex-gap">
                  <span
                    v-for="rel in studentsForSupervisor(sup.id)"
                    :key="rel.id"
                    class="badge badge-info"
                  >
                    {{ rel.student_name }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Section 2: Lernende (Admin) -->
    <div v-else-if="activeSection === 'lernende'">
      <div class="filter-bar">
        <input
          v-model="searchQuery"
          type="search"
          class="form-control filter-search"
          placeholder="Lernende nach Name, Beruf oder E-Mail durchsuchen..."
        />

        <select v-model="filterJobTitle" class="form-control filter-select">
          <option value="">Alle MEM-Berufe</option>
          <option v-for="prof in auth.memProfessions" :key="prof" :value="prof">
            {{ prof }}
          </option>
        </select>

        <span class="text-muted">{{ filteredApprentices.length }} Lernende</span>
      </div>

      <div v-if="filteredApprentices.length === 0" class="card empty-state">
        Keine passenden Lernenden gefunden.
      </div>

      <div v-else>
        <div
          v-for="stu in filteredApprentices"
          :key="stu.id"
          class="collapsible-card"
        >
          <div class="collapsible-header" @click="toggleExpand(stu.id)">
            <div class="flex-gap">
              <span class="expand-indicator">
                {{ expandedIds[stu.id] ? '▾' : '▸' }}
              </span>
              <div class="avatar-circle">
                <img
                  v-if="stu.picture_document"
                  :src="`/api/documents/${stu.picture_document}/file`"
                  alt="Profilbild"
                />
                <span v-else>{{ stu.name[0] }}{{ stu.surname[0] }}</span>
              </div>
              <div>
                <div class="flex-gap">
                  <strong>{{ stu.full_name }}</strong>
                  <span class="badge badge-success">{{ stu.job_title }}</span>
                </div>
                <div class="text-muted" style="margin-top: 2px">
                  Lehrzeit: {{ formatDate(stu.start_date) }} bis {{ formatDate(stu.end_date) }}
                  · {{ stu.company_email }}
                </div>
              </div>
            </div>

            <div class="flex-gap">
              <span class="badge badge-info">
                {{ supervisorsForStudent(stu.id).length }} Ausbildner
              </span>
            </div>
          </div>

          <div v-if="expandedIds[stu.id]" class="collapsible-body">
            <form @submit.prevent="saveApprenticeProfile(stu)">
              <div class="grid-2">
                <div class="form-group">
                  <label class="form-label">Vorname</label>
                  <input
                    v-model="stu.name"
                    type="text"
                    class="form-control"
                    :disabled="!auth.isAdminOrHr"
                  />
                </div>
                <div class="form-group">
                  <label class="form-label">Nachname</label>
                  <input
                    v-model="stu.surname"
                    type="text"
                    class="form-control"
                    :disabled="!auth.isAdminOrHr"
                  />
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">MEM-Lehrberuf</label>
                <select
                  v-model="stu.job_title"
                  class="form-control"
                  :disabled="!auth.isAdminOrHr"
                >
                  <option v-for="prof in auth.memProfessions" :key="prof" :value="prof">
                    {{ prof }}
                  </option>
                </select>
              </div>

              <div class="grid-2">
                <div class="form-group">
                  <label class="form-label">Lehrstart</label>
                  <input
                    v-model="stu.start_date"
                    type="date"
                    class="form-control"
                    :disabled="!auth.isAdminOrHr"
                  />
                </div>
                <div class="form-group">
                  <label class="form-label">Lehrende</label>
                  <input
                    v-model="stu.end_date"
                    type="date"
                    class="form-control"
                    :disabled="!auth.isAdminOrHr"
                  />
                </div>
              </div>

              <div class="grid-3" style="margin-top: var(--space-3)">
                <div class="contact-card">
                  <h4>Privat</h4>
                  <div class="form-group">
                    <label class="form-label">Adresse</label>
                    <input
                      v-model="stu.private_address"
                      class="form-control"
                      :disabled="!auth.isAdminOrHr"
                    />
                  </div>
                  <div class="form-group">
                    <label class="form-label">E-Mail</label>
                    <input
                      v-model="stu.private_email"
                      class="form-control"
                      :disabled="!auth.isAdminOrHr"
                    />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Telefon</label>
                    <input
                      v-model="stu.private_phone"
                      class="form-control"
                      :disabled="!auth.isAdminOrHr"
                    />
                  </div>
                </div>

                <div class="contact-card">
                  <h4>Berufsfachschule</h4>
                  <div class="form-group">
                    <label class="form-label">Schule & Adresse</label>
                    <input
                      v-model="stu.school_address"
                      class="form-control"
                      :disabled="!auth.isAdminOrHr"
                    />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Schul-E-Mail</label>
                    <input
                      v-model="stu.school_email"
                      class="form-control"
                      :disabled="!auth.isAdminOrHr"
                    />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Schul-Telefon</label>
                    <input
                      v-model="stu.school_phone"
                      class="form-control"
                      :disabled="!auth.isAdminOrHr"
                    />
                  </div>
                </div>

                <div class="contact-card">
                  <h4>Lehrbetrieb</h4>
                  <div class="form-group">
                    <label class="form-label">Standort / Adresse</label>
                    <input
                      v-model="stu.company_address"
                      class="form-control"
                      :disabled="!auth.isAdminOrHr"
                    />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Firmen-E-Mail</label>
                    <input
                      v-model="stu.company_email"
                      class="form-control"
                      :disabled="!auth.isAdminOrHr"
                    />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Firmen-Telefon</label>
                    <input
                      v-model="stu.company_phone"
                      class="form-control"
                      :disabled="!auth.isAdminOrHr"
                    />
                  </div>
                </div>
              </div>

              <div v-if="auth.isAdminOrHr" style="margin-top: var(--space-4)">
                <button type="submit" class="btn btn-primary">
                  Stammdaten speichern
                </button>
              </div>
            </form>

            <!-- Supervisor Assignment -->
            <div
              style="
                margin-top: var(--space-5);
                padding-top: var(--space-4);
                border-top: 1px solid var(--color-border);
              "
            >
              <h4>Zugewiesene Ausbildner & Vorgesetzte</h4>
              <div class="flex-gap" style="margin-bottom: var(--space-3)">
                <div
                  v-for="rel in supervisorsForStudent(stu.id)"
                  :key="rel.id"
                  class="sup-chip"
                >
                  <span>
                    <strong>{{ rel.supervisor_name }}</strong> ({{
                      rel.supervisor_job_title
                    }})
                  </span>
                  <button
                    v-if="auth.isTrainer"
                    type="button"
                    class="btn btn-sm btn-danger"
                    @click="unlinkSupervisor(rel.id)"
                  >
                    ×
                  </button>
                </div>
              </div>

              <div v-if="auth.isTrainer" class="flex-gap">
                <select
                  v-model="addSupervisorSelect[stu.id]"
                  class="form-control"
                  style="max-width: 320px"
                >
                  <option value="">Ausbildner/in zum Zuweisen wählen...</option>
                  <option v-for="sup in supervisors" :key="sup.id" :value="sup.id">
                    {{ sup.full_name }} ({{ sup.job_title }})
                  </option>
                </select>
                <button type="button" class="btn" @click="linkSupervisor(stu.id)">
                  Zuweisen
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Section 3: Lehrvertrag -->
    <div v-else-if="activeSection === 'vertrag'">
      <DocumentManager
        document-type="vertrag"
        title="Lehrverträge & Ausbildungsvereinbarungen"
        subtitle="Kantonale Lehrverträge, Anhänge und Bildungspläne (Neueste zuerst)"
      />
    </div>

    <!-- Section 4: Bewerbung -->
    <div v-else-if="activeSection === 'bewerbung'">
      <DocumentManager
        document-type="bewerbung"
        title="Bewerbungsunterlagen & Rekrutierungsdossiers"
        subtitle="Lebensläufe, Eignungstests (Multicheck/Basic-Check) und Schnupperberichte"
      />
    </div>

    <!-- Modal: Create New User -->
    <ModalDialog
      :show="showUserModal"
      :title="
        newRole === 'lernender'
          ? 'Neue/n Lernende/n erfassen'
          : 'Neue/n Ausbildner/in erfassen'
      "
      @close="showUserModal = false"
    >
      <form @submit.prevent="createUser">
        <div class="grid-2">
          <div class="form-group">
            <label class="form-label">Vorname *</label>
            <input v-model="newName" type="text" class="form-control" required />
          </div>
          <div class="form-group">
            <label class="form-label">Nachname *</label>
            <input v-model="newSurname" type="text" class="form-control" required />
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">
            {{
              newRole === 'lernender'
                ? 'MEM-Beruf (EFZ / EBA) *'
                : 'Funktion im Betrieb *'
            }}
          </label>
          <select v-model="newJobTitle" class="form-control" required>
            <option
              v-for="opt in newRole === 'lernender'
                ? auth.memProfessions
                : auth.trainerFunctions"
              :key="opt"
              :value="opt"
            >
              {{ opt }}
            </option>
          </select>
        </div>

        <div class="grid-2">
          <div class="form-group">
            <label class="form-label">Firmen-E-Mail (Login) *</label>
            <input
              v-model="newCompanyEmail"
              type="email"
              class="form-control"
              required
            />
          </div>
          <div class="form-group">
            <label class="form-label">Firmen-Telefon</label>
            <input v-model="newCompanyPhone" type="text" class="form-control" />
          </div>
        </div>

        <div v-if="newRole === 'lernender'" class="grid-2">
          <div class="form-group">
            <label class="form-label">Lehrstart</label>
            <input v-model="newStartDate" type="date" class="form-control" />
          </div>
          <div class="form-group">
            <label class="form-label">Lehrende</label>
            <input v-model="newEndDate" type="date" class="form-control" />
          </div>
        </div>

        <div v-if="newRole === 'lernender'" class="form-group">
          <label class="form-label">Haupt-Berufsbildner/in zuweisen</label>
          <select v-model="newSupervisorId" class="form-control">
            <option value="">Später zuweisen</option>
            <option v-for="sup in supervisors" :key="sup.id" :value="sup.id">
              {{ sup.full_name }} ({{ sup.job_title }})
            </option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Initialpasswort *</label>
          <input v-model="newPassword" type="text" class="form-control" required />
        </div>

        <div class="flex-between">
          <button type="button" class="btn" @click="showUserModal = false">
            Abbrechen
          </button>
          <button type="submit" class="btn btn-primary">Benutzer anlegen</button>
        </div>
      </form>
    </ModalDialog>
  </div>
</template>

<style scoped>
.avatar-circle {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.85rem;
  overflow: hidden;
  border: 1px solid #f5c2c9;
  flex-shrink: 0;
}

.avatar-circle img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.contact-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-4);
}

.contact-card {
  background: var(--color-surface-muted);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
}

.sup-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0.35rem 0.7rem;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
}
</style>

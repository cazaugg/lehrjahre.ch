<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'
import ModalDialog from '../components/ui/ModalDialog.vue'
import PersonDocuments from '../components/ui/PersonDocuments.vue'
import EditButton from '../components/ui/EditButton.vue'

const auth = useAuthStore()

const allUsers = ref([])
const relations = ref([])
const error = ref('')
const message = ref('')

// Filter & Search + Collapsible state
const searchQuery = ref('')
const filterRole = ref('')
const expandedIds = ref({})

// Inline editing of learner master data
const editingPersonId = ref(null)
const profileDraft = reactive({})
const profileFields = [
  'name',
  'surname',
  'job_title',
  'start_date',
  'end_date',
  'private_address',
  'private_email',
  'private_phone',
  'school_address',
  'school_email',
  'school_phone',
  'company_address',
  'company_email',
  'company_phone'
]

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
const newPassword = ref('')
const newSupervisorId = ref('')

// Per-student supervisor select map
const addSupervisorSelect = ref({})

const supervisors = computed(() =>
  allUsers.value.filter((u) => u.role === 'ausbildner' || u.role === 'admin')
)

const people = computed(() =>
  [...allUsers.value].sort((a, b) =>
    `${a.surname} ${a.name}`.localeCompare(`${b.surname} ${b.name}`, 'de-CH')
  )
)

const filteredPeople = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return people.value.filter((u) => {
    if (filterRole.value && u.role !== filterRole.value) return false
    if (q) {
      const hay = `${u.full_name} ${u.job_title} ${u.company_email || ''} ${u.company_phone || ''} ${u.school_address || ''}`.toLowerCase()
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

const ROLE_LABELS = {
  admin: 'Administrator/in',
  ausbildner: 'Ausbildner/in',
  lernender: 'Lernende/r'
}

function roleLabel(role) {
  return ROLE_LABELS[role] || role
}

function roleBadgeClass(role) {
  if (role === 'admin') return 'badge-warning'
  if (role === 'ausbildner') return 'badge-info'
  return 'badge-success'
}

function isSupervisorRole(role) {
  return role === 'ausbildner' || role === 'admin'
}

const createUserTitle = computed(() =>
  newRole.value === 'lernender'
    ? 'Neue/n Lernende/n erfassen'
    : newRole.value === 'admin'
      ? 'Neue/n Administrator/in erfassen'
      : 'Neue/n Ausbildner/in erfassen'
)

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
      : role === 'admin'
        ? 'Administrator'
        : auth.trainerFunctions[1] || 'Berufsbildner'
  newStartDate.value = role === 'lernender' ? '2026-08-10' : ''
  newEndDate.value = role === 'lernender' ? '2030-07-31' : ''
  newPassword.value = ''
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
    searchQuery.value = ''
    filterRole.value = ''
    expandedIds.value[created.id] = true
    await loadUsers()
  } catch (e) {
    error.value = e.message
  }
}

function startEditPerson(person) {
  error.value = ''
  message.value = ''
  for (const field of profileFields) {
    profileDraft[field] = person[field] ?? ''
  }
  profileDraft.id = person.id
  editingPersonId.value = person.id
  expandedIds.value[person.id] = true
}

function cancelEditPerson() {
  editingPersonId.value = null
}

async function saveApprenticeProfile() {
  error.value = ''
  message.value = ''
  try {
    await apiFetch(`/api/user/${profileDraft.id}`, {
      method: 'PUT',
      body: profileDraft
    })
    message.value = `Stammdaten von ${profileDraft.name} ${profileDraft.surname} wurden gespeichert.`
    editingPersonId.value = null
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
    <div class="page-header">
      <div>
        <h1 class="page-title">Personen</h1>
        <p class="page-subtitle">
          Ausbildner, Vorgesetzte und Lernende im Betrieb – zum Aufklappen anklicken
        </p>
      </div>
      <div v-if="auth.isAdmin" class="flex-gap">
        <EditButton
          size="lg"
          show-label
          icon="user-plus"
          label="Ausbildner/in erfassen"
          @click="openCreateUser('ausbildner')"
        />
        <EditButton
          size="lg"
          show-label
          icon="user-plus"
          variant="primary"
          label="Lernende/n erfassen"
          @click="openCreateUser('lernender')"
        />
        <EditButton
          size="lg"
          show-label
          icon="user-plus"
          label="Administrator/in erfassen"
          @click="openCreateUser('admin')"
        />
      </div>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>
    <div v-if="message" class="alert alert-success">{{ message }}</div>

    <div class="filter-bar">
      <input
        v-model="searchQuery"
        type="search"
        class="form-control filter-search"
        placeholder="Personen nach Name, Funktion oder E-Mail durchsuchen..."
      />

      <select v-model="filterRole" class="form-control filter-select">
        <option value="">Alle Personen</option>
        <option value="ausbildner">Ausbildner</option>
        <option value="admin">Administrator</option>
        <option value="lernender">Lernende</option>
      </select>

      <span class="text-muted">{{ filteredPeople.length }} Personen</span>
    </div>

    <div v-if="filteredPeople.length === 0" class="card empty-state">
      Keine passenden Personen gefunden.
    </div>

    <div v-else>
      <div
        v-for="person in filteredPeople"
        :key="person.id"
        class="collapsible-card"
      >
        <div class="collapsible-header" @click="toggleExpand(person.id)">
          <div class="flex-gap">
            <span class="expand-indicator">
              {{ expandedIds[person.id] ? '▾' : '▸' }}
            </span>
            <div class="avatar-circle">
              <img
                v-if="person.picture_document"
                :src="`/api/documents/${person.picture_document}/file`"
                alt="Profilbild"
              />
              <span v-else>{{ person.name[0] }}{{ person.surname[0] }}</span>
            </div>
            <div>
              <div class="flex-gap">
                <strong>{{ person.full_name }}</strong>
                <span class="badge" :class="roleBadgeClass(person.role)">
                  {{ roleLabel(person.role) }}
                </span>
                <span class="text-muted">{{ person.job_title }}</span>
              </div>
              <div class="text-muted" style="margin-top: 2px">
                <template v-if="person.role === 'lernender'">
                  Lehrzeit: {{ formatDate(person.start_date) }} bis
                  {{ formatDate(person.end_date) }} ·
                </template>
                {{ person.company_email }}
                <span v-if="person.company_phone"> · {{ person.company_phone }}</span>
              </div>
            </div>
          </div>

          <div class="flex-gap" @click.stop>
            <span v-if="isSupervisorRole(person.role)" class="badge badge-success">
              {{ studentsForSupervisor(person.id).length }} betreute Lernende
            </span>
            <span v-else class="badge badge-info">
              {{ supervisorsForStudent(person.id).length }} Ausbildner
            </span>
            <EditButton
              v-if="person.can_edit_contacts"
              label="Kontaktdaten / Stammdaten bearbeiten"
              icon="edit"
              @click="startEditPerson(person)"
            />
          </div>
        </div>

        <div v-if="expandedIds[person.id]" class="collapsible-body">
          <!-- Ausbildner / Administrator -->
          <template v-if="isSupervisorRole(person.role)">
            <form
              v-if="editingPersonId === person.id"
              @submit.prevent="saveApprenticeProfile"
            >
              <div class="grid-3">
                <div class="contact-card">
                  <h4>Privat</h4>
                  <div class="form-group">
                    <label class="form-label">Adresse</label>
                    <input v-model="profileDraft.private_address" class="form-control" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">E-Mail</label>
                    <input v-model="profileDraft.private_email" class="form-control" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Telefon</label>
                    <input v-model="profileDraft.private_phone" class="form-control" />
                  </div>
                </div>

                <div class="contact-card">
                  <h4>Berufsfachschule / ÜK-Zentrum</h4>
                  <div class="form-group">
                    <label class="form-label">Schule & Adresse</label>
                    <input v-model="profileDraft.school_address" class="form-control" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Schul-E-Mail</label>
                    <input v-model="profileDraft.school_email" class="form-control" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Schul-Telefon</label>
                    <input v-model="profileDraft.school_phone" class="form-control" />
                  </div>
                </div>

                <div class="contact-card">
                  <h4>Betrieb ({{ person.company }})</h4>
                  <div class="form-group">
                    <label class="form-label">Standort / Adresse</label>
                    <input v-model="profileDraft.company_address" class="form-control" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Firmen-E-Mail</label>
                    <input v-model="profileDraft.company_email" class="form-control" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Firmen-Telefon</label>
                    <input v-model="profileDraft.company_phone" class="form-control" />
                  </div>
                </div>
              </div>

              <div class="flex-gap" style="margin-top: var(--space-4)">
                <button type="submit" class="btn btn-primary">Speichern</button>
                <button type="button" class="btn" @click="cancelEditPerson">Abbrechen</button>
              </div>
            </form>

            <div v-else class="contact-grid">
              <div v-if="person.can_view_private" class="contact-card">
                <h4>Privat</h4>
                <div class="text-muted">{{ person.private_address || '–' }}</div>
                <div>
                  <a v-if="person.private_email" :href="`mailto:${person.private_email}`">
                    {{ person.private_email }}
                  </a>
                </div>
                <div class="text-muted">{{ person.private_phone || '–' }}</div>
              </div>

              <div class="contact-card">
                <h4>Betrieb ({{ person.company }})</h4>
                <div class="text-muted">{{ person.company_address || '–' }}</div>
                <div>
                  <a v-if="person.company_email" :href="`mailto:${person.company_email}`">
                    {{ person.company_email }}
                  </a>
                </div>
                <div class="text-muted">{{ person.company_phone || '–' }}</div>
              </div>

              <div class="contact-card">
                <h4>Berufsfachschule / ÜK-Zentrum</h4>
                <div class="text-muted">{{ person.school_address || '–' }}</div>
                <div>
                  <a v-if="person.school_email" :href="`mailto:${person.school_email}`">
                    {{ person.school_email }}
                  </a>
                </div>
                <div class="text-muted">{{ person.school_phone || '–' }}</div>
              </div>

              <div class="contact-card">
                <h4>Betreute Lernende</h4>
                <div
                  v-if="studentsForSupervisor(person.id).length === 0"
                  class="text-muted"
                >
                  Keine direkt zugewiesenen Lernenden.
                </div>
                <div v-else class="flex-gap">
                  <span
                    v-for="rel in studentsForSupervisor(person.id)"
                    :key="rel.id"
                    class="badge badge-info"
                  >
                    {{ rel.student_name }}
                  </span>
                </div>
              </div>
            </div>
          </template>

          <!-- Lernende/r -->
          <template v-else>
            <h4 style="margin: 0 0 var(--space-3) 0">Stammdaten</h4>

            <form
              v-if="editingPersonId === person.id"
              @submit.prevent="saveApprenticeProfile"
            >
              <div class="grid-2">
                <div class="form-group">
                  <label class="form-label">Vorname</label>
                  <input v-model="profileDraft.name" type="text" class="form-control" />
                </div>
                <div class="form-group">
                  <label class="form-label">Nachname</label>
                  <input v-model="profileDraft.surname" type="text" class="form-control" />
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">MEM-Lehrberuf</label>
                <select v-model="profileDraft.job_title" class="form-control">
                  <option v-for="prof in auth.memProfessions" :key="prof" :value="prof">
                    {{ prof }}
                  </option>
                </select>
              </div>

              <div class="grid-2">
                <div class="form-group">
                  <label class="form-label">Lehrstart</label>
                  <input v-model="profileDraft.start_date" type="date" class="form-control" />
                </div>
                <div class="form-group">
                  <label class="form-label">Lehrende</label>
                  <input v-model="profileDraft.end_date" type="date" class="form-control" />
                </div>
              </div>

              <div class="grid-3" style="margin-top: var(--space-3)">
                <div class="contact-card">
                  <h4>Privat</h4>
                  <div class="form-group">
                    <label class="form-label">Adresse</label>
                    <input v-model="profileDraft.private_address" class="form-control" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">E-Mail</label>
                    <input v-model="profileDraft.private_email" class="form-control" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Telefon</label>
                    <input v-model="profileDraft.private_phone" class="form-control" />
                  </div>
                </div>

                <div class="contact-card">
                  <h4>Berufsfachschule</h4>
                  <div class="form-group">
                    <label class="form-label">Schule & Adresse</label>
                    <input v-model="profileDraft.school_address" class="form-control" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Schul-E-Mail</label>
                    <input v-model="profileDraft.school_email" class="form-control" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Schul-Telefon</label>
                    <input v-model="profileDraft.school_phone" class="form-control" />
                  </div>
                </div>

                <div class="contact-card">
                  <h4>Lehrbetrieb</h4>
                  <div class="form-group">
                    <label class="form-label">Standort / Adresse</label>
                    <input v-model="profileDraft.company_address" class="form-control" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Firmen-E-Mail</label>
                    <input v-model="profileDraft.company_email" class="form-control" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Firmen-Telefon</label>
                    <input v-model="profileDraft.company_phone" class="form-control" />
                  </div>
                </div>
              </div>

              <div class="flex-gap" style="margin-top: var(--space-4)">
                <button type="submit" class="btn btn-primary">Speichern</button>
                <button type="button" class="btn" @click="cancelEditPerson">Abbrechen</button>
              </div>
            </form>

            <div v-else>
              <div class="grid-2">
                <div class="detail-item">
                  <div class="detail-label">Vorname</div>
                  <div class="detail-value">{{ person.name || '–' }}</div>
                </div>
                <div class="detail-item">
                  <div class="detail-label">Nachname</div>
                  <div class="detail-value">{{ person.surname || '–' }}</div>
                </div>
              </div>

              <div class="detail-item">
                <div class="detail-label">MEM-Lehrberuf</div>
                <div class="detail-value">{{ person.job_title || '–' }}</div>
              </div>

              <div class="grid-2">
                <div class="detail-item">
                  <div class="detail-label">Lehrstart</div>
                  <div class="detail-value">{{ formatDate(person.start_date) }}</div>
                </div>
                <div class="detail-item">
                  <div class="detail-label">Lehrende</div>
                  <div class="detail-value">{{ formatDate(person.end_date) }}</div>
                </div>
              </div>

              <div class="contact-grid" style="margin-top: var(--space-3)">
                <div v-if="person.can_view_private" class="contact-card">
                  <h4>Privat</h4>
                  <div class="detail-item">
                    <div class="detail-label">Adresse</div>
                    <div class="detail-value">{{ person.private_address || '–' }}</div>
                  </div>
                  <div class="detail-item">
                    <div class="detail-label">E-Mail</div>
                    <div class="detail-value">{{ person.private_email || '–' }}</div>
                  </div>
                  <div class="detail-item">
                    <div class="detail-label">Telefon</div>
                    <div class="detail-value">{{ person.private_phone || '–' }}</div>
                  </div>
                </div>

                <div class="contact-card">
                  <h4>Berufsfachschule</h4>
                  <div class="detail-item">
                    <div class="detail-label">Schule & Adresse</div>
                    <div class="detail-value">{{ person.school_address || '–' }}</div>
                  </div>
                  <div class="detail-item">
                    <div class="detail-label">Schul-E-Mail</div>
                    <div class="detail-value">{{ person.school_email || '–' }}</div>
                  </div>
                  <div class="detail-item">
                    <div class="detail-label">Schul-Telefon</div>
                    <div class="detail-value">{{ person.school_phone || '–' }}</div>
                  </div>
                </div>

                <div class="contact-card">
                  <h4>Lehrbetrieb</h4>
                  <div class="detail-item">
                    <div class="detail-label">Standort / Adresse</div>
                    <div class="detail-value">{{ person.company_address || '–' }}</div>
                  </div>
                  <div class="detail-item">
                    <div class="detail-label">Firmen-E-Mail</div>
                    <div class="detail-value">{{ person.company_email || '–' }}</div>
                  </div>
                  <div class="detail-item">
                    <div class="detail-label">Firmen-Telefon</div>
                    <div class="detail-value">{{ person.company_phone || '–' }}</div>
                  </div>
                </div>
              </div>
            </div>

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
                  v-for="rel in supervisorsForStudent(person.id)"
                  :key="rel.id"
                  class="sup-chip"
                >
                  <span>
                    <strong>{{ rel.supervisor_name }}</strong> ({{
                      rel.supervisor_job_title
                    }})
                  </span>
                  <EditButton
                    v-if="auth.isAdmin"
                    label="Zuweisung entfernen"
                    icon="delete"
                    variant="danger"
                    @click="unlinkSupervisor(rel.id)"
                  />
                </div>
              </div>

              <div v-if="auth.isAdmin" class="flex-gap">
                <select
                  v-model="addSupervisorSelect[person.id]"
                  class="form-control"
                  style="max-width: 320px"
                >
                  <option value="">Ausbildner/in zum Zuweisen wählen...</option>
                  <option v-for="sup in supervisors" :key="sup.id" :value="sup.id">
                    {{ sup.full_name }} ({{ sup.job_title }})
                  </option>
                </select>
                <EditButton
                  label="Ausbildner/in zuweisen"
                  icon="plus"
                  variant="primary"
                  @click="linkSupervisor(person.id)"
                />
              </div>
            </div>

            <PersonDocuments
              v-if="person.id === auth.user?.id || person.is_subordinate"
              :person-id="person.id"
              :can-edit="Boolean(person.is_subordinate && auth.isTrainer)"
              role="lernender"
            />
          </template>
        </div>
      </div>
    </div>

    <!-- Modal: Create New User -->
    <ModalDialog
      :show="showUserModal"
      :title="createUserTitle"
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
              :placeholder="`vorname.nachname@${auth.user?.company_domain || 'firma.ch'}`"
              required
            />
            <small class="text-muted">
              Muss auf @{{ auth.user?.company_domain || 'firma.ch' }} enden.
            </small>
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
          <input
            v-model="newPassword"
            type="password"
            class="form-control"
            minlength="8"
            autocomplete="new-password"
            required
          />
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
  border: 1px solid var(--color-primary-border);
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

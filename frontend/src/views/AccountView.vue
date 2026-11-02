<script setup>
import { ref, reactive, onMounted } from 'vue'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'
import EditButton from '../components/ui/EditButton.vue'

const auth = useAuthStore()

const message = ref('')
const error = ref('')
const editingContacts = ref(false)

const contactForm = reactive({
  private_address: '',
  private_email: '',
  private_phone: '',
  school_address: '',
  school_email: '',
  school_phone: '',
  company_address: '',
  company_email: '',
  company_phone: ''
})

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')

const selectedPhoto = ref(null)
const uploadingPhoto = ref(false)

function syncFromUser() {
  if (!auth.user) return
  contactForm.private_address = auth.user.private_address || ''
  contactForm.private_email = auth.user.private_email || ''
  contactForm.private_phone = auth.user.private_phone || ''
  contactForm.school_address = auth.user.school_address || ''
  contactForm.school_email = auth.user.school_email || ''
  contactForm.school_phone = auth.user.school_phone || ''
  contactForm.company_address = auth.user.company_address || ''
  contactForm.company_email = auth.user.company_email || ''
  contactForm.company_phone = auth.user.company_phone || ''
}

onMounted(syncFromUser)

function startEditContacts() {
  syncFromUser()
  error.value = ''
  message.value = ''
  editingContacts.value = true
}

function cancelEditContacts() {
  syncFromUser()
  editingContacts.value = false
}

async function saveContacts() {
  error.value = ''
  message.value = ''
  try {
    const updated = await apiFetch(`/api/user/${auth.user.id}`, {
      method: 'PUT',
      body: contactForm
    })
    auth.user = updated
    editingContacts.value = false
    message.value = 'Kontaktangaben wurden erfolgreich gespeichert.'
  } catch (e) {
    error.value = e.message
  }
}

async function changePassword() {
  error.value = ''
  message.value = ''
  if (newPassword.value !== confirmPassword.value) {
    error.value = 'Die neuen Passwörter stimmen nicht überein.'
    return
  }
  try {
    await apiFetch(`/api/user/${auth.user.id}`, {
      method: 'PUT',
      body: {
        current_password: currentPassword.value,
        new_password: newPassword.value
      }
    })
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    message.value = 'Das Passwort wurde erfolgreich geändert.'
  } catch (e) {
    error.value = e.message
  }
}

function onPhotoSelected(event) {
  selectedPhoto.value = event.target.files?.[0] || null
}

async function uploadProfilePhoto() {
  if (!selectedPhoto.value) return
  error.value = ''
  message.value = ''
  uploadingPhoto.value = true
  try {
    const fd = new FormData()
    fd.append('file', selectedPhoto.value)
    fd.append('name', `Profilbild ${auth.user.full_name}`)
    fd.append('type', 'profilbild')
    fd.append('owner', String(auth.user.id))
    fd.append('is_done', 'true')

    const doc = await apiFetch('/api/documents', {
      method: 'POST',
      body: fd
    })

    const updatedUser = await apiFetch(`/api/user/${auth.user.id}`, {
      method: 'PUT',
      body: { picture_document: doc.id }
    })
    auth.user = updatedUser
    selectedPhoto.value = null
    message.value = 'Profilfoto wurde erfolgreich aktualisiert.'
  } catch (e) {
    error.value = e.message
  } finally {
    uploadingPhoto.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">Account</h1>
        <p class="page-subtitle">
          Persönliche Einstellungen für {{ auth.user?.full_name }}
        </p>
      </div>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>
    <div v-if="message" class="alert alert-success">{{ message }}</div>

    <div class="grid-2">
      <!-- Profilfoto -->
      <div class="card">
        <h2>Profilfoto</h2>
        <div class="flex-gap" style="margin-bottom: var(--space-4)">
          <div class="photo-preview">
            <img
              v-if="auth.user?.picture_document"
              :src="`/api/documents/${auth.user.picture_document}/file`"
              alt="Profilfoto"
            />
            <span v-else>{{ auth.user?.name?.[0] }}{{ auth.user?.surname?.[0] }}</span>
          </div>
          <div class="text-muted">
            Das Foto wird als Dokument im Firmenordner unter
            <code>/data/documents/</code> abgelegt und mit Ihrem Profil verknüpft.
          </div>
        </div>

        <form @submit.prevent="uploadProfilePhoto">
          <div class="form-group">
            <label class="form-label">Neues Bild auswählen (PNG, JPG, WEBP)</label>
            <input
              type="file"
              accept=".png,.jpg,.jpeg,.webp"
              class="form-control"
              required
              @change="onPhotoSelected"
            />
          </div>
          <button type="submit" class="btn btn-primary" :disabled="uploadingPhoto">
            {{ uploadingPhoto ? 'Wird hochgeladen...' : 'Foto hochladen' }}
          </button>
        </form>
      </div>

      <!-- Passwort -->
      <div class="card">
        <h2>Passwort ändern</h2>
        <form @submit.prevent="changePassword">
          <div class="form-group">
            <label class="form-label">Aktuelles Passwort *</label>
            <input v-model="currentPassword" type="password" class="form-control" required />
          </div>
          <div class="form-group">
            <label class="form-label">Neues Passwort (mind. 8 Zeichen) *</label>
            <input
              v-model="newPassword"
              type="password"
              minlength="8"
              class="form-control"
              required
            />
          </div>
          <div class="form-group">
            <label class="form-label">Neues Passwort bestätigen *</label>
            <input
              v-model="confirmPassword"
              type="password"
              minlength="8"
              class="form-control"
              required
            />
          </div>
          <button type="submit" class="btn btn-primary">Passwort aktualisieren</button>
        </form>
      </div>
    </div>

    <!-- Kontaktangaben -->
    <div class="card">
      <div class="card-header">
        <h2>Kontaktangaben</h2>
        <EditButton
          v-if="!editingContacts"
          label="Kontaktangaben bearbeiten"
          @click="startEditContacts"
        />
      </div>

      <div v-if="!editingContacts" class="grid-3">
        <div>
          <h3>Privat</h3>
          <div class="detail-item">
            <div class="detail-label">Privatadresse</div>
            <div class="detail-value">{{ auth.user?.private_address || '–' }}</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Private E-Mail</div>
            <div class="detail-value">{{ auth.user?.private_email || '–' }}</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Privates Telefon / Mobile</div>
            <div class="detail-value">{{ auth.user?.private_phone || '–' }}</div>
          </div>
        </div>

        <div>
          <h3>Berufsfachschule</h3>
          <div class="detail-item">
            <div class="detail-label">Schulhaus & Adresse</div>
            <div class="detail-value">{{ auth.user?.school_address || '–' }}</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Schul-E-Mail</div>
            <div class="detail-value">{{ auth.user?.school_email || '–' }}</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Schul-Telefon</div>
            <div class="detail-value">{{ auth.user?.school_phone || '–' }}</div>
          </div>
        </div>

        <div>
          <h3>Lehrbetrieb ({{ auth.user?.company }})</h3>
          <div class="detail-item">
            <div class="detail-label">Arbeitsort / Adresse</div>
            <div class="detail-value">{{ auth.user?.company_address || '–' }}</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Firmen-E-Mail</div>
            <div class="detail-value">{{ auth.user?.company_email || '–' }}</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Firmen-Telefon</div>
            <div class="detail-value">{{ auth.user?.company_phone || '–' }}</div>
          </div>
        </div>
      </div>

      <form v-else @submit.prevent="saveContacts">
        <div class="grid-3">
          <div>
            <h3>Privat</h3>
            <div class="form-group">
              <label class="form-label">Privatadresse</label>
              <input v-model="contactForm.private_address" type="text" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Private E-Mail</label>
              <input v-model="contactForm.private_email" type="email" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Privates Telefon / Mobile</label>
              <input v-model="contactForm.private_phone" type="text" class="form-control" />
            </div>
          </div>

          <div>
            <h3>Berufsfachschule</h3>
            <div class="form-group">
              <label class="form-label">Schulhaus & Adresse</label>
              <input v-model="contactForm.school_address" type="text" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Schul-E-Mail</label>
              <input v-model="contactForm.school_email" type="email" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Schul-Telefon</label>
              <input v-model="contactForm.school_phone" type="text" class="form-control" />
            </div>
          </div>

          <div>
            <h3>Lehrbetrieb ({{ auth.user?.company }})</h3>
            <div class="form-group">
              <label class="form-label">Arbeitsort / Adresse</label>
              <input v-model="contactForm.company_address" type="text" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Firmen-E-Mail</label>
              <input
                v-model="contactForm.company_email"
                type="email"
                class="form-control"
                disabled
              />
            </div>
            <div class="form-group">
              <label class="form-label">Firmen-Telefon</label>
              <input v-model="contactForm.company_phone" type="text" class="form-control" />
            </div>
          </div>
        </div>

        <div class="flex-gap" style="margin-top: var(--space-4)">
          <button type="submit" class="btn btn-primary">Speichern</button>
          <button type="button" class="btn" @click="cancelEditContacts">Abbrechen</button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.card-header h2 {
  margin-bottom: 0;
}

.photo-preview {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: 700;
  overflow: hidden;
  border: 2px solid #f5c2c9;
  flex-shrink: 0;
}

.photo-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>

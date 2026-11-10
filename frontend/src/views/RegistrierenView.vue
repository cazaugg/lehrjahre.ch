<script setup>
import { computed, ref } from 'vue'
import { apiFetch } from '../api'
import BrandLogo from '../components/ui/BrandLogo.vue'

const name = ref('')
const surname = ref('')
const email = ref('')
const jobTitle = ref('')
const companyName = ref('')
const address = ref('')
const password = ref('')
const passwordRepeat = ref('')

const error = ref('')
const loading = ref(false)
const submitted = ref(false)
const submittedEmail = ref('')
const resendMessage = ref('')

// The claim is the e-mail domain: whoever controls the mailbox controls
// the (new) company domain. Public providers are blocked by the server.
const domain = computed(() => {
  const value = email.value.trim().toLowerCase()
  if (!value.includes('@')) return ''
  const candidate = value.split('@')[1]
  return /^[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(candidate) ? candidate : ''
})

const domainHint = ref('')

async function checkDomain() {
  domainHint.value = ''
  if (!domain.value) return
  try {
    const data = await apiFetch(`/api/company-signup/domain-check?domain=${encodeURIComponent(domain.value)}`)
    if (!data.valid) domainHint.value = `${data.domain}: keine gültige Domain`
    else if (!data.available) domainHint.value = `@${data.domain} ist bereits auf lehrjahre.ch registriert`
  } catch {
    // The hint is purely cosmetic; the server validates on submit again.
  }
}

async function submitRegistration() {
  error.value = ''
  domainHint.value = ''
  if (password.value !== passwordRepeat.value) {
    error.value = 'Die Passwörter stimmen nicht überein.'
    return
  }
  loading.value = true
  try {
    await apiFetch('/api/company-signup', {
      method: 'POST',
      body: {
        name: name.value,
        surname: surname.value,
        email: email.value.trim(),
        job_title: jobTitle.value,
        company_name: companyName.value,
        address: address.value,
        password: password.value
      }
    })
    submittedEmail.value = email.value.trim()
    submitted.value = true
  } catch (e) {
    domainHint.value = ''
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function resendMail() {
  resendMessage.value = ''
  try {
    const data = await apiFetch('/api/company-signup/resend', {
      method: 'POST',
      body: { email: (email.value || submittedEmail.value).trim() }
    })
    resendMessage.value = data.message
  } catch (e) {
    resendMessage.value = e.message
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card card">
      <div class="login-brand">
        <BrandLogo :size="48" />
        <div>
          <h1>Firma registrieren</h1>
          <p class="text-muted">Neue Firma auf lehrjahre.ch anlegen (Alpha)</p>
        </div>
      </div>

      <div v-if="submitted" class="signup-done">
        <div class="alert alert-success">
          Fast fertig! Wir haben eine Bestätigungs-E-Mail an
          <strong>{{ submittedEmail }}</strong> gesendet. Der Link ist 24
          Stunden gültig.
        </div>
        <p class="text-muted">
          Nach der Bestätigung wird Ihre Firma angelegt und Ihr Konto als
          Administrator aktiviert.
        </p>
        <form @submit.prevent="resendMail">
          <button type="submit" class="btn" :disabled="loading">
            E-Mail erneut senden
          </button>
          <div v-if="resendMessage" class="text-muted" style="margin-top: var(--space-2)">
            {{ resendMessage }}
          </div>
        </form>
      </div>

      <template v-else>
        <div v-if="error" class="alert alert-error">{{ error }}</div>

        <form @submit.prevent="submitRegistration">
          <div class="form-group">
            <label class="form-label" for="signup-email">Firmen-E-Mail-Adresse</label>
            <input
              id="signup-email"
              v-model="email"
              type="email"
              class="form-control"
              placeholder="vorname.nachname@firma.ch"
              required
              @blur="checkDomain"
            />
            <small v-if="domain && !domainHint" class="text-muted">
              Ihre Firma wird unter der Domain <strong>@{{ domain }}</strong> geführt.
              Alle künftigen Benutzer brauchen eine Adresse auf dieser Domain.
            </small>
            <small v-if="domainHint" class="domain-warn">{{ domainHint }}</small>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label" for="signup-name">Vorname</label>
              <input id="signup-name" v-model="name" type="text" class="form-control" required />
            </div>
            <div class="form-group">
              <label class="form-label" for="signup-surname">Nachname</label>
              <input id="signup-surname" v-model="surname" type="text" class="form-control" required />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label" for="signup-jobtitle">Beruf/Funktion</label>
            <input
              id="signup-jobtitle"
              v-model="jobTitle"
              type="text"
              class="form-control"
              placeholder="z.B. Berufsbildner, HR"
              required
            />
          </div>

          <div class="form-group">
            <label class="form-label" for="signup-company">Firmenname</label>
            <input id="signup-company" v-model="companyName" type="text" class="form-control" required />
          </div>

          <div class="form-group">
            <label class="form-label" for="signup-address">Firmenadresse <span class="text-muted">(optional)</span></label>
            <input id="signup-address" v-model="address" type="text" class="form-control" />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label" for="signup-password">Passwort <span class="text-muted">(mind. 8 Zeichen)</span></label>
              <input id="signup-password" v-model="password" type="password" class="form-control" minlength="8" required />
            </div>
            <div class="form-group">
              <label class="form-label" for="signup-password-repeat">Passwort wiederholen</label>
              <input id="signup-password-repeat" v-model="passwordRepeat" type="password" class="form-control" minlength="8" required />
            </div>
          </div>

          <button type="submit" class="btn btn-primary" style="width: 100%" :disabled="loading">
            {{ loading ? 'Registrierung läuft...' : 'Registrieren und E-Mail bestätigen' }}
          </button>
        </form>

        <p class="text-muted" style="margin-bottom: 0; margin-top: var(--space-4)">
          Haben Sie schon ein Konto?
          <router-link to="/login">Anmelden</router-link>
        </p>
      </template>

      <template v-if="!submitted && email">
        <form @submit.prevent="resendMail" class="resend-box">
          <div class="text-muted">
            Bestätigungs-E-Mail nicht erhalten?
            <button type="submit" class="btn btn-sm">Erneut senden</button>
          </div>
          <div v-if="resendMessage" class="text-muted" style="margin-top: var(--space-2)">
            {{ resendMessage }}
          </div>
        </form>
      </template>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
  background: radial-gradient(circle at top, #164e78 0%, #0b2236 70%);
}

.login-card {
  width: 100%;
  max-width: 520px;
  padding: var(--space-6);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
}

.login-brand h1 {
  margin: 0;
  font-size: 1.3rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.domain-warn {
  color: #b45309;
}

.resend-box {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

@media (max-width: 520px) {
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import BrandLogo from '../components/ui/BrandLogo.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const token = String(route.query.token || '')
const companyId = String(route.query.c || '')
const requiresToken = Boolean(token && companyId)

const password = ref('')
const passwordRepeat = ref('')
const state = ref(requiresToken ? 'form' : 'error') // 'form' | 'accepting' | 'done' | 'error'
const message = ref('')
const loading = ref(false)

async function submitPassword() {
  message.value = ''
  if (password.value !== passwordRepeat.value) {
    message.value = 'Die Passwörter stimmen nicht überein.'
    return
  }
  loading.value = true
  state.value = 'accepting'
  try {
    await auth.acceptInvite(token, password.value, companyId)
    state.value = 'done'
    setTimeout(() => router.push('/projekte'), 2500)
  } catch (e) {
    state.value = 'error'
    message.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card card">
      <div class="login-brand">
        <BrandLogo :size="48" />
        <div>
          <h1>Einladung annehmen</h1>
          <p class="text-muted">lehrjahre.ch</p>
        </div>
      </div>

      <template v-if="state === 'form'">
        <p class="text-muted">
          Legen Sie Ihr persönliches Passwort fest. Danach melden Sie sich
          mit Ihrer Firmen-E-Mail-Adresse an.
        </p>
        <form @submit.prevent="submitPassword">
          <div v-if="message" class="alert alert-error">{{ message }}</div>

          <div class="form-group">
            <label class="form-label" for="invite-password">Passwort <span class="text-muted">(mind. 8 Zeichen)</span></label>
            <input
              id="invite-password"
              v-model="password"
              type="password"
              class="form-control"
              minlength="8"
              autocomplete="new-password"
              required
            />
          </div>
          <div class="form-group">
            <label class="form-label" for="invite-password-repeat">Passwort wiederholen</label>
            <input
              id="invite-password-repeat"
              v-model="passwordRepeat"
              type="password"
              class="form-control"
              minlength="8"
              autocomplete="new-password"
              required
            />
          </div>

          <button type="submit" class="btn btn-primary" style="width: 100%" :disabled="loading">
            {{ loading ? 'Wird angenommen ...' : 'Passwort setzen und anmelden' }}
          </button>
        </form>
      </template>

      <div v-else-if="state === 'accepting'" class="alert">
        Einladung wird angenommen ...
      </div>

      <div v-else-if="state === 'done'" class="alert alert-success">
        Passwort gesetzt. Sie sind angemeldet. Weiterleitung läuft ...
      </div>

      <template v-else>
        <div class="alert alert-error">{{ message }}</div>
        <p class="text-muted">
          Der Einladungslink ist ungültig, bereits verwendet oder abgelaufen.
          Bitten Sie Ihre Verwaltung auf lehrjahre.ch, die Einladung erneut zu
          senden, oder wenden Sie sich an kontakt@lehrjahre.ch.
        </p>
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
  max-width: 460px;
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
</style>

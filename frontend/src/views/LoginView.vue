<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import BrandLogo from '../components/ui/BrandLogo.vue'

const auth = useAuthStore()
const router = useRouter()

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const showDemo = import.meta.env.DEV

async function submitLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    router.push('/projekte')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function fillDemo(demoEmail) {
  email.value = demoEmail
  password.value = 'Lehrjahre2026!'
}
</script>

<template>
  <div class="login-page">
    <div class="login-card card">
      <div class="login-brand">
        <BrandLogo :size="48" />
        <div>
          <h1>
            lehrjahre.ch
            <span class="badge badge-warning" title="Frühe Prototyp-Version">Alpha</span>
          </h1>
          <p class="text-muted">Digitale Lerndokumentation für MEM-Berufslehren in der Schweiz</p>
        </div>
      </div>

      <div v-if="error" class="alert alert-error">{{ error }}</div>

      <form @submit.prevent="submitLogin">
        <div class="form-group">
          <label class="form-label" for="login-email">E-Mail-Adresse (Firma, Schule oder Privat)</label>
          <input
            id="login-email"
            v-model="email"
            type="email"
            class="form-control"
            placeholder="vorname.nachname@firma.ch"
            required
          />
        </div>

        <div class="form-group">
          <label class="form-label" for="login-password">Passwort</label>
          <input
            id="login-password"
            v-model="password"
            type="password"
            class="form-control"
            placeholder="••••••••"
            required
          />
        </div>

        <button type="submit" class="btn btn-primary" style="width: 100%" :disabled="loading">
          {{ loading ? 'Anmeldung läuft...' : 'Anmelden' }}
        </button>
      </form>

      <div v-if="showDemo" class="demo-box">
        <div class="text-muted" style="margin-bottom: var(--space-2)">
          <strong>Schnellauswahl Demo-Zugänge:</strong>
        </div>
        <div class="flex-gap">
          <button
            type="button"
            class="btn btn-sm"
            @click="fillDemo('thomas.keller@vektorwerk.ch')"
          >
            Ausbildner (Berufsbildner)
          </button>
          <button
            type="button"
            class="btn btn-sm"
            @click="fillDemo('sandra.meier@vektorwerk.ch')"
          >
            Ausbildnerin (HR)
          </button>
          <button
            type="button"
            class="btn btn-sm"
            @click="fillDemo('lea.buchmann@vektorwerk.ch')"
          >
            Lernende (Konstrukteurin EFZ, 1. Lehrjahr)
          </button>
          <button
            type="button"
            class="btn btn-sm"
            @click="fillDemo('livia.kaelin@vektorwerk.ch')"
          >
            Lernende (Konstrukteurin EFZ, 3. Lehrjahr)
          </button>
        </div>
      </div>
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
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0;
  font-size: 1.4rem;
}

.login-brand p {
  margin: 2px 0 0 0;
}

.demo-box {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}
</style>

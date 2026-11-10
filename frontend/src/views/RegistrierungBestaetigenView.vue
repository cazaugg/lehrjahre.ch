<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import BrandLogo from '../components/ui/BrandLogo.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const state = ref('verifying') // 'verifying' | 'done' | 'error'
const message = ref('')

onMounted(async () => {
  const token = String(route.query.token || '')
  if (!token) {
    state.value = 'error'
    message.value = 'Kein Bestätigungslink übergeben.'
    return
  }
  try {
    await auth.verifyCompanySignup(token)
    state.value = 'done'
    setTimeout(() => router.push('/projekte'), 2500)
  } catch (e) {
    state.value = 'error'
    message.value = e.message
  }
})
</script>

<template>
  <div class="login-page">
    <div class="login-card card">
      <div class="login-brand">
        <BrandLogo :size="48" />
        <div>
          <h1>Registrierung bestätigen</h1>
          <p class="text-muted">lehrjahre.ch</p>
        </div>
      </div>

      <div v-if="state === 'verifying'" class="alert">
        Bestätigung läuft ...
      </div>

      <div v-else-if="state === 'done'" class="alert alert-success">
        E-Mail bestätigt. Ihre Firma wurde angelegt und Sie sind als
        Administrator angemeldet. Weiterleitung läuft ...
      </div>

      <template v-else>
        <div class="alert alert-error">{{ message }}</div>
        <p class="text-muted">
          Fordern Sie auf der
          <router-link to="/registrierung">Registrierungsseite</router-link>
          eine neue Bestätigungs-E-Mail an oder kontaktieren Sie uns unter
          kontakt@lehrjahre.ch.
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

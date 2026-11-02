<script setup>
import { useAuthStore } from './stores/auth'
import AppLayout from './components/ui/AppLayout.vue'

const auth = useAuthStore()
</script>

<template>
  <AppLayout v-if="auth.user">
    <router-view />
  </AppLayout>
  <router-view v-else />
</template>

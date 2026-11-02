<script setup>
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import BrandLogo from './BrandLogo.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const navItems = [
  {
    to: '/projekte',
    prefix: '/projekte',
    label: 'Projekte, Themen & Praktika'
  },
  {
    to: '/lerndokumentation/noten',
    prefix: '/lerndokumentation',
    label: 'Lerndokumentation',
    children: [
      { to: '/lerndokumentation/noten', label: 'Noten & Prüfungen' },
      { to: '/lerndokumentation/nachweise', label: 'Zeugnisse & Kursnachweise' },
      { to: '/lerndokumentation/gespraeche', label: 'Ausbildungsgespräche' },
      { to: '/lerndokumentation/lernjournal', label: 'Lernjournal' }
    ]
  },
  {
    to: '/wissen',
    prefix: '/wissen',
    label: 'Wissen & Notizen'
  },
  {
    to: '/personen',
    prefix: '/personen',
    label: 'Personen'
  },
  {
    to: '/account',
    prefix: '/account',
    label: 'Account'
  }
]

function isParentActive(item) {
  return route.path.startsWith(item.prefix)
}

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <BrandLogo :size="40" />
        <div>
          <div class="brand-title">
            <span>lehrjahre.ch</span>
            <span class="badge badge-warning" title="Frühe Prototyp-Version">Alpha</span>
          </div>
          <div class="brand-sub">MEM Lerndokumentation</div>
        </div>
      </div>

      <nav class="sidebar-nav">
        <div
          v-for="item in navItems"
          :key="item.prefix"
          class="nav-group"
        >
          <router-link
            :to="item.to"
            class="nav-link"
            :class="{
              active: isParentActive(item) && !item.children,
              'parent-active': isParentActive(item) && item.children
            }"
          >
            <span>{{ item.label }}</span>
            <span v-if="item.children" class="chevron">
              {{ isParentActive(item) ? '▾' : '▸' }}
            </span>
          </router-link>

          <div
            v-if="item.children && isParentActive(item)"
            class="sub-nav"
          >
            <router-link
              v-for="sub in item.children"
              :key="sub.to"
              :to="sub.to"
              class="sub-nav-link"
              :class="{ active: route.path === sub.to }"
            >
              {{ sub.label }}
            </router-link>
          </div>
        </div>
      </nav>

      <div v-if="auth.user" class="sidebar-footer">
        <div class="user-summary">
          <div class="user-name">{{ auth.user.full_name }}</div>
          <div class="user-role">{{ auth.user.job_title }}</div>
          <div class="user-company">{{ auth.user.company }}</div>
        </div>
        <button type="button" class="btn btn-sm logout-btn" @click="handleLogout">
          Abmelden
        </button>
      </div>
    </aside>

    <div class="main-area">
      <header class="topbar">
        <div class="topbar-info">
          <span class="badge" :class="auth.isTrainer ? 'badge-info' : 'badge-success'">
            {{ auth.isTrainer ? 'Ausbildner' : 'Lernende/r' }}
          </span>
          <span class="text-muted">{{ auth.user?.company }}</span>
        </div>
        <div class="text-muted">
          Angemeldet als <strong>{{ auth.user?.full_name }}</strong> ({{ auth.user?.job_title }})
        </div>
      </header>

      <main class="content-area">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: 265px 1fr;
  min-height: 100vh;
}

.sidebar {
  background: var(--color-sidebar);
  color: var(--color-sidebar-text);
  display: flex;
  flex-direction: column;
  padding: var(--space-5) var(--space-4);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding-bottom: var(--space-5);
  margin-bottom: var(--space-4);
  border-bottom: 1px solid #374151;
}

.brand-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-weight: 700;
  font-size: 1.1rem;
  color: #ffffff;
}

.brand-sub {
  font-size: 0.75rem;
  color: #9ca3af;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
}

.nav-group {
  display: flex;
  flex-direction: column;
}

.nav-link {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.65rem 0.85rem;
  border-radius: var(--radius-sm);
  color: #d1d5db;
  font-size: 0.92rem;
  font-weight: 500;
  transition: background 0.15s;
}

.nav-link:hover {
  background: var(--color-sidebar-hover);
  color: #ffffff;
}

.nav-link.active {
  background: var(--color-primary);
  color: #ffffff;
  font-weight: 600;
}

.nav-link.parent-active {
  background: #1f2937;
  color: #ffffff;
  font-weight: 600;
}

.chevron {
  font-size: 0.75rem;
  color: #9ca3af;
}

.sub-nav {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin: 0.25rem 0 0.4rem 0.85rem;
  padding-left: 0.65rem;
  border-left: 2px solid #374151;
}

.sub-nav-link {
  display: block;
  padding: 0.45rem 0.75rem;
  border-radius: var(--radius-sm);
  color: #9ca3af;
  font-size: 0.85rem;
  font-weight: 500;
  transition: all 0.15s ease;
}

.sub-nav-link:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.06);
}

.sub-nav-link.active {
  background: var(--color-primary);
  color: #ffffff;
  font-weight: 600;
}

.sidebar-footer {
  padding-top: var(--space-4);
  border-top: 1px solid #374151;
}

.user-summary {
  margin-bottom: var(--space-3);
}

.user-name {
  font-weight: 600;
  color: #ffffff;
  font-size: 0.9rem;
}

.user-role {
  font-size: 0.78rem;
  color: #9ca3af;
}

.user-company {
  font-size: 0.75rem;
  color: #6b7280;
}

.logout-btn {
  width: 100%;
  background: #1f2937;
  color: #f3f4f6;
  border-color: #374151;
}

.logout-btn:hover {
  background: #374151;
}

.main-area {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 0.75rem var(--space-6);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.topbar-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.content-area {
  padding: var(--space-6);
  max-width: 1360px;
  width: 100%;
  margin: 0 auto;
}

@media (max-width: 820px) {
  .app-shell {
    grid-template-columns: 1fr;
  }
}
</style>

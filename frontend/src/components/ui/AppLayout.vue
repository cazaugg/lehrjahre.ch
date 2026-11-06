<script setup>
import { useRouter, useRoute } from 'vue-router'
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { fallbackJobs, fetchLehrplanJobs } from '../../utils/lehrplanJobs'
import BrandLogo from './BrandLogo.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

// Sidebar children for the lehrplan jobs, fetched from the API and cached
// (falls back to the bundled list on error).
const lehrplanJobs = ref(fallbackJobs)
onMounted(async () => {
  const jobs = await fetchLehrplanJobs()
  if (Array.isArray(jobs) && jobs.length) {
    lehrplanJobs.value = jobs
  }
})

const baseNavItems = [
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
    to: '/lehrplan',
    prefix: '/lehrplan',
    label: 'Lehrplan'
  },
  {
    to: '/vorlagen',
    prefix: '/vorlagen',
    label: 'Vorlagen'
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

const navItems = computed(() =>
  baseNavItems.map((item) =>
    item.prefix === '/lehrplan'
      ? {
          ...item,
          children: lehrplanJobs.value.map((job) => ({
            to: `/lehrplan/${job.code}`,
            label: String(job.name).replace(/ (EFZ|EBA)$/, '')
          }))
        }
      : item
  )
)

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
      <router-link to="/" class="sidebar-brand" title="Zur Startseite">
        <BrandLogo :size="40" />
        <div>
          <div class="brand-title">
            <span>lehrjahre.ch</span>
            <span class="badge badge-warning" title="Frühe Prototyp-Version">Alpha</span>
          </div>
          <div class="brand-sub">MEM Lerndokumentation</div>
        </div>
      </router-link>

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
            {{ auth.isAdmin ? 'Administrator' : (auth.isTrainer ? 'Ausbildner' : 'Lernende/r') }}
          </span>
          <span class="text-muted">{{ auth.user?.company }}</span>
        </div>
        <div class="text-muted">
          Angemeldet als <strong>{{ auth.user?.full_name }}</strong> ({{ auth.user?.job_title }})
        </div>
      </header>

      <main class="content-area">
        <div class="content-inner">
          <slot />
        </div>
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
  border-bottom: 1px solid var(--color-sidebar-border);
  color: inherit;
  text-decoration: none;
}

.sidebar-brand:hover {
  opacity: 0.85;
  text-decoration: none;
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
  color: var(--color-sidebar-muted);
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
  color: var(--color-sidebar-text);
  font-size: 0.9rem;
  font-weight: 500;
  transition: all 0.15s ease;
  border-left: 3px solid transparent;
}

.nav-link:hover {
  background: var(--color-sidebar-hover);
  color: #ffffff;
  text-decoration: none;
}

.nav-link.active {
  background: var(--color-sidebar-active);
  color: #ffffff;
  font-weight: 600;
  border-left-color: var(--color-accent);
}

.nav-link.parent-active {
  background: var(--color-sidebar-hover);
  color: #ffffff;
  font-weight: 600;
}

.chevron {
  font-size: 0.75rem;
  color: var(--color-sidebar-muted);
}

.sub-nav {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin: 0.25rem 0 0.4rem 0.85rem;
  padding-left: 0.65rem;
  border-left: 2px solid var(--color-sidebar-border);
}

.sub-nav-link {
  display: block;
  padding: 0.45rem 0.75rem;
  border-radius: var(--radius-sm);
  color: var(--color-sidebar-muted);
  font-size: 0.84rem;
  font-weight: 500;
  transition: all 0.15s ease;
}

.sub-nav-link:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.07);
  text-decoration: none;
}

.sub-nav-link.active {
  background: var(--color-sidebar-active);
  color: #ffffff;
  font-weight: 600;
}

.sidebar-footer {
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-sidebar-border);
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
  color: var(--color-sidebar-muted);
}

.user-company {
  font-size: 0.75rem;
  color: #64748b;
}

.logout-btn {
  width: 100%;
  background: var(--color-sidebar-hover);
  color: #f8fafc;
  border-color: var(--color-sidebar-border);
}

.logout-btn:hover {
  background: var(--color-sidebar-active);
  border-color: #2c5a85;
  color: #ffffff;
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
  flex: 1;
  min-height: 0;
}

.content-inner {
  padding: var(--space-6);
  max-width: 1360px;
  width: 100%;
  margin: 0 auto;
}

/* Lock the desktop shell to the viewport; only the content panel scrolls. */
@media (min-width: 821px) {
  .app-shell {
    height: 100vh;
    height: 100dvh;
    min-height: 0;
    grid-template-rows: minmax(0, 1fr);
    overflow: hidden;
  }

  .sidebar {
    min-height: 0;
    overflow-y: auto;
  }

  .content-area {
    overflow-y: auto;
    scrollbar-gutter: stable;
  }

  .content-inner {
    height: 100%;
    container-type: size;
  }
}

@media (max-width: 820px) {
  .app-shell {
    grid-template-columns: 1fr;
  }
}
</style>

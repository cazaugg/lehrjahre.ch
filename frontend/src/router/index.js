import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import ProjekteView from '../views/ProjekteView.vue'
import LerndokumentationView from '../views/LerndokumentationView.vue'
import WissenView from '../views/WissenView.vue'
import PersonenView from '../views/PersonenView.vue'
import AccountView from '../views/AccountView.vue'

const routes = [
  { path: '/', redirect: '/projekte' },
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/projekte', name: 'projekte', component: ProjekteView },
  { path: '/lerndokumentation', redirect: '/lerndokumentation/noten' },
  {
    path: '/lerndokumentation/zeugnisse',
    redirect: '/lerndokumentation/nachweise'
  },
  {
    path: '/lerndokumentation/kursnachweise',
    redirect: '/lerndokumentation/nachweise'
  },
  {
    path: '/lerndokumentation/:section',
    name: 'lerndokumentation',
    component: LerndokumentationView
  },
  { path: '/wissen', name: 'wissen', component: WissenView },
  { path: '/personen', name: 'personen', component: PersonenView },
  { path: '/personen/:section', redirect: '/personen' },
  { path: '/account', name: 'account', component: AccountView },
  { path: '/account/:section', redirect: '/account' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.initialized) {
    await auth.fetchMe()
  }
  if (!to.meta.public && !auth.user) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.user) {
    return { name: 'projekte' }
  }
})

export default router

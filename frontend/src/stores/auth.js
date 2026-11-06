import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiFetch, setCsrfToken } from '../api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const initialized = ref(false)
  const memProfessions = ref([])
  const trainerFunctions = ref([])

  // Trainers can select which student's portfolio they are currently inspecting
  const selectedStudentId = ref(null)
  const companyStudents = ref([])

  // Supervisors (ausbildner and admin) share the same visibility rules; the
  // admin additionally manages people and relationships company-wide.
  const isTrainer = computed(() => ['ausbildner', 'admin'].includes(user.value?.role))
  const isStudent = computed(() => user.value?.role === 'lernender')
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isAdminOrHr = isTrainer

  function isSubordinate(studentId) {
    if (!isTrainer.value || !studentId) return false
    const id = Number(studentId)
    if (Array.isArray(user.value?.supervised_student_ids)) {
      return user.value.supervised_student_ids.includes(id)
    }
    return companyStudents.value.some((s) => s.id === id)
  }

  const activeStudentId = computed(() => {
    if (isStudent.value) return user.value?.id
    return selectedStudentId.value
  })

  const activeStudent = computed(() => {
    if (isStudent.value) return user.value
    return companyStudents.value.find((s) => s.id === selectedStudentId.value) || null
  })

  async function fetchMe() {
    try {
      const data = await apiFetch('/api/auth/me')
      user.value = data.user
      setCsrfToken(data.csrf_token)
      memProfessions.value = data.mem_professions || []
      trainerFunctions.value = data.trainer_functions || []

      if (isTrainer.value) {
        await loadCompanyStudents()
      } else if (user.value) {
        selectedStudentId.value = user.value.id
      }
    } catch {
      user.value = null
    } finally {
      initialized.value = true
    }
  }

  async function loadCompanyStudents() {
    if (!user.value) return
    try {
      const res = await apiFetch('/api/user?role=lernender&subordinate_only=true')
      companyStudents.value = res.users || []
      if (isTrainer.value) {
        user.value.supervised_student_ids = companyStudents.value.map((s) => s.id)
      }
      if (!selectedStudentId.value && companyStudents.value.length > 0) {
        selectedStudentId.value = companyStudents.value[0].id
      }
    } catch {
      companyStudents.value = []
    }
  }

  async function login(email, password) {
    const data = await apiFetch('/api/auth/login', {
      method: 'POST',
      body: { email, password }
    })
    user.value = data.user
    setCsrfToken(data.csrf_token)
    memProfessions.value = data.mem_professions || []
    trainerFunctions.value = data.trainer_functions || []

    if (isTrainer.value) {
      await loadCompanyStudents()
    } else {
      selectedStudentId.value = user.value.id
    }
  }

  async function logout() {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' })
    } finally {
      user.value = null
      selectedStudentId.value = null
      companyStudents.value = []
    }
  }

  return {
    user,
    initialized,
    memProfessions,
    trainerFunctions,
    selectedStudentId,
    companyStudents,
    isTrainer,
    isStudent,
    isAdmin,
    isAdminOrHr,
    isSubordinate,
    activeStudentId,
    activeStudent,
    fetchMe,
    loadCompanyStudents,
    login,
    logout
  }
})

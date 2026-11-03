<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiFetch } from '../api'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const projectId = computed(() => Number(route.params.id))

const project = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const successMsg = ref('')

// Global fields
const globalEvalText = ref('')
const isCompleted = ref(false)

// Selected student for per-student evaluation
const selectedStudentId = ref(null)
const isReleased = ref(false)

// Per-student form state
const projectEvalText = ref('')
const projectScoreType = ref('grade') // '' | 'grade' | 'percent'
const projectScoreValue = ref('')

const taskEvals = ref([]) // [{ task_id, title, eval_text, score_type, score_value }]
const goalEvals = ref([]) // [{ goal, eval_text }]

const availableStudents = computed(() => {
  if (!project.value) return []
  const assigned = project.value.assigned_student_users || []
  if (assigned.length > 0) return assigned
  return auth.companyStudents
})

async function loadProject() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiFetch(`/api/project/${projectId.value}`)
    project.value = data
    globalEvalText.value = data.global_eval_text || ''
    isCompleted.value = Boolean(data.is_completed)

    const students = availableStudents.value
    if (!selectedStudentId.value && students.length > 0) {
      selectedStudentId.value = students[0].id
    } else {
      hydrateStudentForm(selectedStudentId.value)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(loadProject)

watch(selectedStudentId, (sid) => {
  hydrateStudentForm(sid)
})

function hydrateStudentForm(sid) {
  if (!project.value || !sid) return
  const allEvals = (project.value.evaluations || []).filter(
    (e) => e.student === Number(sid)
  )

  const projEv = allEvals.find(
    (e) => e.project === project.value.id && e.target_type === 'project'
  )
  projectEvalText.value = projEv?.eval_text || ''
  projectScoreType.value = projEv?.score_type || 'grade'
  projectScoreValue.value =
    projEv?.score_value !== null && projEv?.score_value !== undefined
      ? String(projEv.score_value)
      : ''

  isReleased.value = allEvals.some((e) => e.is_released)

  taskEvals.value = (project.value.tasks || []).map((t) => {
    const tEv = allEvals.find(
      (e) => e.project === t.id && e.target_type === 'task'
    )
    return {
      task_id: t.id,
      title: t.title,
      eval_text: tEv?.eval_text || '',
      score_type: tEv?.score_type || 'grade',
      score_value:
        tEv?.score_value !== null && tEv?.score_value !== undefined
          ? String(tEv.score_value)
          : ''
    }
  })

  goalEvals.value = (project.value.goals || []).map((g) => {
    const gEv = allEvals.find(
      (e) =>
        e.project === project.value.id &&
        (e.target_type === 'goal' || !e.target_type) &&
        e.goal === g
    )
    return {
      goal: g,
      eval_text: gEv?.eval_text || ''
    }
  })
}

function submissionFor(targetProjId, studentId) {
  if (!project.value || !studentId) return null
  return (
    (project.value.participations || []).find(
      (p) => p.project === targetProjId && p.student === Number(studentId)
    ) || null
  )
}

async function saveEvaluation(closeProjectAfter = false) {
  error.value = ''
  successMsg.value = ''
  saving.value = true
  if (closeProjectAfter) {
    isCompleted.value = true
    isReleased.value = true
  }
  try {
    await apiFetch(`/api/evaluation/project/${projectId.value}`, {
      method: 'POST',
      body: {
        global_eval_text: globalEvalText.value,
        is_completed: isCompleted.value,
        student: selectedStudentId.value ? Number(selectedStudentId.value) : null,
        is_released: isReleased.value,
        project_eval: {
          eval_text: projectEvalText.value,
          score_type: projectScoreType.value || null,
          score_value:
            projectScoreValue.value !== '' ? Number(projectScoreValue.value) : null
        },
        task_evals: taskEvals.value.map((te) => ({
          task_id: te.task_id,
          eval_text: te.eval_text,
          score_type: te.score_type || null,
          score_value:
            te.score_value !== '' ? Number(te.score_value) : null
        })),
        goal_evals: goalEvals.value.map((ge) => ({
          goal: ge.goal,
          eval_text: ge.eval_text
        }))
      }
    })
    await loadProject()
    successMsg.value = closeProjectAfter
      ? 'Auswertung gespeichert und Projekt abgeschlossen.'
      : 'Auswertung erfolgreich gespeichert.'
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <div class="flex-gap" style="margin-bottom: 4px">
          <router-link :to="`/projekte/${projectId}`" class="btn btn-sm">
            ← Zur Projekt-Ansicht
          </router-link>
          <span class="badge badge-success">Auswertung (Berufsbildner/in)</span>
          <span v-if="project?.is_completed" class="badge badge-info">
            Projekt abgeschlossen
          </span>
        </div>
        <h1 class="page-title">
          Auswertung: {{ project?.title || '...' }}
        </h1>
        <p class="page-subtitle">
          Globales Fazit, Einzelauswertung pro Lernende/r (Projekt, Aufgaben, Ziele) und Projektabschluss
        </p>
      </div>

      <div class="flex-gap">
        <router-link :to="`/projekte/${projectId}/planung`" class="btn">
          Zur Planung
        </router-link>
      </div>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>
    <div v-if="successMsg" class="alert alert-success">{{ successMsg }}</div>

    <div v-if="loading" class="card">Lade Auswertung...</div>

    <form v-else-if="project" @submit.prevent="saveEvaluation(false)">
      <!-- 1. Auswertungstext global -->
      <div class="card">
        <div class="card-header">
          <div>
            <h3 style="margin: 0">1. Auswertungstext global</h3>
            <span class="text-muted">
              Übergreifende Rückmeldung zum gesamten Projekt (für alle zugewiesenen Lernenden sichtbar nach Freigabe/Abschluss)
            </span>
          </div>
        </div>

        <div class="form-group" style="margin-bottom: 0">
          <textarea
            v-model="globalEvalText"
            class="form-control"
            rows="4"
            placeholder="Allgemeines Fazit zum Projektverlauf..."
          />
        </div>
      </div>

      <!-- 2. Auswertung pro Student -->
      <div class="card">
        <div class="card-header">
          <div>
            <h3 style="margin: 0">2. Auswertung pro Lernende/r</h3>
            <span class="text-muted">
              Wählen Sie eine/n Lernende/n aus, um das Gesamtprojekt, die Aufgaben und die Ziele zu bewerten.
            </span>
          </div>
        </div>

        <div v-if="availableStudents.length === 0" class="text-muted">
          Keine Lernenden zugewiesen.
        </div>

        <div v-else>
          <!-- Student selector tabs -->
          <div class="tabs">
            <button
              v-for="stu in availableStudents"
              :key="stu.id"
              type="button"
              class="tab-btn"
              :class="{ active: selectedStudentId === stu.id }"
              @click="selectedStudentId = stu.id"
            >
              {{ stu.full_name }}
            </button>
          </div>

          <!-- 2a. Gesamtprojekt-Bewertung für diesen Lernenden -->
          <div class="eval-section-box">
            <h4 style="margin-bottom: var(--space-3)">
              Gesamtes Projekt – Beurteilung & Bewertung
            </h4>

            <!-- Show main project submission if project has no subtasks -->
            <div
              v-if="(project.tasks || []).length === 0"
              class="submission-preview"
            >
              <div class="detail-label">Abgabe des Lernenden (Hauptprojekt):</div>
              <div v-if="submissionFor(project.id, selectedStudentId)">
                <div class="flex-gap" style="margin-bottom: 4px">
                  <span
                    class="badge"
                    :class="
                      submissionFor(project.id, selectedStudentId).is_done
                        ? 'badge-success'
                        : 'badge-warning'
                    "
                  >
                    {{
                      submissionFor(project.id, selectedStudentId).is_done
                        ? 'Abgegeben'
                        : 'Entwurf'
                    }}
                  </span>
                  <a
                    v-if="submissionFor(project.id, selectedStudentId).document"
                    :href="`/api/documents/${submissionFor(project.id, selectedStudentId).document.id}/file`"
                    target="_blank"
                    rel="noopener"
                    class="btn btn-sm"
                  >
                    📄 {{ submissionFor(project.id, selectedStudentId).document.name }}
                  </a>
                </div>
                <p
                  v-if="submissionFor(project.id, selectedStudentId).text"
                  style="white-space: pre-line; margin: 0"
                >
                  {{ submissionFor(project.id, selectedStudentId).text }}
                </p>
              </div>
              <div v-else class="text-muted">Noch keine Abgabe eingereicht.</div>
            </div>

            <div class="grid-2">
              <div class="form-group" style="margin-bottom: 0">
                <label class="form-label">Auswertungstext fürs gesamte Projekt</label>
                <textarea
                  v-model="projectEvalText"
                  class="form-control"
                  rows="4"
                  placeholder="Gesamtbeurteilung für diese/n Lernende/n..."
                />
              </div>

              <div>
                <div class="form-group">
                  <label class="form-label">Bewertungsart (Gesamtprojekt)</label>
                  <select v-model="projectScoreType" class="form-control">
                    <option value="grade">Note (1.0 – 6.0)</option>
                    <option value="percent">Prozent (0 – 100 %)</option>
                  </select>
                </div>

                <div class="form-group" style="margin-bottom: 0">
                  <label class="form-label">
                    {{
                      projectScoreType === 'percent'
                        ? 'Prozentwert (0 – 100 %)'
                        : 'Note (1.0 – 6.0)'
                    }}
                  </label>
                  <input
                    v-model="projectScoreValue"
                    type="number"
                    class="form-control"
                    :min="projectScoreType === 'percent' ? 0 : 1"
                    :max="projectScoreType === 'percent' ? 100 : 6"
                    :step="projectScoreType === 'percent' ? 1 : 0.1"
                    :placeholder="projectScoreType === 'percent' ? 'z.B. 85' : 'z.B. 5.2'"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- 2b. Auswertung pro Aufgabe -->
          <div v-if="taskEvals.length > 0" class="eval-section-box">
            <h4 style="margin-bottom: var(--space-3)">
              Auswertung pro Aufgabe ({{ taskEvals.length }})
            </h4>

            <div
              v-for="te in taskEvals"
              :key="te.task_id"
              class="sub-eval-item"
            >
              <div class="flex-between" style="margin-bottom: var(--space-2)">
                <strong>{{ te.title }}</strong>
                <div v-if="submissionFor(te.task_id, selectedStudentId)" class="flex-gap">
                  <span
                    class="badge"
                    :class="
                      submissionFor(te.task_id, selectedStudentId).is_done
                        ? 'badge-success'
                        : 'badge-warning'
                    "
                  >
                    {{
                      submissionFor(te.task_id, selectedStudentId).is_done
                        ? 'Abgegeben'
                        : 'Offen'
                    }}
                  </span>
                  <a
                    v-if="submissionFor(te.task_id, selectedStudentId).document"
                    :href="`/api/documents/${submissionFor(te.task_id, selectedStudentId).document.id}/file`"
                    target="_blank"
                    rel="noopener"
                    class="btn btn-sm"
                  >
                    📄 {{ submissionFor(te.task_id, selectedStudentId).document.name }}
                  </a>
                </div>
                <span v-else class="badge badge-neutral">Keine Abgabe</span>
              </div>

              <div
                v-if="submissionFor(te.task_id, selectedStudentId)?.text"
                class="submission-preview"
              >
                <div class="detail-label">Bericht des Lernenden:</div>
                <div style="white-space: pre-line">
                  {{ submissionFor(te.task_id, selectedStudentId).text }}
                </div>
              </div>

              <div class="grid-2">
                <div class="form-group" style="margin-bottom: 0">
                  <label class="form-label">Auswertungstext zur Aufgabe</label>
                  <textarea
                    v-model="te.eval_text"
                    class="form-control"
                    rows="3"
                    placeholder="Feedback zur Ausführung dieser Aufgabe..."
                  />
                </div>

                <div class="grid-2">
                  <div class="form-group" style="margin-bottom: 0">
                    <label class="form-label">Art</label>
                    <select v-model="te.score_type" class="form-control">
                      <option value="grade">Note (1–6)</option>
                      <option value="percent">Prozent (%)</option>
                    </select>
                  </div>
                  <div class="form-group" style="margin-bottom: 0">
                    <label class="form-label">
                      {{ te.score_type === 'percent' ? 'Prozent' : 'Note' }}
                    </label>
                    <input
                      v-model="te.score_value"
                      type="number"
                      class="form-control"
                      :min="te.score_type === 'percent' ? 0 : 1"
                      :max="te.score_type === 'percent' ? 100 : 6"
                      :step="te.score_type === 'percent' ? 1 : 0.1"
                      :placeholder="te.score_type === 'percent' ? '0–100' : '1.0–6.0'"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 2c. Auswertung pro Ziel -->
          <div v-if="goalEvals.length > 0" class="eval-section-box">
            <h4 style="margin-bottom: var(--space-3)">
              Auswertung pro Lernziel ({{ goalEvals.length }})
            </h4>

            <div
              v-for="(ge, idx) in goalEvals"
              :key="idx"
              class="sub-eval-item"
            >
              <div class="form-group" style="margin-bottom: 0">
                <label class="form-label">🎯 {{ ge.goal }}</label>
                <textarea
                  v-model="ge.eval_text"
                  class="form-control"
                  rows="2"
                  placeholder="Beurteilung der Zielerreichung..."
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. Bewertung freigeben & Projekt abschliessen -->
      <div class="card publish-bar">
        <div class="flex-column-gap">
          <label class="publish-toggle">
            <input v-model="isReleased" type="checkbox" />
            <div>
              <strong>Bewertung für diese/n Lernende/n freigeben</strong>
              <div class="text-muted">
                Macht die Auswertung für den ausgewählten Lernenden sichtbar.
              </div>
            </div>
          </label>

          <label class="publish-toggle">
            <input v-model="isCompleted" type="checkbox" />
            <div>
              <strong>Gesamtes Projekt abschliessen</strong>
              <div class="text-muted">
                Nach Abschluss sind Planung, Durchführung und Auswertung für Lernende endgültig im Read-Only-Modus sichtbar.
              </div>
            </div>
          </label>
        </div>

        <div class="flex-gap">
          <router-link :to="`/projekte/${projectId}`" class="btn">
            Zurück zur Ansicht
          </router-link>
          <button type="submit" class="btn btn-primary" :disabled="saving">
            {{ saving ? 'Speichert...' : 'Auswertung speichern' }}
          </button>
          <button
            v-if="!project.is_completed"
            type="button"
            class="btn btn-success-action"
            :disabled="saving"
            @click="saveEvaluation(true)"
          >
            Bewertung freigeben & Projekt abschliessen
          </button>
        </div>
      </div>
    </form>
  </div>
</template>

<style scoped>
.eval-section-box {
  padding: var(--space-4);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
}

.eval-section-box:last-child {
  margin-bottom: 0;
}

.sub-eval-item {
  padding: var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-3);
}

.sub-eval-item:last-child {
  margin-bottom: 0;
}

.submission-preview {
  padding: var(--space-3);
  background: var(--color-surface);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-3);
  font-size: 0.88rem;
}

.publish-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.flex-column-gap {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.publish-toggle {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  cursor: pointer;
}

.publish-toggle input {
  margin-top: 4px;
}

.btn-success-action {
  background: var(--color-success);
  color: #ffffff;
  border-color: var(--color-success);
}

.btn-success-action:hover:not(:disabled) {
  opacity: 0.92;
}
</style>

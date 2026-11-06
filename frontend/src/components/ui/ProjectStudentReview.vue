<script setup>
import { computed } from 'vue'
import DocumentViewer from './DocumentViewer.vue'
import LernzielLabel from './LernzielLabel.vue'

const props = defineProps({
  project: { type: Object, required: true },
  student: { type: Object, required: true }
})

const emit = defineEmits(['undo-release'])

const hasSubtasks = computed(() => (props.project.tasks || []).length > 0)

const submissionTargets = computed(() => {
  if (!props.project) return []
  if (hasSubtasks.value) {
    return props.project.tasks.map((task, idx) => ({
      ...task,
      indexLabel: `Aufgabe ${idx + 1}`
    }))
  }
  return [{ ...props.project, indexLabel: 'Projektabgabe' }]
})

function getParticipation(targetId) {
  return (
    (props.project.participations || []).find(
      (p) =>
        p.project === targetId && p.student === Number(props.student.id)
    ) || null
  )
}

const studentEvaluations = computed(() =>
  (props.project.evaluations || []).filter(
    (evaluation) => evaluation.student === Number(props.student.id)
  )
)

const overallEval = computed(() =>
  studentEvaluations.value.find(
    (evaluation) =>
      evaluation.project === props.project.id &&
      evaluation.target_type === 'project'
  )
)

function taskEvalFor(taskId) {
  return studentEvaluations.value.find(
    (evaluation) =>
      evaluation.project === taskId && evaluation.target_type === 'task'
  )
}

function goalEvalFor(goalText) {
  return studentEvaluations.value.find(
    (evaluation) =>
      evaluation.project === props.project.id &&
      (evaluation.target_type === 'goal' || !evaluation.target_type) &&
      evaluation.goal === goalText
  )
}

const hasVisibleEvaluation = computed(() =>
  Boolean(
    props.project.global_eval_text ||
      studentEvaluations.value.length > 0 ||
      props.project.is_completed
  )
)

function formatScore(evaluation) {
  if (
    !evaluation ||
    evaluation.score_value === null ||
    evaluation.score_value === undefined
  ) {
    return null
  }
  if (evaluation.score_type === 'percent') return `${evaluation.score_value} %`
  return `Note ${evaluation.score_value}`
}
</script>

<template>
  <div class="student-review">
    <section class="student-section">
      <div class="student-section-header">
        <div>
          <h2 class="section-heading">2. Durchführung & Abgabe</h2>
          <span class="text-muted">
            <template v-if="hasSubtasks">
              Pro zugeordneter Aufgabe wird ein Dokument eingereicht (Textdokument oder Datei).
            </template>
            <template v-else>
              Da dieses Projekt keine Unteraufgaben hat, wird eine einzelne Projektabgabe als Dokument eingereicht.
            </template>
          </span>
        </div>
      </div>

      <div class="submission-list">
        <div
          v-for="target in submissionTargets"
          :key="target.id"
          class="submission-box"
        >
          <div class="flex-between" style="margin-bottom: var(--space-3)">
            <div>
              <span class="badge badge-neutral" style="margin-right: 6px">
                {{ target.indexLabel }}
              </span>
              <strong>{{ target.title }}</strong>
            </div>

            <div>
              <span
                v-if="getParticipation(target.id)?.is_done"
                class="badge badge-success"
              >
                Abgegeben & gesperrt
              </span>
              <span v-else class="badge badge-warning">
                Offen / In Bearbeitung
              </span>
            </div>
          </div>

          <div v-if="!getParticipation(target.id)" class="text-muted">
            Noch keine Durchführung / Abgabe vorhanden.
          </div>
          <div v-else>
            <div v-if="getParticipation(target.id).text" class="detail-item">
              <div class="detail-label">Eingereichter Text</div>
              <div class="readonly-text-box" style="white-space: pre-line">
                {{ getParticipation(target.id).text }}
              </div>
            </div>

            <div
              v-if="getParticipation(target.id).document"
              class="detail-item"
            >
              <div class="detail-label">Eingereichtes Dokument</div>
              <div class="doc-link-bar">
                <DocumentViewer :document="getParticipation(target.id).document" />
              </div>
            </div>

            <div
              v-if="
                project.can_manage &&
                getParticipation(target.id).is_done &&
                !project.is_completed
              "
              style="margin-top: var(--space-3)"
            >
              <button
                type="button"
                class="btn btn-sm"
                @click="emit('undo-release', getParticipation(target.id))"
              >
                ↩ Freigabe rückgängig machen (Zur Bearbeitung öffnen)
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="student-section">
      <div class="student-section-header">
        <div>
          <h2 class="section-heading">3. Auswertung & Bewertung</h2>
          <span class="text-muted">
            Beurteilung durch den/die Berufsbildner/in (Schreibgeschützt)
          </span>
        </div>
      </div>

      <div v-if="!hasVisibleEvaluation" class="text-muted">
        Die Auswertung wurde noch nicht freigegeben.
      </div>

      <div v-else>
        <div v-if="project.global_eval_text" class="detail-item">
          <div class="detail-label">Auswertungstext global</div>
          <div class="readonly-text-box" style="white-space: pre-line">
            {{ project.global_eval_text }}
          </div>
        </div>

        <div v-if="overallEval" class="detail-item">
          <div class="flex-between" style="margin-bottom: 4px">
            <div class="detail-label">Beurteilung Gesamtprojekt</div>
            <span v-if="formatScore(overallEval)" class="badge badge-success">
              Bewertung Gesamtprojekt: {{ formatScore(overallEval) }}
            </span>
          </div>
          <div class="readonly-text-box" style="white-space: pre-line">
            {{ overallEval.eval_text || 'Keine Textbemerkung.' }}
          </div>
        </div>

        <div v-if="hasSubtasks" class="detail-item">
          <div class="detail-label" style="margin-bottom: 6px">
            Auswertung pro Aufgabe
          </div>
          <div class="task-overview-list">
            <div
              v-for="(task, idx) in project.tasks"
              :key="'eval-task-' + task.id"
              class="task-overview-item"
            >
              <div class="flex-between">
                <strong>Aufgabe {{ idx + 1 }}: {{ task.title }}</strong>
                <span
                  v-if="formatScore(taskEvalFor(task.id))"
                  class="badge badge-success"
                >
                  {{ formatScore(taskEvalFor(task.id)) }}
                </span>
              </div>
              <p
                style="white-space: pre-line; margin: 6px 0 0 0"
                :class="{ 'text-muted': !taskEvalFor(task.id)?.eval_text }"
              >
                {{
                  taskEvalFor(task.id)?.eval_text ||
                  'Noch keine Einzelbemerkung zu dieser Aufgabe.'
                }}
              </p>
            </div>
          </div>
        </div>

        <div v-if="(project.goals || []).length > 0" class="detail-item">
          <div class="detail-label" style="margin-bottom: 6px">
            Auswertung der Lernziele
          </div>
          <div class="task-overview-list">
            <div
              v-for="(goal, idx) in project.goals"
              :key="'eval-goal-' + idx"
              class="task-overview-item"
            >
              <strong><LernzielLabel icon :goal="goal" /></strong>
              <p
                style="white-space: pre-line; margin: 6px 0 0 0"
                :class="{ 'text-muted': !goalEvalFor(goal)?.eval_text }"
              >
                {{
                  goalEvalFor(goal)?.eval_text ||
                  'Noch keine Rückmeldung zu diesem Ziel.'
                }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.student-review {
  min-width: 0;
}

.student-section {
  margin-bottom: var(--space-5);
}

.student-section:last-child {
  margin-bottom: 0;
}

.student-section-header {
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-border);
}

.section-heading {
  margin: 0;
  font-size: 1.15rem;
}

.readonly-text-box {
  padding: var(--space-3);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.doc-link-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.task-overview-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: 4px;
}

.task-overview-item {
  padding: var(--space-3);
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.submission-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.submission-box {
  padding: var(--space-4);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}
</style>

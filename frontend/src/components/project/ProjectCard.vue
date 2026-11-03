<script setup>
import { computed, inject } from 'vue'
import EditButton from '../ui/EditButton.vue'
import MarkdownEditor from '../ui/MarkdownEditor.vue'

const props = defineProps({
  project: { type: Object, required: true },
  depth: { type: Number, default: 0 }
})

const ctx = inject('projectCtx')

const subprojects = computed(() => ctx.childrenOf(props.project.id))
const impls = computed(() => ctx.implementationsFor(props.project.id))
const evals = computed(() => ctx.evaluationsFor(props.project.id))
const goals = computed(() => props.project.goals || [])

// Phase status computation for the 3-step indicator
const phase1Done = computed(
  () => Boolean(props.project.description || goals.value.length > 0 || evals.value.some((e) => e.planning_text))
)
const phase2Active = computed(() => impls.value.length > 0)
const phase2Done = computed(
  () => impls.value.length > 0 && impls.value.every((i) => i.is_done)
)
const phase3Done = computed(
  () => evals.value.length > 0 && evals.value.every((e) => Boolean(e.eval_text))
)
const phase3Partial = computed(
  () => evals.value.some((e) => Boolean(e.eval_text)) && !phase3Done.value
)
</script>

<template>
  <div class="collapsible-card" :class="{ 'subproject-card': depth > 0 }">
    <!-- Collapsible Header with 3-Phase Stepper -->
    <div class="collapsible-header" @click="ctx.toggleExpand(project)">
      <div class="flex-gap">
        <span class="expand-indicator">{{ ctx.isExpanded(project) ? '▾' : '▸' }}</span>
        <div>
          <div class="flex-gap">
            <strong style="font-size: 1rem">{{ project.title }}</strong>
            <span v-if="depth > 0" class="badge badge-info">Teilprojekt</span>
          </div>
          <div class="text-muted" style="margin-top: 2px">
            Zeitraum: {{ ctx.formatDate(project.start_date) }} bis
            {{ ctx.formatDate(project.due_date) }}
            <span v-if="project.author_name"> · Berufsbildner/in: {{ project.author_name }}</span>
          </div>
        </div>
      </div>

      <!-- 3-Phase Stepper + Header Actions on Right -->
      <div class="flex-gap">
        <div class="phase-stepper" @click.stop="ctx.toggleExpand(project)">
          <div class="step-pill" :class="{ done: phase1Done }">
            <span class="step-num">1</span>
            <span>Planung ({{ goals.length }})</span>
          </div>
          <span class="step-arrow">→</span>
          <div
            class="step-pill"
            :class="{ done: phase2Done, active: phase2Active && !phase2Done }"
          >
            <span class="step-num">2</span>
            <span>Ausführung ({{ impls.length }})</span>
          </div>
          <span class="step-arrow">→</span>
          <div
            class="step-pill"
            :class="{ done: phase3Done, active: phase3Partial }"
          >
            <span class="step-num">3</span>
            <span>Bewertung ({{ evals.filter((e) => e.eval_text).length }}/{{ evals.length }})</span>
          </div>
        </div>

        <div v-if="ctx.auth.isTrainer" class="flex-gap">
          <EditButton
            label="Teilprojekt hinzufügen"
            icon="folder-plus"
            @click="ctx.openNewProject(project.id)"
          />
          <EditButton
            label="Projekt bearbeiten"
            icon="edit"
            @click="ctx.openEditProject(project)"
          />
          <EditButton
            label="Projekt löschen"
            icon="delete"
            variant="danger"
            @click="ctx.deleteProject(project)"
          />
        </div>
      </div>
    </div>

    <!-- Expanded Project Body: 3 Structured Phases -->
    <div v-if="ctx.isExpanded(project)" class="collapsible-body">
      <div class="phases-container">
        <!-- PHASE 1: Planung durch Berufsbildner/in -->
        <section class="phase-box phase-1">
          <div class="phase-header">
            <div class="flex-gap">
              <span class="phase-number">1</span>
              <div>
                <h4 class="phase-title">Phase 1: Planung & Auftrag (Berufsbildner/in)</h4>
                <div class="text-muted">
                  Projektbeschreibung, Lernziele und Planungsvorgaben des Berufsbildners
                </div>
              </div>
            </div>
            <div v-if="ctx.auth.isTrainer" class="flex-gap">
              <EditButton
                label="Zielplanung für Lernende/n hinzufügen"
                icon="plus"
                variant="primary"
                @click="ctx.openNewEval(project, '', 'planning')"
              />
            </div>
          </div>

          <div class="phase-content">
            <div class="planning-description">
              <div class="form-label">Auftrag & Beschreibung</div>
              <p style="white-space: pre-line; margin: 0">
                {{ project.description || 'Keine Beschreibung hinterlegt.' }}
              </p>
            </div>

            <!-- Defined Project Goals -->
            <div style="margin-top: var(--space-3)">
              <div class="form-label">Definierte Lernziele</div>
              <div v-if="goals.length === 0" class="text-muted">
                Keine allgemeinen Lernziele im Projekt hinterlegt.
              </div>
              <ul v-else class="goal-list">
                <li v-for="(g, idx) in goals" :key="idx" class="goal-item">
                  <span>🎯 {{ g }}</span>
                  <EditButton
                    v-if="ctx.auth.isTrainer"
                    label="Für Lernende/n planen"
                    icon="plus"
                    @click="ctx.openNewEval(project, g, 'planning')"
                  />
                </li>
              </ul>
            </div>

            <!-- Trainer's Specific Goal Planning per Student (eval.planning_text) -->
            <div v-if="evals.length > 0" style="margin-top: var(--space-3)">
              <div class="form-label">Geplante Ziele & Vorgaben pro Lernende/r (Berufsbildner/in)</div>
              <div v-for="ev in evals" :key="'plan-' + ev.id" class="item-row">
                <div>
                  <div class="flex-gap">
                    <strong>{{ ev.goal }}</strong>
                    <span class="badge badge-info">{{ ev.student_name }}</span>
                  </div>
                  <div class="text-muted" style="margin-top: 4px; white-space: pre-line">
                    <strong>Planungsvorgabe:</strong> {{ ev.planning_text || 'Keine spezifische Vorgabe notiert.' }}
                  </div>
                </div>
                <div v-if="ctx.auth.isTrainer" class="flex-gap">
                  <EditButton
                    label="Planung anpassen"
                    icon="edit"
                    @click="ctx.openEditEval(ev, 'planning')"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- PHASE 2: Ausführung durch Lernende/n -->
        <section class="phase-box phase-2">
          <div class="phase-header">
            <div class="flex-gap">
              <span class="phase-number">2</span>
              <div>
                <h4 class="phase-title">Phase 2: Ausführung & Arbeitsberichte (Lernende/r)</h4>
                <div class="text-muted">
                  Dokumentation der ausgeführten Arbeiten, Erkenntnisse und Fortschritte
                </div>
              </div>
            </div>
            <EditButton
              label="Arbeitsbericht erfassen"
              icon="plus"
              variant="primary"
              @click="ctx.openNewImpl(project)"
            />
          </div>

          <div class="phase-content">
            <div v-if="impls.length === 0" class="text-muted">
              Noch keine Arbeitsberichte für dieses Projekt erfasst.
            </div>
            <div v-else>
              <div v-for="item in impls" :key="item.id" class="item-row">
                <div style="flex: 1">
                  <div class="flex-gap">
                    <strong>{{ item.title }}</strong>
                    <span class="badge badge-info">{{ item.student_name }}</span>
                    <span
                      class="badge"
                      :class="item.is_done ? 'badge-success' : 'badge-warning'"
                    >
                      {{ item.is_done ? 'Abgeschlossen' : 'In Arbeit' }}
                    </span>
                  </div>
                  <div v-if="item.text" style="margin: 8px 0">
                    <MarkdownEditor :model-value="item.text" :readonly="true" />
                  </div>
                  <p v-else class="text-muted" style="margin: 6px 0 4px 0">
                    Kein Berichtstext vorhanden.
                  </p>
                  <div class="text-muted">
                    Lernende/r: {{ item.student_name }}
                    <span v-if="item.supervisor_name">
                      · Zuständig: {{ item.supervisor_name }}
                    </span>
                  </div>
                </div>

                <div class="flex-gap">
                  <EditButton
                    :label="item.is_done ? 'Wieder öffnen' : 'Als erledigt markieren'"
                    :icon="item.is_done ? 'undo' : 'check'"
                    :variant="item.is_done ? 'default' : 'success'"
                    @click="ctx.toggleImplDone(item)"
                  />
                  <EditButton
                    label="Arbeitsbericht bearbeiten"
                    icon="edit"
                    @click="ctx.openEditImpl(item)"
                  />
                  <EditButton
                    label="Arbeitsbericht löschen"
                    icon="delete"
                    variant="danger"
                    @click="ctx.deleteImpl(item)"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- PHASE 3: Bewertung durch Berufsbildner/in -->
        <section class="phase-box phase-3">
          <div class="phase-header">
            <div class="flex-gap">
              <span class="phase-number">3</span>
              <div>
                <h4 class="phase-title">Phase 3: Bewertung & Abschluss (Berufsbildner/in)</h4>
                <div class="text-muted">
                  Kompetenzbeurteilung und Rückmeldung zu den geplanten Lernzielen
                </div>
              </div>
            </div>
            <EditButton
              v-if="ctx.auth.isTrainer"
              label="Bewertung erfassen"
              icon="plus"
              variant="primary"
              @click="ctx.openNewEval(project, '', 'eval')"
            />
          </div>

          <div class="phase-content">
            <div v-if="evals.length === 0" class="text-muted">
              Noch keine Zielplanungen oder Bewertungen vorhanden.
            </div>
            <div v-else>
              <div
                v-for="ev in evals"
                :key="'eval-' + ev.id"
                class="item-row"
                :class="{ 'evaluated-row': Boolean(ev.eval_text) }"
              >
                <div style="flex: 1">
                  <div class="flex-gap">
                    <strong>{{ ev.goal }}</strong>
                    <span class="badge badge-info">{{ ev.student_name }}</span>
                    <span
                      class="badge"
                      :class="ev.eval_text ? 'badge-success' : 'badge-warning'"
                    >
                      {{ ev.eval_text ? 'Bewertet' : 'Bewertung ausstehend' }}
                    </span>
                  </div>

                  <div class="eval-comparison">
                    <div class="eval-col">
                      <span class="eval-label">1. Planungsvorgabe (Berufsbildner/in):</span>
                      <div>{{ ev.planning_text || '–' }}</div>
                    </div>
                    <div class="eval-col">
                      <span class="eval-label">3. Beurteilung / Feedback (Berufsbildner/in):</span>
                      <div :class="{ 'text-muted': !ev.eval_text }">
                        {{ ev.eval_text || 'Noch nicht bewertet.' }}
                      </div>
                    </div>
                  </div>

                  <div v-if="ev.supervisor_name" class="text-muted" style="margin-top: 4px">
                    Beurteilt durch: {{ ev.supervisor_name }}
                  </div>
                </div>

                <div v-if="ctx.auth.isTrainer" class="flex-gap">
                  <EditButton
                    :label="ev.eval_text ? 'Bewertung anpassen' : 'Jetzt bewerten'"
                    icon="edit"
                    variant="primary"
                    @click="ctx.openEditEval(ev, 'eval')"
                  />
                  <EditButton
                    label="Bewertung löschen"
                    icon="delete"
                    variant="danger"
                    @click="ctx.deleteEval(ev)"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- Optional Subprojects (Teilprojekte) -->
      <div
        v-if="subprojects.length > 0 || ctx.auth.isTrainer"
        class="subprojects-section"
      >
        <div class="flex-between" style="margin-bottom: var(--space-3)">
          <div>
            <h4 style="margin: 0">Teilprojekte ({{ subprojects.length }})</h4>
            <span class="text-muted">Untergeordnete Teilaufgaben oder Ausbildungsabschnitte</span>
          </div>
          <EditButton
            v-if="ctx.auth.isTrainer"
            label="Teilprojekt hinzufügen"
            icon="folder-plus"
            variant="primary"
            @click="ctx.openNewProject(project.id)"
          />
        </div>

        <div v-if="subprojects.length > 0">
          <ProjectCard
            v-for="sub in subprojects"
            :key="sub.id"
            :project="sub"
            :depth="depth + 1"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.subproject-card {
  border-left: 3px solid var(--color-primary);
  margin-top: var(--space-2);
}

/* 3-Phase Stepper in Header */
.phase-stepper {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.step-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 600;
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
}

.step-pill.active {
  background: var(--color-warning-bg);
  color: var(--color-warning);
  border-color: #fde68a;
}

.step-pill.done {
  background: var(--color-success-bg);
  color: var(--color-success);
  border-color: #bbf7d0;
}

.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 17px;
  height: 17px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.08);
  font-size: 0.7rem;
  font-weight: 700;
}

.step-arrow {
  color: var(--color-text-light);
  font-size: 0.75rem;
}

/* 3 Phase Boxes inside Expanded Project */
.phases-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.phase-box {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  overflow: hidden;
}

.phase-1 {
  border-left: 4px solid var(--color-primary);
}

.phase-2 {
  border-left: 4px solid var(--color-warning);
}

.phase-3 {
  border-left: 4px solid var(--color-success);
}

.phase-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: 0.75rem var(--space-4);
  background: var(--color-surface-muted);
  border-bottom: 1px solid var(--color-border);
}

.phase-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-weight: 700;
  font-size: 0.85rem;
  color: #ffffff;
  background: #374151;
  flex-shrink: 0;
}

.phase-1 .phase-number {
  background: var(--color-primary);
}

.phase-2 .phase-number {
  background: var(--color-warning);
}

.phase-3 .phase-number {
  background: var(--color-success);
}

.phase-title {
  margin: 0;
  font-size: 0.95rem;
}

.phase-content {
  padding: var(--space-4);
}

.planning-description {
  padding: var(--space-3);
  background: var(--color-surface-muted);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
}

.goal-list {
  list-style: none;
  padding: 0;
  margin: 0.35rem 0 0 0;
}

.goal-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  padding: 0.5rem 0.75rem;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  margin-bottom: 0.35rem;
  font-size: 0.88rem;
}

.item-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-2);
  background: var(--color-surface);
}

.item-row.evaluated-row {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.eval-comparison {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px dashed var(--color-border);
  font-size: 0.87rem;
}

.eval-col {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.eval-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-muted);
}

.subprojects-section {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}
</style>

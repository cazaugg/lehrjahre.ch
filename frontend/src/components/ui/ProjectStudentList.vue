<script setup>
import { getStudentCombinedStatus } from '../../utils/projectStatus'

const props = defineProps({
  project: { type: Object, required: true },
  students: { type: Array, default: () => [] },
  selectedStudentId: { type: [Number, String], default: null },
  title: { type: String, default: 'Lernende' },
  subtitle: {
    type: String,
    default: 'Abgabe und Auswertung pro Lernende/r'
  },
  emptyText: { type: String, default: 'Keine Lernenden zugewiesen.' }
})

const emit = defineEmits(['toggle'])

function combinedStatus(studentId) {
  return getStudentCombinedStatus(props.project, studentId)
}

function toggle(studentId) {
  emit('toggle', studentId)
}
</script>

<template>
  <div class="card project-student-list">
    <div class="card-header">
      <div>
        <h2 class="section-heading">{{ title }}</h2>
        <span class="text-muted">{{ subtitle }}</span>
      </div>
      <span class="text-muted">
        {{ students.length }}
        {{ students.length === 1 ? 'Lernende/r' : 'Lernende' }}
      </span>
    </div>

    <div v-if="students.length === 0" class="text-muted">
      {{ emptyText }}
    </div>

    <div v-else class="student-list">
      <div
        v-for="student in students"
        :key="student.id"
        class="student-list-item"
        :class="{ 'is-expanded': selectedStudentId === student.id }"
      >
        <div
          class="student-list-row"
          role="button"
          tabindex="0"
          @click="toggle(student.id)"
          @keydown.enter.prevent="toggle(student.id)"
          @keydown.space.prevent="toggle(student.id)"
        >
          <div class="flex-gap">
            <span class="expand-indicator">
              {{ selectedStudentId === student.id ? '▾' : '▸' }}
            </span>
            <div>
              <div class="flex-gap">
                <strong>{{ student.full_name }}</strong>
                <span class="text-muted">{{ student.job_title }}</span>
              </div>
            </div>
          </div>
          <span
            class="badge"
            :class="combinedStatus(student.id).variant"
          >
            {{ combinedStatus(student.id).label }}
          </span>
        </div>

        <div
          v-if="selectedStudentId === student.id"
          class="student-list-body"
        >
          <slot name="body" :student="student" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.section-heading {
  margin: 0;
  font-size: 1.15rem;
}

.student-list {
  display: flex;
  flex-direction: column;
}

.student-list-item {
  border-bottom: 1px solid var(--color-border);
}

.student-list-item:last-child {
  border-bottom: none;
}

.student-list-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  padding: 0.8rem var(--space-2);
  cursor: pointer;
  user-select: none;
}

.student-list-row:hover {
  background: var(--color-surface-muted);
}

.student-list-row:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.student-list-item.is-expanded .student-list-row {
  background: var(--color-primary-soft);
}

.student-list-body {
  padding: var(--space-4) var(--space-2) var(--space-3);
  border-top: 1px solid var(--color-border);
}
</style>

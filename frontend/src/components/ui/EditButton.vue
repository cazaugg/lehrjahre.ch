<script setup>
defineProps({
  label: { type: String, required: true }
})

defineEmits(['click'])
</script>

<template>
  <button
    type="button"
    class="icon-btn"
    :data-tooltip="label"
    :aria-label="label"
    @click="$emit('click')"
  >
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  </button>
</template>

<style scoped>
.icon-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.icon-btn:hover,
.icon-btn:focus-visible {
  color: var(--color-primary);
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  outline: none;
}

.icon-btn::after {
  content: attr(data-tooltip);
  position: absolute;
  right: calc(100% + 8px);
  top: 50%;
  transform: translateY(-50%);
  padding: 0.25rem 0.5rem;
  border-radius: var(--radius-sm);
  background: var(--color-text);
  color: #ffffff;
  font-size: 0.75rem;
  font-weight: 500;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  z-index: 20;
}

.icon-btn:hover::after,
.icon-btn:focus-visible::after {
  opacity: 1;
}
</style>

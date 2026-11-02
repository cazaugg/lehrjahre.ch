<script setup>
defineProps({
  size: {
    type: Number,
    default: 40
  }
})
</script>

<template>
  <span class="brand-logo" :style="{ width: `${size}px`, height: `${size}px` }">
    <img src="/lehrjahre-logo.jpg" alt="lehrjahre.ch Logo" />
  </span>
</template>

<style scoped>
.brand-logo {
  display: inline-flex;
  flex-shrink: 0;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: #ffffff;
}

.brand-logo img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>

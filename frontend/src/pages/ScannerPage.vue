<template>
  <ScanResults
    class="h-full overflow-hidden"
    @select-email="$emit('go-to-email', $event)"
  />
</template>

<script setup>
import ScanResults from '../components/ScanResults.vue'

defineEmits(['go-to-email'])
</script>

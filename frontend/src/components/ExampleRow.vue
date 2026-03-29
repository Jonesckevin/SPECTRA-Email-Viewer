<template>
  <button
    @click="$emit('click')"
    class="flex items-center gap-2 px-2 py-1 rounded hover:bg-blue-50 dark:hover:bg-blue-900/30 text-left w-full group"
  >
    <code class="text-xs bg-gray-100 dark:bg-gray-700 group-hover:bg-blue-100 dark:group-hover:bg-blue-800/40 px-2 py-0.5 rounded font-mono text-gray-700 dark:text-gray-300 flex-1 truncate">
      {{ example }}
    </code>
    <span v-if="label" class="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap hidden sm:inline">{{ label }}</span>
  </button>
</template>

<script setup>
defineProps({
  example: String,
  label: String,
})
defineEmits(['click'])
</script>

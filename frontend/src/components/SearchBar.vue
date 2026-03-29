<template>
  <div class="relative flex items-center gap-2">
    <div class="relative flex-1">
      <input
        ref="inputRef"
        type="text"
        :value="modelValue"
        @input="$emit('update:modelValue', $event.target.value)"
        @keydown.enter="$emit('search', modelValue)"
        placeholder="Search emails... (from: to: subject: has:attachment is:starred regex:/pattern/)"
        class="w-full pl-9 pr-20 py-1.5 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
      <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>

      <!-- Clear + Help buttons inside input -->
      <div class="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-1">
        <button
          v-if="modelValue"
          @click="$emit('clear')"
          class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          title="Clear search"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        <button
          @click="showHelp = !showHelp"
          class="px-1.5 py-0.5 text-xs font-bold text-blue-500 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded"
          title="Search help"
        >?</button>
      </div>
    </div>

    <button
      @click="$emit('search', modelValue)"
      class="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors shrink-0"
    >Search</button>

    <!-- Search help modal -->
    <SearchHelp v-if="showHelp" @close="showHelp = false" @insert="insertExample" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import SearchHelp from './SearchHelp.vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'search', 'clear'])

const inputRef = ref(null)
const showHelp = ref(false)

function insertExample(text) {
  emit('update:modelValue', text)
  showHelp.value = false
  inputRef.value?.focus()
}
</script>

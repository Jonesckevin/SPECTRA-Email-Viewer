<template>
  <div class="flex flex-col h-full">
    <!-- List header -->
    <div class="px-3 py-2 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800">
      <span>{{ total }} email{{ total !== 1 ? 's' : '' }}</span>
      <span v-if="totalPages > 1">Page {{ page }} of {{ totalPages }}</span>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading && emails.length === 0" class="flex-1 overflow-y-auto">
      <div v-for="i in 8" :key="i" class="px-3 py-3 border-b border-gray-100 dark:border-gray-800 animate-pulse">
        <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-2"></div>
        <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-2/3 mb-1"></div>
        <div class="h-2 bg-gray-100 dark:bg-gray-800 rounded w-1/4"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!loading && emails.length === 0" class="flex-1 flex items-center justify-center text-gray-400 dark:text-gray-600">
      <div class="text-center">
        <div class="text-4xl mb-2">📭</div>
        <p>No emails found</p>
      </div>
    </div>

    <!-- Email list -->
    <div v-else class="flex-1 overflow-y-auto">
      <div
        v-for="em in emails"
        :key="em.id"
        @click="$emit('select', em)"
        :class="[
          'px-3 py-2.5 border-b border-gray-100 dark:border-gray-800 cursor-pointer transition-colors',
          em.id === selectedId ? 'bg-blue-50 dark:bg-blue-900/20 border-l-2 border-l-blue-500' : 'hover:bg-gray-50 dark:hover:bg-gray-800 border-l-2 border-l-transparent',
        ]"
      >
        <div class="flex items-start gap-2">
          <!-- Star button -->
          <button
            @click.stop="$emit('toggle-star', em)"
            :class="['text-lg leading-none mt-0.5 shrink-0', em.is_starred ? 'text-yellow-400' : 'text-gray-300 dark:text-gray-600 hover:text-yellow-300']"
            :title="em.is_starred ? 'Unstar' : 'Star'"
          >{{ em.is_starred ? '★' : '☆' }}</button>

          <div class="flex-1 min-w-0">
            <!-- Sender + Date -->
            <div class="flex items-center justify-between gap-2 mb-0.5">
              <span class="font-medium text-sm text-gray-800 dark:text-gray-200 truncate">
                {{ em.sender_name || em.sender || '(unknown sender)' }}
              </span>
              <span class="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap shrink-0">{{ formatDate(em.date) }}</span>
            </div>

            <!-- Subject -->
            <div class="text-sm text-gray-700 dark:text-gray-300 truncate" v-html="em.subject_highlight || em.subject || '(no subject)'"></div>

            <!-- Indicators -->
            <div class="flex items-center gap-2 mt-0.5">
              <span v-if="em.has_attachments" class="text-xs text-gray-400 dark:text-gray-500" title="Has attachments">📎</span>
              <span class="text-xs text-gray-400 dark:text-gray-500 truncate">{{ em.recipients }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="px-3 py-2 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between bg-gray-50 dark:bg-gray-800">
      <button
        @click="$emit('page-change', page - 1)"
        :disabled="page <= 1"
        class="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
      >← Prev</button>
      <div class="flex items-center gap-1">
        <button
          v-for="p in visiblePages"
          :key="p"
          @click="$emit('page-change', p)"
          :class="[
            'w-7 h-7 text-xs rounded',
            p === page ? 'bg-blue-600 text-white' : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300'
          ]"
        >{{ p }}</button>
      </div>
      <button
        @click="$emit('page-change', page + 1)"
        :disabled="page >= totalPages"
        class="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
      >Next →</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  emails: { type: Array, default: () => [] },
  selectedId: { type: Number, default: null },
  loading: Boolean,
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  perPage: { type: Number, default: 50 },
})

defineEmits(['select', 'toggle-star', 'page-change'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.perPage)))

const visiblePages = computed(() => {
  const pages = []
  const start = Math.max(1, props.page - 2)
  const end = Math.min(totalPages.value, props.page + 2)
  for (let i = start; i <= end; i++) pages.push(i)
  return pages
})

function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    const now = new Date()
    if (d.toDateString() === now.toDateString()) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    if (d.getFullYear() === now.getFullYear()) {
      return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
    }
    return d.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return dateStr
  }
}
</script>

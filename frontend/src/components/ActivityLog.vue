<template>
  <div class="h-full overflow-y-auto bg-gray-50 dark:bg-gray-950 p-6">
    <div class="max-w-5xl mx-auto">
      <!-- Header -->
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-gray-800 dark:text-gray-200">📋 Activity Log</h2>
          <p class="text-sm text-gray-500 dark:text-gray-400">Real-time server activity and event history</p>
        </div>
        <div class="flex items-center gap-3">
          <!-- Live indicator -->
          <div class="flex items-center gap-1.5">
            <span
              class="w-2 h-2 rounded-full"
              :class="connected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'"
            ></span>
            <span class="text-xs text-gray-500 dark:text-gray-400">{{ connected ? 'Live' : 'Disconnected' }}</span>
          </div>

          <!-- Filters -->
          <select
            v-model="filterLevel"
            class="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 rounded text-gray-700 dark:text-gray-300"
          >
            <option value="">All levels</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>

          <select
            v-model="filterCategory"
            class="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 rounded text-gray-700 dark:text-gray-300"
          >
            <option value="">All categories</option>
            <option value="import">Import</option>
            <option value="scan">Scan</option>
            <option value="project">Project</option>
            <option value="export">Export</option>
            <option value="system">System</option>
          </select>

          <button
            @click="clearLogs"
            class="px-3 py-1 text-xs font-medium rounded border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >Clear</button>
        </div>
      </div>

      <!-- Log entries -->
      <div class="space-y-1">
        <div
          v-for="entry in filteredEntries"
          :key="entry.id"
          class="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 px-4 py-2 flex items-start gap-3 text-sm"
        >
          <!-- Level badge -->
          <span
            class="shrink-0 w-2 h-2 rounded-full mt-1.5"
            :class="{
              'bg-blue-500': entry.level === 'info',
              'bg-yellow-500': entry.level === 'warning',
              'bg-red-500': entry.level === 'error',
              'bg-gray-400': !entry.level || entry.level === 'debug',
            }"
          ></span>

          <!-- Timestamp -->
          <span class="shrink-0 text-xs text-gray-400 dark:text-gray-500 font-mono w-20 mt-0.5">
            {{ formatTime(entry.timestamp) }}
          </span>

          <!-- Category -->
          <span
            v-if="entry.category"
            class="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded uppercase"
            :class="categoryClass(entry.category)"
          >{{ entry.category }}</span>

          <!-- Message -->
          <span class="flex-1 text-gray-700 dark:text-gray-300">{{ entry.message }}</span>

          <!-- Project badge -->
          <span
            v-if="entry.project"
            class="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400"
          >{{ entry.project }}</span>
        </div>
      </div>

      <!-- Empty state -->
      <div v-if="!loading && filteredEntries.length === 0" class="text-center py-16">
        <div class="text-5xl mb-4">📋</div>
        <p class="text-lg text-gray-500 dark:text-gray-400">No activity logs yet</p>
        <p class="text-sm text-gray-400 dark:text-gray-500 mt-1">Import emails or run a scan to see activity here</p>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="text-center py-8 text-gray-500 dark:text-gray-400">Loading logs...</div>

      <!-- Load more -->
      <div v-if="hasMore && !loading" class="text-center py-4">
        <button
          @click="loadMore"
          class="px-4 py-2 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 font-medium"
        >Load more...</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchActivityLogs, clearActivityLogs, createActivityStream } from '../api.js'

const entries = ref([])
const loading = ref(true)
const connected = ref(false)
const filterLevel = ref('')
const filterCategory = ref('')
const hasMore = ref(false)
let eventSource = null

const filteredEntries = computed(() => {
  return entries.value.filter(e => {
    if (filterLevel.value && e.level !== filterLevel.value) return false
    if (filterCategory.value && e.category !== filterCategory.value) return false
    return true
  })
})

function categoryClass(cat) {
  const map = {
    import: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300',
    scan: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300',
    project: 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300',
    export: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300',
    system: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300',
  }
  return map[cat] || map.system
}

function formatTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return ts }
}

async function load() {
  loading.value = true
  try {
    const data = await fetchActivityLogs({ limit: 100 })
    entries.value = data.logs || data
    hasMore.value = (data.logs || data).length >= 100
  } catch (e) {
    entries.value = []
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  const oldest = entries.value[entries.value.length - 1]
  if (!oldest) return
  try {
    const data = await fetchActivityLogs({ limit: 100, offset: entries.value.length })
    const newLogs = data.logs || data
    entries.value.push(...newLogs)
    hasMore.value = newLogs.length >= 100
  } catch (e) { /* ignore */ }
}

async function clearLogs() {
  if (!confirm('Clear all activity logs?')) return
  try {
    await clearActivityLogs()
    entries.value = []
  } catch (e) {
    alert('Failed to clear logs: ' + e.message)
  }
}

function startSSE() {
  try {
    eventSource = createActivityStream()
    eventSource.onopen = () => { connected.value = true }
    eventSource.onmessage = (event) => {
      try {
        const entry = JSON.parse(event.data)
        if (entry.type === 'keepalive') return
        entries.value.unshift(entry)
        // Keep max 500 entries in memory
        if (entries.value.length > 500) entries.value.length = 500
      } catch { /* ignore parse errors */ }
    }
    eventSource.onerror = () => {
      connected.value = false
      // Auto-reconnect handled by EventSource
    }
  } catch (e) {
    connected.value = false
  }
}

onMounted(async () => {
  await load()
  startSSE()
})

onUnmounted(() => {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
})
</script>

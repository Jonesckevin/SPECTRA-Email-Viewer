<template>
  <div class="h-full overflow-y-auto bg-gray-50 dark:bg-gray-950 p-6">
    <div class="max-w-4xl mx-auto">

      <!-- Header -->
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-gray-800 dark:text-gray-200">🔍 Suspicious Email Scanner</h2>
          <p class="text-sm text-gray-500 dark:text-gray-400">Scan all emails for suspicious indicators</p>
        </div>
        <div class="flex items-center gap-2">
          <button
            v-if="scanning"
            @click="doStopScan"
            :disabled="stopping"
            class="px-4 py-2 bg-gray-700 text-white rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {{ stopping ? 'Stopping…' : '⏹ Stop Scan' }}
          </button>
          <button
            @click="doStartScan"
            :disabled="scanning"
            class="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {{ scanning ? 'Scanning…' : scanDone ? 'Scan Again' : '🛡 Start Scan' }}
          </button>
        </div>
      </div>

      <!-- YARA Rules section -->
      <div class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-4">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-sm font-medium text-gray-700 dark:text-gray-300">🧬 YARA Rules</h3>
          <div class="flex items-center gap-2">
            <span v-if="yaraStatus" class="text-xs text-gray-500 dark:text-gray-400">
              {{ yaraStatus.available ? `${yaraStatus.rules_count} rule(s) loaded` : 'YARA not available' }}
            </span>
            <label class="px-3 py-1 text-xs font-medium rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50 cursor-pointer transition-colors">
              Upload .yar
              <input type="file" accept=".yar,.yara,.txt" @change="handleYaraUpload" class="hidden" />
            </label>
            <button
              v-if="yaraStatus?.rules_count"
              @click="handleClearYara"
              class="px-3 py-1 text-xs font-medium rounded bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors"
            >Clear Rules</button>
          </div>
        </div>
        <p class="text-xs text-gray-400 dark:text-gray-500">Upload YARA rules to include custom pattern matching in scans. Rules are applied to email headers, body, and metadata.</p>
      </div>

      <!-- Progress bar -->
      <div v-if="scanning || scanDone" class="mb-4">
        <div class="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
          <span>{{ statusInfo.processed || scannedCount }} / {{ statusInfo.total || totalEmails }} emails scanned</span>
          <span>{{ allFlagged.length }} flagged</span>
        </div>
        <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
          <div
            class="bg-red-500 dark:bg-red-400 h-2 rounded-full transition-all duration-300"
            :style="{ width: progressPct + '%' }"
          ></div>
        </div>
      </div>

      <!-- Summary cards -->
      <div v-if="scanDone" class="grid grid-cols-3 gap-4 mb-6">
        <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{{ scannedCount }}</div>
          <div class="text-xs text-gray-500 dark:text-gray-400">Emails Scanned</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-red-200 dark:border-red-800">
          <div class="text-2xl font-bold text-red-600 dark:text-red-400">{{ allFlagged.length }}</div>
          <div class="text-xs text-gray-500 dark:text-gray-400">Flagged Emails</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-amber-200 dark:border-amber-800">
          <div class="text-2xl font-bold text-amber-600 dark:text-amber-400">{{ totalIndicators }}</div>
          <div class="text-xs text-gray-500 dark:text-gray-400">Total Indicators</div>
        </div>
      </div>

      <!-- Severity breakdown -->
      <div v-if="scanDone && allFlagged.length" class="flex gap-3 mb-4">
        <button
          v-for="sev in ['all', 'high', 'medium', 'low']"
          :key="sev"
          @click="filterSeverity = sev"
          class="px-3 py-1 rounded-full text-xs font-medium transition-colors"
          :class="filterSeverity === sev
            ? sevBtnActive[sev]
            : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'"
        >
          {{ sev === 'all' ? 'All' : sev.charAt(0).toUpperCase() + sev.slice(1) }}
          ({{ severityCounts[sev] || 0 }})
        </button>
      </div>

      <!-- Results list -->
      <div v-if="scanDone && filteredFlagged.length" class="space-y-3">
        <div
          v-for="item in filteredFlagged"
          :key="item.email_id"
          class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 hover:shadow-md transition-shadow cursor-pointer"
          @click="$emit('select-email', item.email_id)"
        >
          <div class="flex items-start justify-between mb-2">
            <div class="flex-1 min-w-0">
              <div class="font-medium text-gray-800 dark:text-gray-200 truncate">
                {{ item.subject }}
              </div>
              <div class="text-sm text-gray-500 dark:text-gray-400 truncate">
                {{ item.sender_name ? item.sender_name + ' — ' : '' }}{{ item.sender }}
              </div>
            </div>
            <div class="flex gap-1 ml-2 shrink-0">
              <span
                v-for="(count, sev) in itemSeverities(item)"
                :key="sev"
                class="text-[10px] font-bold px-1.5 py-0.5 rounded"
                :class="sevBadge[sev]"
              >{{ count }} {{ sev }}</span>
            </div>
          </div>

          <div class="space-y-1">
            <div
              v-for="(ind, i) in item.indicators"
              :key="i"
              class="flex items-start gap-2 text-xs"
            >
              <span
                class="shrink-0 w-2 h-2 rounded-full mt-1"
                :class="{
                  'bg-red-500': ind.severity === 'high',
                  'bg-amber-500': ind.severity === 'medium',
                  'bg-gray-400': ind.severity === 'low',
                }"
              ></span>
              <span class="text-gray-600 dark:text-gray-400">{{ ind.message }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="scanDone && !allFlagged.length" class="text-center py-16">
        <div class="text-5xl mb-4">✅</div>
        <p class="text-lg font-medium text-green-600 dark:text-green-400">No suspicious emails detected</p>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">All {{ scannedCount }} emails passed the scan</p>
      </div>

      <!-- Not started -->
      <div v-else-if="!scanning" class="text-center py-16">
        <div class="text-5xl mb-4">🛡</div>
        <p class="text-lg text-gray-500 dark:text-gray-400">Click "Start Scan" to analyze all emails</p>
        <p class="text-sm text-gray-400 dark:text-gray-500 mt-1">
          Checks for Reply-To mismatches, forged headers, suspicious senders, and more
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { startScan, stopScan, getScanStatus, getScanResults, getYaraStatus, uploadYaraRules, clearYaraRules, scanSuspicious } from '../api'

defineEmits(['select-email'])

const scanning = ref(false)
const scanDone = ref(false)
const scannedCount = ref(0)
const totalEmails = ref(0)
const allFlagged = ref([])
const filterSeverity = ref('all')
const statusInfo = ref({})
const yaraStatus = ref(null)
const stopping = ref(false)
let pollTimer = null

const sevBtnActive = {
  all: 'bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-900',
  high: 'bg-red-600 text-white',
  medium: 'bg-amber-500 text-white',
  low: 'bg-gray-500 text-white',
}

const sevBadge = {
  high: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300',
  medium: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300',
  low: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300',
}

const progressPct = computed(() => {
  const total = statusInfo.value.total || totalEmails.value
  const processed = statusInfo.value.processed || scannedCount.value
  return total ? Math.min((processed / total) * 100, 100) : 0
})

const totalIndicators = computed(() =>
  allFlagged.value.reduce((sum, f) => sum + f.indicators.length, 0)
)

const severityCounts = computed(() => {
  const counts = { all: allFlagged.value.length, high: 0, medium: 0, low: 0 }
  for (const f of allFlagged.value) {
    const sevs = new Set(f.indicators.map(i => i.severity))
    if (sevs.has('high')) counts.high++
    if (sevs.has('medium')) counts.medium++
    if (sevs.has('low')) counts.low++
  }
  return counts
})

const filteredFlagged = computed(() => {
  if (filterSeverity.value === 'all') return allFlagged.value
  return allFlagged.value.filter(f =>
    f.indicators.some(i => i.severity === filterSeverity.value)
  )
})

function itemSeverities(item) {
  const counts = {}
  for (const ind of item.indicators) {
    counts[ind.severity] = (counts[ind.severity] || 0) + 1
  }
  return counts
}

async function doStartScan() {
  scanning.value = true
  scanDone.value = false
  allFlagged.value = []
  scannedCount.value = 0

  try {
    // Try the new persistent scan API first
    await startScan()
    // Poll for status
    pollTimer = setInterval(async () => {
      try {
        const status = await getScanStatus()
        statusInfo.value = status
        scannedCount.value = status.processed || 0
        totalEmails.value = status.total || 0
        if (status.status === 'completed' || status.status === 'failed' || status.status === 'stopped') {
          clearInterval(pollTimer)
          pollTimer = null
          scanning.value = false
          stopping.value = false
          scanDone.value = true
          // Fetch results
          await loadResults()
        }
      } catch (e) {
        // Status endpoint may not exist, fall back
        clearInterval(pollTimer)
        pollTimer = null
        await fallbackScan()
      }
    }, 1000)
  } catch (e) {
    // Fall back to legacy page-by-page scan
    await fallbackScan()
  }
}

async function fallbackScan() {
  scanning.value = true
  allFlagged.value = []
  scannedCount.value = 0
  try {
    let page = 1
    while (true) {
      const result = await scanSuspicious(page, 200)
      totalEmails.value = result.total_emails
      scannedCount.value = Math.min(page * result.per_page, result.total_emails)
      allFlagged.value.push(...result.flagged)
      if (page >= result.total_pages) break
      page++
    }
  } catch (e) { /* partial results */ }
  scanning.value = false
  scanDone.value = true
}

async function doStopScan() {
  stopping.value = true
  try {
    await stopScan()
  } catch (e) {
    stopping.value = false
  }
}

async function loadResults() {
  try {
    const data = await getScanResults({ limit: 1000 })
    allFlagged.value = data.results || []
  } catch (e) { /* keep what we have */ }
}

async function loadYaraStatus() {
  try {
    yaraStatus.value = await getYaraStatus()
  } catch (e) {
    yaraStatus.value = { available: false, rules_count: 0 }
  }
}

async function handleYaraUpload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  try {
    await uploadYaraRules(file)
    await loadYaraStatus()
  } catch (e) {
    alert('Failed to upload YARA rules: ' + e.message)
  }
  event.target.value = ''
}

async function handleClearYara() {
  try {
    await clearYaraRules()
    await loadYaraStatus()
  } catch (e) {
    alert('Failed to clear YARA rules: ' + e.message)
  }
}

// On mount, check if there's a previous scan and load YARA status
onMounted(async () => {
  await loadYaraStatus()
  try {
    const status = await getScanStatus()
    if (status.status === 'completed' || status.status === 'stopped') {
      statusInfo.value = status
      scanDone.value = true
      scannedCount.value = status.processed || 0
      totalEmails.value = status.total || 0
      await loadResults()
    } else if (status.status === 'running') {
      scanning.value = true
      statusInfo.value = status
      // Resume polling
      pollTimer = setInterval(async () => {
        const s = await getScanStatus()
        statusInfo.value = s
        if (s.status === 'completed' || s.status === 'failed' || s.status === 'stopped') {
          clearInterval(pollTimer)
          pollTimer = null
          scanning.value = false
          stopping.value = false
          scanDone.value = true
          scannedCount.value = s.processed || 0
          totalEmails.value = s.total || 0
          await loadResults()
        }
      }, 1000)
    }
  } catch (e) { /* no previous scan */ }
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

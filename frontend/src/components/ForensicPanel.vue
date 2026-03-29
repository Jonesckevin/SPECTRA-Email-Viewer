<template>
  <div class="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
    <!-- Loading state -->
    <div v-if="loading" class="p-4 text-center text-gray-500 dark:text-gray-400 text-sm">
      Loading forensic analysis…
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="p-4 text-center text-red-500 dark:text-red-400 text-sm">
      {{ error }}
    </div>

    <!-- Forensic data -->
    <div v-else-if="data" class="text-sm">
      <!-- No forensic data banner -->
      <div v-if="!data.has_forensic_data" class="p-4 text-amber-600 dark:text-amber-400 text-center">
        ⚠ No raw header data available for this email. Forensic analysis is limited.
      </div>

      <!-- Tab bar -->
      <div class="flex border-b border-gray-200 dark:border-gray-700 overflow-x-auto">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="px-3 py-2 text-xs font-medium whitespace-nowrap border-b-2 transition-colors"
          :class="activeTab === tab.key
            ? 'border-blue-500 text-blue-600 dark:text-blue-400'
            : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
          <span
            v-if="tab.badge"
            class="ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold"
            :class="tab.badgeClass"
          >{{ tab.badge }}</span>
        </button>
      </div>

      <!-- Tab content -->
      <div class="max-h-72 overflow-y-auto">

        <!-- Metadata -->
        <div v-if="activeTab === 'metadata'" class="p-3 space-y-1">
          <div class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            <span class="text-gray-500 dark:text-gray-400 font-medium">Message-ID:</span>
            <span class="font-mono text-xs break-all">{{ data.metadata.message_id || '—' }}</span>
            <span class="text-gray-500 dark:text-gray-400 font-medium">Source file:</span>
            <span class="font-mono text-xs break-all">{{ data.metadata.file_source || '—' }}</span>
            <span class="text-gray-500 dark:text-gray-400 font-medium">Imported:</span>
            <span>{{ data.metadata.imported_at || '—' }}</span>
            <span class="text-gray-500 dark:text-gray-400 font-medium">Content hash:</span>
            <span class="font-mono text-xs break-all select-all">{{ data.metadata.content_hash || '—' }}</span>
          </div>
        </div>

        <!-- Hashes -->
        <div v-if="activeTab === 'hashes'" class="p-3 space-y-3">
          <div v-if="data.content_hashes.body_text && Object.keys(data.content_hashes.body_text).length">
            <h4 class="font-medium text-gray-600 dark:text-gray-300 mb-1">Body text</h4>
            <div v-for="(val, algo) in data.content_hashes.body_text" :key="algo" class="flex items-center gap-2 mb-0.5">
              <span class="text-gray-500 dark:text-gray-400 uppercase text-xs w-12">{{ algo }}:</span>
              <code class="font-mono text-xs break-all select-all flex-1">{{ val }}</code>
              <button @click="copy(val)" class="text-gray-400 hover:text-blue-500 text-xs" title="Copy">📋</button>
            </div>
          </div>
          <div v-if="data.content_hashes.body_html && Object.keys(data.content_hashes.body_html).length">
            <h4 class="font-medium text-gray-600 dark:text-gray-300 mb-1">Body HTML</h4>
            <div v-for="(val, algo) in data.content_hashes.body_html" :key="algo" class="flex items-center gap-2 mb-0.5">
              <span class="text-gray-500 dark:text-gray-400 uppercase text-xs w-12">{{ algo }}:</span>
              <code class="font-mono text-xs break-all select-all flex-1">{{ val }}</code>
              <button @click="copy(val)" class="text-gray-400 hover:text-blue-500 text-xs" title="Copy">📋</button>
            </div>
          </div>
          <div v-if="data.attachment_hashes.length">
            <h4 class="font-medium text-gray-600 dark:text-gray-300 mb-1">Attachments</h4>
            <div v-for="att in data.attachment_hashes" :key="att.id" class="mb-2">
              <div class="text-gray-700 dark:text-gray-300">📎 {{ att.filename }} <span class="text-gray-400">({{ att.content_type }})</span></div>
              <div v-if="att.hashes.sha256" class="flex items-center gap-2 ml-4">
                <span class="text-gray-500 dark:text-gray-400 uppercase text-xs w-12">SHA256:</span>
                <code class="font-mono text-xs break-all select-all flex-1">{{ att.hashes.sha256 }}</code>
                <button @click="copy(att.hashes.sha256)" class="text-gray-400 hover:text-blue-500 text-xs" title="Copy">📋</button>
              </div>
              <div v-if="att.hashes.error" class="ml-4 text-red-500 dark:text-red-400 text-xs">{{ att.hashes.error }}</div>
            </div>
          </div>
          <div v-if="!data.content_hashes.body_text || !Object.keys(data.content_hashes.body_text).length" class="text-gray-400 dark:text-gray-500">
            No hash data available.
          </div>
        </div>

        <!-- Received chain -->
        <div v-if="activeTab === 'received'" class="p-3">
          <div v-if="data.received_chain.length" class="space-y-2">
            <div
              v-for="hop in data.received_chain"
              :key="hop.hop_number"
              class="border border-gray-200 dark:border-gray-600 rounded p-2"
            >
              <div class="flex items-center gap-2 mb-1">
                <span class="bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded text-xs font-bold">
                  Hop {{ hop.hop_number }}
                </span>
                <span v-if="hop.delay_seconds !== null && hop.delay_seconds !== undefined"
                  class="text-xs px-1.5 py-0.5 rounded"
                  :class="hop.delay_seconds < 0
                    ? 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300'
                    : hop.delay_seconds > 3600
                      ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300'
                      : 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300'"
                >
                  {{ formatDelay(hop.delay_seconds) }}
                </span>
              </div>
              <div class="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-xs">
                <span class="text-gray-500 dark:text-gray-400">From:</span>
                <span class="font-mono break-all">{{ hop.from_server || '—' }}</span>
                <span class="text-gray-500 dark:text-gray-400">By:</span>
                <span class="font-mono break-all">{{ hop.by_server || '—' }}</span>
                <span v-if="hop.ip" class="text-gray-500 dark:text-gray-400">IP:</span>
                <span v-if="hop.ip" class="font-mono">{{ hop.ip }}</span>
                <span v-if="hop.protocol" class="text-gray-500 dark:text-gray-400">Proto:</span>
                <span v-if="hop.protocol" class="font-mono">{{ hop.protocol }}</span>
                <span class="text-gray-500 dark:text-gray-400">Time:</span>
                <span>{{ hop.timestamp || '—' }}</span>
              </div>
            </div>
          </div>
          <div v-else class="text-gray-400 dark:text-gray-500 text-center py-4">No received chain data.</div>
        </div>

        <!-- Authentication -->
        <div v-if="activeTab === 'auth'" class="p-3">
          <div class="space-y-2">
            <div v-for="(info, method) in data.authentication" :key="method" class="flex items-start gap-2">
              <span class="uppercase font-bold text-xs w-12">{{ method }}:</span>
              <span
                class="px-2 py-0.5 rounded text-xs font-bold"
                :class="authBadge(info.result)"
              >{{ info.result || 'none' }}</span>
              <span v-if="info.details" class="text-gray-500 dark:text-gray-400 text-xs">{{ info.details }}</span>
            </div>
            <div v-if="!data.authentication || !Object.keys(data.authentication).length" class="text-gray-400 dark:text-gray-500 text-center py-4">
              No authentication data available.
            </div>
          </div>
        </div>

        <!-- Suspicious indicators -->
        <div v-if="activeTab === 'suspicious'" class="p-3">
          <div v-if="data.suspicious_indicators.length" class="space-y-2">
            <div
              v-for="(ind, i) in data.suspicious_indicators"
              :key="i"
              class="flex items-start gap-2 p-2 rounded"
              :class="{
                'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800': ind.severity === 'high',
                'bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800': ind.severity === 'medium',
                'bg-gray-100 dark:bg-gray-700/40 border border-gray-200 dark:border-gray-600': ind.severity === 'low',
              }"
            >
              <span class="text-xs font-bold px-1.5 py-0.5 rounded shrink-0"
                :class="{
                  'bg-red-200 dark:bg-red-800 text-red-800 dark:text-red-200': ind.severity === 'high',
                  'bg-amber-200 dark:bg-amber-800 text-amber-800 dark:text-amber-200': ind.severity === 'medium',
                  'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300': ind.severity === 'low',
                }"
              >{{ ind.severity.toUpperCase() }}</span>
              <div>
                <div class="font-medium text-gray-800 dark:text-gray-200">{{ ind.message }}</div>
              </div>
            </div>
          </div>
          <div v-else class="text-center py-4">
            <span class="text-green-600 dark:text-green-400 font-medium">✓ No suspicious indicators detected</span>
          </div>
        </div>

        <!-- Raw headers -->
        <div v-if="activeTab === 'headers'" class="p-3">
          <pre v-if="data.raw_headers" class="font-mono text-xs whitespace-pre-wrap break-all text-gray-700 dark:text-gray-300 select-all bg-white dark:bg-gray-900 p-3 rounded border border-gray-200 dark:border-gray-600 max-h-60 overflow-y-auto">{{ data.raw_headers }}</pre>
          <div v-else class="text-gray-400 dark:text-gray-500 text-center py-4">No raw headers stored.</div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { fetchForensics } from '../api'

const props = defineProps({
  emailId: { type: Number, required: true },
  email: { type: Object, default: null },
})

const data = ref(null)
const loading = ref(false)
const error = ref('')
const activeTab = ref('metadata')

const tabs = computed(() => {
  const suspCount = data.value?.suspicious_indicators?.length || 0
  return [
    { key: 'metadata', label: '📋 Metadata' },
    { key: 'hashes', label: '🔑 Hashes' },
    { key: 'received', label: '🔗 Received Chain', badge: data.value?.received_chain?.length || null },
    { key: 'auth', label: '🛡 Auth' },
    {
      key: 'suspicious',
      label: '⚠ Suspicious',
      badge: suspCount || null,
      badgeClass: suspCount
        ? 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300'
        : '',
    },
    { key: 'headers', label: '📄 Raw Headers' },
  ]
})

async function load() {
  loading.value = true
  error.value = ''
  data.value = null
  try {
    data.value = await fetchForensics(props.emailId)
  } catch (e) {
    error.value = e.message || 'Failed to load forensic data'
  } finally {
    loading.value = false
  }
}

watch(() => props.emailId, load, { immediate: true })

function copy(text) {
  navigator.clipboard.writeText(text)
}

function formatDelay(seconds) {
  if (seconds === null || seconds === undefined) return ''
  if (seconds < 0) return `⚠ ${seconds}s (negative!)`
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`
  return `${(seconds / 86400).toFixed(1)}d`
}

function authBadge(result) {
  if (!result) return 'bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300'
  const r = result.toLowerCase()
  if (r === 'pass') return 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300'
  if (r === 'fail' || r === 'hardfail') return 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300'
  if (r === 'softfail') return 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300'
  return 'bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300'
}
</script>

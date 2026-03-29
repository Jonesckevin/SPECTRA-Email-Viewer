<template>
  <div class="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" @click.self="$emit('close')">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-lg mx-4">
      <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <h2 class="text-lg font-bold text-gray-800 dark:text-gray-100">Upload Email Files</h2>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl">&times;</button>
      </div>

      <!-- Active imports banner -->
      <div v-if="activeJobCount > 0" class="px-6 py-2 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-100 dark:border-blue-800 flex items-center gap-2">
        <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
        <span class="text-xs text-blue-700 dark:text-blue-300 font-medium">{{ activeJobCount }} import{{ activeJobCount > 1 ? 's' : '' }} in progress</span>
      </div>

      <!-- Tabs -->
      <div class="flex border-b border-gray-200 dark:border-gray-700 px-6">
        <button
          @click="activeTab = 'upload'"
          :class="[
            'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
            activeTab === 'upload'
              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          ]"
        >Upload New</button>
        <button
          @click="activeTab = 'existing'; loadFiles()"
          :class="[
            'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
            activeTab === 'existing'
              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          ]"
        >Existing Files</button>
      </div>

      <div class="px-6 py-4">
        <!-- Upload tab -->
        <div v-if="activeTab === 'upload'">
          <!-- Drop zone -->
          <div
            @dragover.prevent="dragOver = true"
            @dragleave="dragOver = false"
            @drop.prevent="handleDrop"
            :class="[
              'border-2 border-dashed rounded-lg p-8 text-center transition-colors',
              isUploading ? 'pointer-events-none opacity-60' : '',
              dragOver ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500',
            ]"
          >
            <div class="text-4xl mb-2">📁</div>
            <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">Drag & drop email files here</p>
            <p class="text-xs text-gray-400 dark:text-gray-500 mb-3">Supports: .eml, .mbox, .pst, .ost, .msg, .olm, .edb</p>
            <label :class="['inline-block px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700', isUploading ? 'pointer-events-none opacity-50' : 'cursor-pointer']">
              {{ isUploading ? 'Uploading...' : 'Choose Files' }}
              <input
                type="file"
                multiple
                accept=".eml,.mbox,.pst,.ost,.msg,.olm,.edb"
                @change="handleFiles($event.target.files)"
                class="hidden"
                :disabled="isUploading"
              />
            </label>
          </div>

          <!-- Upload progress -->
          <div v-if="uploads.length" class="mt-4 space-y-2">
            <div
              v-for="u in uploads"
              :key="u.id"
              class="flex items-center gap-3 p-2 bg-gray-50 dark:bg-gray-700/50 rounded"
            >
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">{{ u.name }}</div>
                <div class="text-xs text-gray-400 dark:text-gray-500">{{ formatSize(u.size) }}</div>
              </div>
              <div v-if="u.status === 'uploading'" class="text-xs text-blue-500 flex items-center gap-2">
                <span>Uploading</span>
                <div class="w-16 h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                  <div class="h-full bg-blue-500 rounded-full animate-pulse" style="width: 60%"></div>
                </div>
              </div>
              <div v-else-if="u.status === 'importing'" class="text-xs text-blue-500 flex items-center gap-2">
                <span>{{ u.processed || 0 }} processed</span>
                <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                <button
                  @click="stopUpload(u)"
                  class="px-1.5 py-0.5 text-xs font-medium rounded bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors"
                  title="Stop import"
                >Stop</button>
              </div>
              <span v-else-if="u.status === 'done'" class="text-xs text-green-500">{{ importedLabel(u) }}</span>
              <span v-else-if="u.status === 'error'" class="text-xs text-red-500" :title="u.error">✗ Failed</span>
              <span v-else-if="u.status === 'duplicate'" class="text-xs text-yellow-500">⚠ Already queued</span>
              <span v-else class="text-xs text-gray-400 dark:text-gray-500">Queued</span>
            </div>
          </div>
        </div>

        <!-- Existing files tab -->
        <div v-if="activeTab === 'existing'">
          <div class="flex items-center justify-between mb-3">
            <p class="text-sm text-gray-500 dark:text-gray-400">Files in the uploads folder</p>
            <button
              @click="loadFiles"
              class="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-medium"
            >Refresh</button>
          </div>

          <div v-if="loadingFiles" class="py-8 text-center text-sm text-gray-400 dark:text-gray-500">Loading...</div>

          <div v-else-if="existingFiles.length === 0" class="py-8 text-center">
            <div class="text-3xl mb-2">📭</div>
            <p class="text-sm text-gray-400 dark:text-gray-500">No email files found in uploads folder</p>
          </div>

          <div v-else class="space-y-1 max-h-72 overflow-y-auto">
            <div
              v-for="f in existingFiles"
              :key="f.name"
              class="flex items-center gap-3 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700 group"
            >
              <div class="text-lg shrink-0">{{ fileIcon(f.name) }}</div>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-gray-700 dark:text-gray-300 truncate" :title="f.name">{{ f.name }}</div>
                <div class="text-xs text-gray-400 dark:text-gray-500">{{ formatSize(f.size) }} &middot; {{ formatDate(f.modified) }}</div>
              </div>
              <button
                v-if="f.status === 'idle'"
                @click="importFile(f)"
                class="shrink-0 px-3 py-1 text-xs font-medium rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
              >Import</button>
              <div v-else-if="f.status === 'importing'" class="shrink-0 flex items-center gap-2">
                <div class="text-right">
                  <div class="text-xs text-blue-600 dark:text-blue-400 font-medium flex items-center gap-1">
                    {{ f.processed || 0 }} processed
                    <span class="inline-block w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></span>
                  </div>
                  <div class="text-xs text-gray-400 dark:text-gray-500">{{ f.imported || 0 }} imported</div>
                </div>
                <button
                  @click="stopImport(f)"
                  class="px-2 py-1 text-xs font-medium rounded bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors"
                  title="Stop import"
                >Stop</button>
              </div>
              <span v-else-if="f.status === 'done'" class="shrink-0 text-xs text-green-500">{{ importedLabel(f) }}</span>
              <span v-else-if="f.status === 'error'" class="shrink-0 text-xs text-red-500" :title="f.error">✗ Failed</span>
            </div>
          </div>

          <!-- Bulk import button -->
          <div v-if="existingFiles.length > 0" class="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700 flex justify-end gap-2">
            <button
              v-if="hasImportingFiles"
              @click="stopAllImports"
              class="px-4 py-1.5 text-sm font-medium rounded bg-red-600 text-white hover:bg-red-700 transition-colors"
            >Stop All</button>
            <button
              @click="importAll"
              :disabled="bulkImporting || !hasIdleFiles"
              class="px-4 py-1.5 text-sm font-medium rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >{{ bulkImporting ? 'Importing...' : 'Import All' }}</button>
          </div>
        </div>
      </div>

      <div class="px-6 py-3 border-t border-gray-200 dark:border-gray-700 flex justify-end">
        <button
          @click="$emit('close')"
          class="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
        >Close</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { uploadFile, listUploadedFiles, importExistingFile, getImportStatus, stopImportJob } from '../api.js'

const STORAGE_KEY = 'spectra-active-imports'

const emit = defineEmits(['close', 'uploaded'])

const activeTab = ref('upload')
const dragOver = ref(false)
const uploads = ref([])
const isUploading = ref(false)
let uploadIdCounter = 0

// Existing files state
const existingFiles = ref([])
const loadingFiles = ref(false)
const bulkImporting = ref(false)

// Track active poll timers so we can clean up
const pollTimers = ref([])

const activeJobCount = computed(() => {
  const uploadActive = uploads.value.filter(u => u.status === 'uploading' || u.status === 'importing').length
  const fileActive = existingFiles.value.filter(f => f.status === 'importing').length
  return uploadActive + fileActive
})

const hasIdleFiles = computed(() => existingFiles.value.some(f => f.status === 'idle'))
const hasImportingFiles = computed(() => existingFiles.value.some(f => f.status === 'importing'))

// ── Persistence helpers ──

function saveActiveJobs() {
  const jobs = {}
  for (const f of existingFiles.value) {
    if (f.status === 'importing' && f._jobId) {
      jobs[f.name] = { job_id: f._jobId, processed: f.processed, imported: f.imported }
    }
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs))
  } catch {}
}

function loadActiveJobs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function clearJobFromStorage(filename) {
  const jobs = loadActiveJobs()
  delete jobs[filename]
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs))
  } catch {}
}

// ── Lifecycle ──

onMounted(() => {
  // Resume polling for any active jobs from a previous session
  resumeActiveJobs()
})

onUnmounted(() => {
  pollTimers.value.forEach(clearInterval)
})

async function resumeActiveJobs() {
  const activeJobs = loadActiveJobs()
  if (Object.keys(activeJobs).length === 0) return

  // Validate jobs still exist on the server before resuming
  const validJobs = {}
  for (const [filename, info] of Object.entries(activeJobs)) {
    try {
      const job = await getImportStatus(info.job_id)
      if (job.status === 'running') {
        validJobs[filename] = info
      } else {
        // Job finished while we were away
        clearJobFromStorage(filename)
      }
    } catch {
      // Job not found (server restarted) — discard
      clearJobFromStorage(filename)
    }
  }

  if (Object.keys(validJobs).length === 0) return

  // Switch to existing tab and load files
  activeTab.value = 'existing'
  await loadFiles()

  // Re-attach polling only for validated jobs
  for (const [filename, info] of Object.entries(validJobs)) {
    const f = existingFiles.value.find(ef => ef.name === filename)
    if (f) {
      f.status = 'importing'
      f.processed = info.processed || 0
      f.imported = info.imported || 0
      f._jobId = info.job_id
      pollImportJob(f, info.job_id)
    }
  }
}

// ── Upload tab ──

function handleDrop(e) {
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files?.length) handleFiles(files)
}

async function handleFiles(files) {
  if (isUploading.value) return

  const newEntries = []
  const existingNames = new Set(uploads.value.map(u => u.name))

  for (const file of files) {
    if (existingNames.has(file.name)) {
      // Mark as duplicate but don't add to queue
      uploads.value.push({ id: ++uploadIdCounter, name: file.name, size: file.size, status: 'duplicate', result: null, error: null })
      continue
    }
    existingNames.add(file.name)
    const entry = { id: ++uploadIdCounter, name: file.name, size: file.size, status: 'queued', result: null, error: null, _file: file }
    uploads.value.push(entry)
    newEntries.push(entry)
  }

  if (newEntries.length === 0) return

  isUploading.value = true
  for (const entry of newEntries) {
    if (entry.status !== 'queued') continue

    entry.status = 'uploading'
    try {
      const result = await uploadFile(entry._file)
      // If result includes a job_id, it's a background import — poll for progress
      if (result.job_id) {
        entry.status = 'importing'
        entry._jobId = result.job_id
        pollUploadJob(entry, result.job_id)
      } else {
        entry.status = 'done'
        entry.result = result
        emit('uploaded', result)
      }
    } catch (err) {
      entry.status = 'error'
      entry.error = err.message
    }
  }
  isUploading.value = false
}

function pollUploadJob(entry, jobId) {
  let failCount = 0
  const timer = setInterval(async () => {
    try {
      const job = await getImportStatus(jobId)
      failCount = 0
      entry.processed = job.processed
      entry.imported = job.imported
      if (job.status === 'done' || job.status === 'error' || job.status === 'cancelled') {
        clearInterval(timer)
        pollTimers.value = pollTimers.value.filter(t => t !== timer)
        if (job.status === 'done') {
          entry.status = 'done'
          entry.result = job
          emit('uploaded', job)
        } else if (job.status === 'cancelled') {
          entry.status = 'done'
          entry.result = job
          emit('uploaded', job)
        } else {
          entry.status = 'error'
          entry.error = job.error || 'Import failed'
        }
      }
    } catch {
      failCount++
      if (failCount >= 3) {
        clearInterval(timer)
        pollTimers.value = pollTimers.value.filter(t => t !== timer)
        entry.status = 'error'
        entry.error = 'Lost connection to import job'
      }
    }
  }, 2000)
  pollTimers.value.push(timer)
}

// ── Existing files tab ──

async function loadFiles() {
  loadingFiles.value = true
  try {
    const data = await listUploadedFiles()
    existingFiles.value = data.files.map(f => {
      // Preserve state for files already being polled in this session
      const existing = existingFiles.value.find(ef => ef.name === f.name)
      if (existing && existing.status !== 'idle') {
        return { ...f, status: existing.status, result: existing.result, error: existing.error, _jobId: existing._jobId, processed: existing.processed, imported: existing.imported }
      }
      return { ...f, status: 'idle', result: null, error: null }
    })
  } catch (err) {
    existingFiles.value = []
  } finally {
    loadingFiles.value = false
  }
}

async function importFile(f) {
  if (f.status !== 'idle') return // Prevent duplicate imports
  f.status = 'importing'
  f.processed = 0
  f.imported = 0
  try {
    const { job_id } = await importExistingFile(f.name)
    f._jobId = job_id
    saveActiveJobs()
    pollImportJob(f, job_id)
  } catch (err) {
    f.status = 'error'
    f.error = err.message
  }
}

function pollImportJob(f, jobId) {
  let failCount = 0
  const timer = setInterval(async () => {
    try {
      const job = await getImportStatus(jobId)
      failCount = 0
      f.processed = job.processed
      f.imported = job.imported
      f.skipped = job.skipped
      f.errors = job.errors
      saveActiveJobs()
      if (job.status === 'done' || job.status === 'error' || job.status === 'cancelled') {
        clearInterval(timer)
        pollTimers.value = pollTimers.value.filter(t => t !== timer)
        clearJobFromStorage(f.name)
        if (job.status === 'done') {
          f.status = 'done'
          f.result = job
          emit('uploaded', job)
        } else if (job.status === 'cancelled') {
          f.status = 'done'
          f.result = job
          emit('uploaded', job)
        } else {
          f.status = 'error'
          f.error = job.error || 'Import failed'
        }
      }
    } catch {
      failCount++
      if (failCount >= 3) {
        // Job is gone (server restarted or job expired) — stop polling
        clearInterval(timer)
        pollTimers.value = pollTimers.value.filter(t => t !== timer)
        clearJobFromStorage(f.name)
        f.status = 'idle'
      }
    }
  }, 2000)
  pollTimers.value.push(timer)
}

async function importAll() {
  bulkImporting.value = true
  for (const f of existingFiles.value) {
    if (f.status !== 'idle') continue
    await importFile(f)
  }
  bulkImporting.value = false
}

async function stopImport(f) {
  if (f.status !== 'importing' || !f._jobId) return
  try {
    await stopImportJob(f._jobId)
  } catch {}
}

async function stopUpload(u) {
  if (u.status !== 'importing' || !u._jobId) return
  try {
    await stopImportJob(u._jobId)
  } catch {}
}

async function stopAllImports() {
  const importing = existingFiles.value.filter(f => f.status === 'importing' && f._jobId)
  await Promise.allSettled(importing.map(f => stopImportJob(f._jobId)))
}

// ── Helpers ──

function importedLabel(item) {
  const r = item.result
  if (!r) return '✓ Done'
  const parts = []
  if (r.imported) parts.push(`${r.imported} imported`)
  if (r.skipped) parts.push(`${r.skipped} skipped`)
  if (r.errors) parts.push(`${r.errors} errors`)
  return parts.length ? `✓ ${parts.join(', ')}` : '✓ Done'
}

function fileIcon(name) {
  const ext = name.split('.').pop()?.toLowerCase()
  const icons = { eml: '✉️', mbox: '📦', pst: '🗄️', ost: '🗄️', msg: '💬' }
  return icons[ext] || '📄'
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

function formatDate(timestamp) {
  if (!timestamp) return ''
  return new Date(timestamp * 1000).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  })
}
</script>

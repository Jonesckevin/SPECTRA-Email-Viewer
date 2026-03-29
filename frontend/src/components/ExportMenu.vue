<template>
  <div class="relative">
    <button
      @click="open = !open"
      class="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
    >
      Export ▾
    </button>

    <!-- Dropdown -->
    <div
      v-if="open"
      class="absolute right-0 top-full mt-1 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 py-1 w-64 z-40"
      @click.stop
    >
      <div class="px-3 py-1.5 text-xs text-gray-400 dark:text-gray-500 border-b border-gray-100 dark:border-gray-700">
        Export emails
      </div>

      <button @click="doExport('json', false)" class="menu-item">
        📄 Export all as JSON
      </button>
      <button @click="doExport('zip', false)" class="menu-item">
        📦 Export all as ZIP (.eml files)
      </button>

      <div v-if="searchQuery || starredOnly" class="border-t border-gray-100 dark:border-gray-700">
        <div class="px-3 py-1.5 text-xs text-gray-400 dark:text-gray-500">Filtered/Starred</div>
        <button @click="doExport('json', true)" class="menu-item">
          📄 Export filtered as JSON
        </button>
        <button @click="doExport('zip', true)" class="menu-item">
          📦 Export filtered as ZIP
        </button>
      </div>

      <div v-if="starredOnly || !searchQuery" class="border-t border-gray-100 dark:border-gray-700">
        <button @click="doExportStarred('json')" class="menu-item">
          ⭐ Export starred as JSON
        </button>
        <button @click="doExportStarred('zip')" class="menu-item">
          ⭐ Export starred as ZIP
        </button>
      </div>

      <div v-if="currentEmailId" class="border-t border-gray-100 dark:border-gray-700">
        <button @click="doExportImage()" class="menu-item">
          📷 Export current email as image
        </button>
      </div>

      <div class="border-t border-gray-100 dark:border-gray-700">
        <button @click="doExportImages(false)" class="menu-item">
          📷 Export all as images (ZIP)
        </button>
        <button v-if="searchQuery || starredOnly" @click="doExportImages(true)" class="menu-item">
          📷 Export filtered as images (ZIP)
        </button>
      </div>

      <div class="border-t border-gray-100 dark:border-gray-700">
        <div class="px-3 py-1.5 text-xs text-gray-400 dark:text-gray-500">Forensic</div>
        <button @click="doExport('json', false, true)" class="menu-item">
          🔍 Export all with forensic data (JSON)
        </button>
        <button v-if="searchQuery || starredOnly" @click="doExport('json', true, true)" class="menu-item">
          🔍 Export filtered with forensic data
        </button>
      </div>
    </div>

    <!-- Click-away overlay -->
    <div v-if="open" class="fixed inset-0 z-30" @click="open = false"></div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { exportJson, exportZip, exportImage, exportImagesZip } from '../api.js'

const props = defineProps({
  searchQuery: { type: String, default: '' },
  starredOnly: { type: Boolean, default: false },
  selectedIds: { type: Array, default: () => [] },
  currentEmailId: { type: Number, default: null },
})

const open = ref(false)

function download(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
  open.value = false
}

async function doExport(format, useFilters, includeForensics = false) {
  try {
    const body = {}
    if (useFilters) {
      if (props.searchQuery) body.search_query = props.searchQuery
      if (props.starredOnly) body.starred_only = true
    }
    if (includeForensics) body.include_forensics = true
    const blob = format === 'json'
      ? await exportJson(body)
      : await exportZip(body)
    download(blob, `emails.${format === 'json' ? 'json' : 'zip'}`)
  } catch (err) {
    alert('Export failed: ' + err.message)
  }
}

async function doExportStarred(format) {
  try {
    const body = { starred_only: true }
    const blob = format === 'json'
      ? await exportJson(body)
      : await exportZip(body)
    download(blob, `starred_emails.${format === 'json' ? 'json' : 'zip'}`)
  } catch (err) {
    alert('Export failed: ' + err.message)
  }
}

async function doExportImage() {
  if (!props.currentEmailId) return
  try {
    const blob = await exportImage(props.currentEmailId)
    download(blob, `email_${props.currentEmailId}.png`)
  } catch (err) {
    alert('Export failed: ' + err.message)
  }
}

async function doExportImages(useFilters) {
  try {
    const body = {}
    if (useFilters) {
      if (props.searchQuery) body.search_query = props.searchQuery
      if (props.starredOnly) body.starred_only = true
    }
    const blob = await exportImagesZip(body)
    download(blob, 'email_images.zip')
  } catch (err) {
    alert('Export failed: ' + err.message)
  }
}
</script>

<style scoped>
.menu-item {
  @apply w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors;
}
</style>

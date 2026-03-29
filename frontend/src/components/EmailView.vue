<template>
  <div class="flex flex-col h-full">
    <!-- Email header bar -->
    <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shrink-0">
      <div class="flex items-center gap-3 mb-2">
        <!-- Back button (mobile) -->
        <button
          @click="$emit('back')"
          class="md:hidden text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
        >← Back</button>

        <!-- Star -->
        <button
          @click="$emit('toggle-star', email)"
          :class="['text-xl leading-none', email.is_starred ? 'text-yellow-400' : 'text-gray-300 dark:text-gray-600 hover:text-yellow-300']"
        >{{ email.is_starred ? '★' : '☆' }}</button>

        <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100 flex-1 line-clamp-1">{{ email.subject || '(no subject)' }}</h2>

        <!-- Forensics toggle button -->
        <button
          @click="showForensics = !showForensics"
          :class="[
            'px-2 py-1 text-xs border rounded transition-colors',
            showForensics
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
              : 'border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'
          ]"
          title="Toggle forensic analysis"
        >
          🔍 Forensics
        </button>

        <!-- Export as image button -->
        <button
          @click="exportAsImage"
          :disabled="exportingImage"
          class="px-2 py-1 text-xs border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400 disabled:opacity-50"
          title="Export as image"
        >
          {{ exportingImage ? '...' : '📷 Image' }}
        </button>
      </div>

      <!-- Metadata -->
      <div class="text-sm space-y-0.5">
        <div class="flex items-center gap-2">
          <span class="font-medium text-gray-700 dark:text-gray-300">From:</span>
          <span class="text-gray-600 dark:text-gray-400">
            {{ email.sender_name ? `${email.sender_name} <${email.sender}>` : email.sender }}
          </span>
        </div>
        <div class="flex items-center gap-2">
          <span class="font-medium text-gray-700 dark:text-gray-300">To:</span>
          <span class="text-gray-600 dark:text-gray-400 truncate">{{ email.recipients }}</span>
        </div>
        <div v-if="email.cc" class="flex items-center gap-2">
          <span class="font-medium text-gray-700 dark:text-gray-300">Cc:</span>
          <span class="text-gray-600 dark:text-gray-400 truncate">{{ email.cc }}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="font-medium text-gray-700 dark:text-gray-300">Date:</span>
          <span class="text-gray-600 dark:text-gray-400">{{ formatFullDate(email.date) }}</span>
        </div>
      </div>

      <!-- Attachments -->
      <div v-if="email.attachments?.length" class="mt-2 flex flex-wrap gap-2">
        <a
          v-for="att in email.attachments"
          :key="att.id"
          :href="`/api/emails/attachment/${att.id}`"
          target="_blank"
          class="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
        >
          📎 {{ att.filename }}
          <span class="text-gray-400 dark:text-gray-500">({{ formatSize(att.size) }})</span>
        </a>
      </div>
    </div>

    <!-- Forensic panel (collapsible) -->
    <ForensicPanel
      v-if="showForensics"
      :email-id="email.id"
      :email="email"
    />

    <!-- Email body -->
    <div class="flex-1 overflow-y-auto bg-white dark:bg-gray-900">
      <div v-if="email.body_html" class="h-full">
        <iframe
          ref="iframeRef"
          sandbox="allow-same-origin"
          class="email-frame w-full h-full"
          :srcdoc="sanitizedHtml"
        ></iframe>
      </div>
      <div v-else class="p-4">
        <pre class="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300 font-sans leading-relaxed">{{ email.body_text || '(empty email)' }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { exportImage } from '../api.js'
import { useDarkMode } from '../composables/useDarkMode.js'
import ForensicPanel from './ForensicPanel.vue'

const props = defineProps({
  email: { type: Object, required: true },
})
defineEmits(['back', 'toggle-star'])

const { isDark } = useDarkMode()
const iframeRef = ref(null)
const exportingImage = ref(false)
const showForensics = ref(false)

const sanitizedHtml = computed(() => {
  let html = props.email.body_html || ''
  // Strip script tags for safety (iframe sandbox also blocks them)
  html = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
  // Add base styles for readability — includes dark mode support
  const darkCss = isDark.value ? `
    body { background: #111827 !important; color: #d1d5db !important; }
    a { color: #60a5fa !important; }
    table, td, th { border-color: #374151 !important; }
    blockquote { border-left-color: #4b5563 !important; color: #9ca3af !important; }
    hr { border-color: #374151 !important; }
    pre, code { background: #1f2937 !important; color: #d1d5db !important; }
  ` : ''
  const style = `<style>
    body { font-family: sans-serif; padding: 16px; margin: 0; max-width: 100%; overflow-x: hidden; }
    img { max-width: 100%; height: auto; }
    ${darkCss}
  </style>`
  if (html.includes('<head')) {
    html = html.replace(/<head([^>]*)>/, `<head$1>${style}`)
  } else if (html.includes('<html')) {
    html = html.replace(/<html([^>]*)>/, `<html$1><head>${style}</head>`)
  } else {
    html = style + html
  }
  return html
})

function formatFullDate(dateStr) {
  if (!dateStr) return ''
  try {
    return new Date(dateStr).toLocaleString([], {
      weekday: 'short', year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return dateStr }
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

async function exportAsImage() {
  exportingImage.value = true
  try {
    const blob = await exportImage(props.email.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `email_${props.email.id}.png`
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    alert('Failed to export image: ' + err.message)
  } finally {
    exportingImage.value = false
  }
}
</script>

<template>
  <div class="h-screen flex flex-col">
    <!-- Top bar -->
    <header class="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-4 py-2 flex items-center gap-3 shrink-0">
      <h1 class="text-lg font-bold text-blue-600 dark:text-blue-400 whitespace-nowrap flex items-center gap-1.5"><img src="/logo.svg" alt="SPECTRA" class="w-6 h-6" /> SPECTRA</h1>

      <!-- Navigation tabs -->
      <nav class="flex border border-gray-200 dark:border-gray-600 rounded-lg overflow-hidden">
        <router-link
          v-for="tab in navTabs"
          :key="tab.to"
          :to="tab.to"
          class="px-3 py-1.5 text-xs font-medium transition-colors"
          :class="isActive(tab.to)
            ? 'bg-blue-600 text-white'
            : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'"
        >{{ tab.label }}</router-link>
      </nav>

      <!-- Search bar (only on emails route) -->
      <SearchBar
        v-if="isEmailsRoute"
        v-model="searchQuery"
        @search="doSearch"
        @clear="clearSearch"
        class="flex-1 max-w-2xl"
      />
      <div v-else class="flex-1"></div>

      <!-- Starred filter toggle (only on emails route) -->
      <button
        v-if="isEmailsRoute"
        @click="toggleStarredFilter"
        :class="[
          'px-3 py-1.5 rounded text-sm font-medium border transition-colors',
          starredOnly
            ? 'bg-yellow-100 dark:bg-yellow-900/40 border-yellow-400 dark:border-yellow-600 text-yellow-700 dark:text-yellow-300'
            : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
        ]"
        :title="starredOnly ? 'Showing starred only — click to show all' : 'Show starred only'"
      >
        {{ starredOnly ? '★ Starred' : '☆ Starred' }}
      </button>

      <!-- Export menu (only on emails route) -->
      <ExportMenu
        v-if="isEmailsRoute"
        :search-query="activeSearch"
        :starred-only="starredOnly"
        :selected-ids="selectedIds"
        :current-email-id="selectedEmail?.id"
      />

      <!-- Upload button -->
      <button
        @click="showUpload = true"
        class="px-3 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 transition-colors"
      >
        Upload
      </button>

      <!-- Project switcher -->
      <ProjectSwitcher />

      <!-- Dark mode toggle -->
      <button
        @click="toggleDark"
        class="p-1.5 rounded text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
      >
        <svg v-if="isDark" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
        <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
        </svg>
      </button>

      <!-- Stats -->
      <span v-if="stats" class="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
        {{ stats.total_emails }} emails
      </span>
    </header>

    <!-- Main content: Router View -->
    <router-view
      v-slot="{ Component }"
      class="flex-1 overflow-hidden"
    >
      <component
        :is="Component"
        :emails="emails"
        :selected-email="selectedEmail"
        :selected-ids="selectedIds"
        :loading="loading"
        :total-emails="totalEmails"
        :page="page"
        :per-page="perPage"
        :starred-only="starredOnly"
        @select="selectEmail"
        @toggle-star="handleToggleStar"
        @toggle-star-detail="handleToggleStarDetail"
        @page-change="changePage"
        @go-to-email="goToEmail"
      />
    </router-view>

    <!-- Upload modal -->
    <UploadModal
      v-if="showUpload"
      @close="showUpload = false"
      @uploaded="handleUploaded"
    />

    <!-- Footer -->
    <footer class="bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 px-4 py-1.5 flex items-center shrink-0 text-xs">
      <!-- Left: Tools dropdown -->
      <div class="flex-1 flex items-center">
        <div class="relative" ref="toolsDropdownRef">
          <button
            @click="toolsOpen = !toolsOpen"
            class="flex items-center gap-1 px-2 py-1 rounded text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            🧰 Tools
            <svg class="w-3 h-3 transition-transform" :class="{ 'rotate-180': toolsOpen }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
            </svg>
          </button>
          <div
            v-if="toolsOpen"
            class="absolute bottom-full left-0 mb-1 w-56 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-1 z-50"
          >
            <a
              v-for="tool in externalTools"
              :key="tool.href"
              :href="tool.href"
              target="_blank"
              rel="noopener"
              class="flex items-center gap-2 px-3 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              @click="toolsOpen = false"
            >
              <span>{{ tool.icon }}</span>
              <span>{{ tool.label }}</span>
              <svg class="w-3 h-3 ml-auto text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
            </a>
          </div>
        </div>
      </div>

      <!-- Center: Project name -->
      <div class="text-gray-400 dark:text-gray-500 font-medium">
        <span class="font-semibold">SPECTRA</span>
        <span class="hidden sm:inline text-gray-300 dark:text-gray-600 mx-1">—</span>
        <span class="hidden sm:inline">Suspicious Post & Email Capture Tool for Rapid Analysis</span>
      </div>

      <!-- Right: GitHub link -->
      <div class="flex-1 flex justify-end">
        <a
          href="https://github.com/jonesckevin"
          target="_blank"
          rel="noopener"
          class="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          title="GitHub"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
          </svg>
        </a>
      </div>
    </footer>

    <!-- Toast notifications -->
    <div class="fixed bottom-4 right-4 flex flex-col gap-2 z-50">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        :class="[
          'px-4 py-2 rounded-lg shadow-lg text-white text-sm max-w-sm transition-all',
          toast.type === 'error' ? 'bg-red-500' : 'bg-green-500'
        ]"
      >
        {{ toast.message }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { fetchEmails, fetchEmail, searchEmails, toggleStar, fetchStats, setActiveProject, getActiveProjectApi } from './api.js'
import { useDarkMode } from './composables/useDarkMode.js'
import SearchBar from './components/SearchBar.vue'
import ExportMenu from './components/ExportMenu.vue'
import UploadModal from './components/UploadModal.vue'
import ProjectSwitcher from './components/ProjectSwitcher.vue'

const { isDark, toggle: toggleDark } = useDarkMode()
const router = useRouter()
const route = useRoute()

const navTabs = [
  { to: '/emails', label: '📧 Emails' },
  { to: '/scanner', label: '🛡 Scanner' },
  { to: '/statistics', label: '📊 Statistics' },
  { to: '/logs', label: '📋 Logs' },
  { to: '/projects', label: '📁 Projects' },
]

const isEmailsRoute = computed(() => route.path.startsWith('/emails'))

function isActive(path) {
  return route.path.startsWith(path)
}

const emails = ref([])
const selectedEmail = ref(null)
const selectedIds = ref([])
const loading = ref(false)
const searchQuery = ref('')
const activeSearch = ref('')
const starredOnly = ref(false)
const page = ref(1)
const perPage = ref(50)
const totalEmails = ref(0)
const showUpload = ref(false)
const stats = ref(null)
const toasts = ref([])

// Tools dropdown
const toolsOpen = ref(false)
const toolsDropdownRef = ref(null)
const externalTools = [
  { icon: '�', label: 'EML Viewer', href: '/tools/eml-viewer.html' },
  { icon: '💼', label: 'MSG Viewer', href: '/tools/msg-viewer.html' },
  { icon: '�🔧', label: 'PST / OST Repair', href: '/tools/pst-repair.html' },
]

function handleClickOutsideTools(e) {
  if (toolsDropdownRef.value && !toolsDropdownRef.value.contains(e.target)) {
    toolsOpen.value = false
  }
}

let toastId = 0
function showToast(message, type = 'success') {
  const id = ++toastId
  toasts.value.push({ id, message, type })
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }, 4000)
}

async function loadEmails() {
  loading.value = true
  try {
    let result
    if (activeSearch.value) {
      result = await searchEmails({
        q: activeSearch.value,
        page: page.value,
        per_page: perPage.value,
        starred_only: starredOnly.value,
      })
    } else {
      result = await fetchEmails({
        page: page.value,
        per_page: perPage.value,
        starred: starredOnly.value,
      })
    }
    emails.value = result.emails
    totalEmails.value = result.total
  } catch (err) {
    showToast(err.message, 'error')
  } finally {
    loading.value = false
  }
}

async function doSearch(query) {
  activeSearch.value = query
  page.value = 1
  await loadEmails()
}

function clearSearch() {
  searchQuery.value = ''
  activeSearch.value = ''
  page.value = 1
  loadEmails()
}

function toggleStarredFilter() {
  starredOnly.value = !starredOnly.value
  page.value = 1
  loadEmails()
}

async function selectEmail(emailSummary) {
  try {
    selectedEmail.value = await fetchEmail(emailSummary.id)
  } catch (err) {
    showToast(err.message, 'error')
  }
}

async function goToEmail(emailId) {
  router.push('/emails')
  try {
    selectedEmail.value = await fetchEmail(emailId)
  } catch (err) {
    showToast(err.message, 'error')
  }
}

async function handleToggleStar(emailSummary) {
  try {
    const result = await toggleStar(emailSummary.id)
    // Update in list
    const idx = emails.value.findIndex(e => e.id === emailSummary.id)
    if (idx !== -1) {
      emails.value[idx] = { ...emails.value[idx], is_starred: result.is_starred }
    }
    // Update detail view if same email
    if (selectedEmail.value?.id === emailSummary.id) {
      selectedEmail.value = { ...selectedEmail.value, is_starred: result.is_starred }
    }
  } catch (err) {
    showToast(err.message, 'error')
  }
}

async function handleToggleStarDetail(email) {
  await handleToggleStar(email)
}

function changePage(newPage) {
  page.value = newPage
  loadEmails()
}

async function handleUploaded(result) {
  showToast(`Imported ${result.imported} emails (${result.skipped} skipped, ${result.errors} errors)`)
  await loadEmails()
  stats.value = await fetchStats()
}

onMounted(async () => {
  document.addEventListener('click', handleClickOutsideTools)

  // Load active project from server
  try {
    const proj = await getActiveProjectApi()
    if (proj.active_project) setActiveProject(proj.active_project)
  } catch (e) { /* fallback to default */ }

  await loadEmails()
  try {
    stats.value = await fetchStats()
  } catch (e) { /* stats are non-critical */ }
})

// Reload emails when navigating back to the emails page
watch(() => route.path, (newPath) => {
  if (newPath.startsWith('/emails') && emails.value.length === 0) {
    loadEmails()
  }
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutsideTools)
})
</script>

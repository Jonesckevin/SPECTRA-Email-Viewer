<template>
  <div class="h-full overflow-y-auto bg-gray-50 dark:bg-gray-950 p-6">
    <div class="max-w-4xl mx-auto">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h2 class="text-lg font-bold text-gray-800 dark:text-gray-200">📁 Projects / Cases</h2>
          <p class="text-sm text-gray-500 dark:text-gray-400">Each project has its own isolated email database</p>
        </div>
      </div>

      <!-- Create project -->
      <div class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-6">
        <h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Create New Project</h3>
        <form @submit.prevent="handleCreate" class="flex gap-3">
          <input
            v-model="newName"
            type="text"
            placeholder="Project name (e.g. Case 2024-001)"
            class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            :disabled="!newName.trim() || creating"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >{{ creating ? 'Creating...' : 'Create' }}</button>
        </form>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="text-center py-8 text-gray-500 dark:text-gray-400">Loading projects...</div>

      <!-- Project list -->
      <div v-else class="space-y-3">
        <div
          v-for="proj in projects"
          :key="proj.slug"
          class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 flex items-center gap-4 transition-shadow hover:shadow-md"
          :class="{ 'ring-2 ring-blue-500 border-blue-300 dark:border-blue-600': proj.is_active }"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-medium text-gray-800 dark:text-gray-200">{{ proj.name }}</span>
              <span v-if="proj.is_active" class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">ACTIVE</span>
            </div>
            <div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {{ proj.slug }} &middot; {{ proj.email_count ?? '—' }} emails
              <span v-if="proj.created_at"> &middot; created {{ formatDate(proj.created_at) }}</span>
            </div>
          </div>

          <div class="flex items-center gap-2 shrink-0">
            <button
              @click="handleReset(proj.slug, proj.name)"
              :disabled="resetting === proj.slug"
              class="px-3 py-1.5 text-xs font-medium rounded bg-yellow-50 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 hover:bg-yellow-100 dark:hover:bg-yellow-900/50 disabled:opacity-50 transition-colors"
            >{{ resetting === proj.slug ? 'Resetting...' : 'Reset Data' }}</button>
            <button
              v-if="proj.slug !== 'default'"
              @click="handleDelete(proj.slug, proj.name)"
              class="px-3 py-1.5 text-xs font-medium rounded bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors"
            >Delete</button>
          </div>
        </div>
      </div>

      <div v-if="!loading && projects.length === 0" class="text-center py-16">
        <div class="text-5xl mb-4">📁</div>
        <p class="text-lg text-gray-500 dark:text-gray-400">No projects found</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listProjects, createProject, deleteProject, resetProject } from '../api.js'

const projects = ref([])
const loading = ref(true)
const newName = ref('')
const creating = ref(false)
const resetting = ref(null)

async function load() {
  loading.value = true
  try {
    const data = await listProjects()
    projects.value = data.projects || data
  } catch (e) {
    projects.value = []
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!newName.value.trim()) return
  creating.value = true
  try {
    await createProject(newName.value.trim())
    newName.value = ''
    await load()
  } catch (e) {
    alert('Failed to create project: ' + e.message)
  } finally {
    creating.value = false
  }
}

async function handleReset(slug, name) {
  if (!confirm(`Reset project "${name}"? This will permanently delete ALL emails, attachments, and scan results. The project itself will remain.`)) return
  resetting.value = slug
  try {
    await resetProject(slug)
    await load()
  } catch (e) {
    alert('Failed to reset: ' + e.message)
  } finally {
    resetting.value = null
  }
}

async function handleDelete(slug, name) {
  if (!confirm(`Delete project "${name}"? This will permanently delete all emails in this project.`)) return
  try {
    await deleteProject(slug)
    await load()
  } catch (e) {
    alert('Failed to delete: ' + e.message)
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const ts = typeof dateStr === 'number' && dateStr < 1e12 ? dateStr * 1000 : dateStr
    return new Date(ts).toLocaleDateString()
  } catch { return dateStr }
}

onMounted(load)
</script>

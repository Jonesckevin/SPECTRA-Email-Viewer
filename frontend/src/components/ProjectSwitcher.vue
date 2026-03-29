<template>
  <div class="relative">
    <button
      @click="open = !open; if(open) load()"
      class="px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors flex items-center gap-1"
      title="Switch project"
    >
      📁 {{ currentName || 'default' }}
      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
    </button>

    <!-- Dropdown -->
    <div
      v-if="open"
      class="absolute right-0 top-full mt-1 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 py-1 w-56 z-40"
    >
      <div class="px-3 py-1.5 text-xs text-gray-400 dark:text-gray-500 border-b border-gray-100 dark:border-gray-700">
        Projects
      </div>
      <div v-if="loading" class="px-3 py-2 text-xs text-gray-400">Loading...</div>
      <button
        v-for="p in projects"
        :key="p.slug"
        @click="switchTo(p.slug)"
        class="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors flex items-center justify-between"
        :class="p.is_active ? 'text-blue-600 dark:text-blue-400 font-medium' : 'text-gray-700 dark:text-gray-300'"
      >
        <span class="truncate">{{ p.name }}</span>
        <span v-if="p.is_active" class="text-[10px] bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300 px-1 rounded">active</span>
      </button>
      <div class="border-t border-gray-100 dark:border-gray-700">
        <router-link
          to="/projects"
          @click="open = false"
          class="block px-3 py-2 text-xs text-blue-600 dark:text-blue-400 hover:bg-gray-50 dark:hover:bg-gray-700"
        >Manage projects →</router-link>
      </div>
    </div>

    <!-- Click-away -->
    <div v-if="open" class="fixed inset-0 z-30" @click="open = false"></div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listProjects, activateProject, setActiveProject, getActiveProject } from '../api.js'

const open = ref(false)
const loading = ref(false)
const projects = ref([])
const currentName = ref(getActiveProject() || 'default')

async function load() {
  loading.value = true
  try {
    const data = await listProjects()
    projects.value = data.projects || data
    const active = projects.value.find(p => p.is_active)
    if (active) currentName.value = active.name
  } catch (e) {
    projects.value = []
  } finally {
    loading.value = false
  }
}

async function switchTo(slug) {
  try {
    await activateProject(slug)
    setActiveProject(slug)
    currentName.value = projects.value.find(p => p.slug === slug)?.name || slug
    open.value = false
    // Reload the page to refresh all data
    window.location.reload()
  } catch (e) {
    alert('Failed to switch project: ' + e.message)
  }
}

onMounted(load)
</script>

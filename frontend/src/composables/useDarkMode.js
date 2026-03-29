import { ref, watch } from 'vue'

const isDark = ref(false)

function applyTheme(dark) {
  if (dark) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

// Initialize from localStorage
const stored = localStorage.getItem('spectra-dark-mode')
if (stored !== null) {
  isDark.value = stored === 'true'
} else {
  isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
}
applyTheme(isDark.value)

watch(isDark, (val) => {
  localStorage.setItem('spectra-dark-mode', val)
  applyTheme(val)
})

export function useDarkMode() {
  function toggle() {
    isDark.value = !isDark.value
  }
  return { isDark, toggle }
}

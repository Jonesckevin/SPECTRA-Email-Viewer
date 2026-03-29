const BASE = '/api'

// Active project slug — sent with every request
let _activeProject = null

export function setActiveProject(slug) {
  _activeProject = slug
}

export function getActiveProject() {
  return _activeProject
}

function projectHeaders() {
  const h = {}
  if (_activeProject) h['X-Project'] = _activeProject
  return h
}

async function request(url, options = {}) {
  const hdrs = { 'Content-Type': 'application/json', ...projectHeaders(), ...options.headers }
  const res = await fetch(`${BASE}${url}`, { ...options, headers: hdrs })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Request failed: ${res.status}`)
  }
  return res
}

export async function fetchEmails(params = {}) {
  const qs = new URLSearchParams(params).toString()
  const res = await request(`/emails?${qs}`)
  return res.json()
}

export async function fetchEmail(id) {
  const res = await request(`/emails/${id}`)
  return res.json()
}

export async function searchEmails(params = {}) {
  const qs = new URLSearchParams(params).toString()
  const res = await request(`/search?${qs}`)
  return res.json()
}

export async function toggleStar(emailId) {
  const res = await request(`/stars/${emailId}/toggle`, { method: 'POST' })
  return res.json()
}

export async function bulkStar(emailIds, starred) {
  const res = await request('/stars/bulk', {
    method: 'POST',
    body: JSON.stringify({ email_ids: emailIds, starred }),
  })
  return res.json()
}

export async function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${BASE}/upload`, {
    method: 'POST',
    headers: projectHeaders(),
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Upload failed')
  }
  return res.json()
}

export async function listUploadedFiles() {
  const res = await request('/upload/files')
  return res.json()
}

export async function importExistingFile(filename) {
  const res = await request('/upload/import', {
    method: 'POST',
    body: JSON.stringify({ filename }),
  })
  return res.json()
}

export async function getImportStatus(jobId) {
  const res = await request(`/upload/import/${jobId}`)
  return res.json()
}

export async function stopImportJob(jobId) {
  const res = await request(`/upload/import/${jobId}/stop`, { method: 'POST' })
  return res.json()
}

export async function exportJson(body) {
  const res = await fetch(`${BASE}/export/json`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...projectHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error('Export failed')
  return res.blob()
}

export async function exportZip(body) {
  const res = await fetch(`${BASE}/export/zip`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...projectHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error('Export failed')
  return res.blob()
}

export async function exportImage(emailId) {
  const res = await fetch(`${BASE}/export/image/${emailId}`, { headers: projectHeaders() })
  if (!res.ok) throw new Error('Export failed')
  return res.blob()
}

export async function exportImagesZip(body) {
  const res = await fetch(`${BASE}/export/images`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...projectHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error('Export failed')
  return res.blob()
}

export async function deleteEmail(id) {
  const res = await request(`/emails/${id}`, { method: 'DELETE' })
  return res.json()
}

export async function fetchStats() {
  const res = await request('/stats')
  return res.json()
}

export async function fetchForensics(emailId) {
  const res = await request(`/emails/${emailId}/forensics`)
  return res.json()
}

export async function scanSuspicious(page = 1, perPage = 100) {
  const res = await request(`/emails/scan-suspicious?page=${page}&per_page=${perPage}`)
  return res.json()
}

export async function fetchStatistics() {
  const res = await request('/statistics')
  return res.json()
}

// ── Scanner (persistent) ──

export async function startScan() {
  const res = await request('/emails/scan/start', { method: 'POST' })
  return res.json()
}

export async function stopScan() {
  const res = await request('/emails/scan/stop', { method: 'POST' })
  return res.json()
}

export async function getScanStatus() {
  const res = await request('/emails/scan/status')
  return res.json()
}

export async function getScanResults(params = {}) {
  const qs = new URLSearchParams(params).toString()
  const res = await request(`/emails/scan/results?${qs}`)
  return res.json()
}

// ── YARA ──

export async function uploadYaraRules(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE}/emails/yara/upload`, {
    method: 'POST',
    headers: projectHeaders(),
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'YARA upload failed')
  }
  return res.json()
}

export async function getYaraStatus() {
  const res = await request('/emails/yara/status')
  return res.json()
}

export async function clearYaraRules() {
  const res = await request('/emails/yara', { method: 'DELETE' })
  return res.json()
}

// ── Projects ──

export async function listProjects() {
  const res = await request('/projects')
  return res.json()
}

export async function createProject(name) {
  const res = await request('/projects', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
  return res.json()
}

export async function deleteProject(slug) {
  const res = await request(`/projects/${slug}`, { method: 'DELETE' })
  return res.json()
}

export async function resetProject(slug) {
  const res = await request(`/projects/${slug}/reset`, { method: 'POST' })
  return res.json()
}

export async function activateProject(slug) {
  const res = await request(`/projects/${slug}/activate`, { method: 'POST' })
  return res.json()
}

export async function getActiveProjectApi() {
  const res = await request('/projects/active')
  return res.json()
}

// ── Activity Log ──

export async function fetchActivityLogs(params = {}) {
  const qs = new URLSearchParams(params).toString()
  const res = await request(`/activity?${qs}`)
  return res.json()
}

export async function clearActivityLogs() {
  const res = await request('/activity', { method: 'DELETE' })
  return res.json()
}

export function createActivityStream() {
  const url = `${BASE}/activity/stream`
  return new EventSource(url)
}

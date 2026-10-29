async function j(res) {
  let data
  try { data = await res.json() } catch { throw new Error(`HTTP ${res.status}`) }
  if (!res.ok || data.ok === false) throw new Error(data.detail || data.reason || `HTTP ${res.status}`)
  return data
}

export const api = {
  list: () => fetch('/api/projects').then(j),
  add: (repo_url) => fetch('/api/projects', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url })
  }).then(j),
  report: (id) => fetch(`/api/projects/${id}/report`).then(j),
  refresh: (id, force = false) => fetch(`/api/projects/${id}/refresh?force=${force}`, { method: 'POST' }).then(j),
  analyze: (id) => fetch(`/api/projects/${id}/analyze`, { method: 'POST' }).then(j),
  search: (q, project_id) =>
    fetch(`/api/search?q=${encodeURIComponent(q)}${project_id ? `&project_id=${project_id}` : ''}`).then(j),
  cite: (snapshot_id, cite) =>
    fetch(`/api/cite?snapshot_id=${snapshot_id}&cite=${encodeURIComponent(cite)}`).then(j),
  share: (token) => fetch(`/api/share/${token}`).then(j)
}

import axios from 'axios'

const base = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8080'

export async function fetchUsers(page = 1, size = 20) {
  const { data } = await axios.get(`${base}/api/users`, { params: { page, size } })
  return data
}

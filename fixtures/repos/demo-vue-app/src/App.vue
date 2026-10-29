<script setup>
import { onMounted, ref } from 'vue'
import { fetchUsers } from './api.js'

const users = ref([])
const page = ref(1)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await fetchUsers(page.value)
    users.value = res.items
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <main>
    <h1>用户列表</h1>
    <table>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td>{{ u.id }}</td>
          <td>{{ u.name }}</td>
        </tr>
      </tbody>
    </table>
    <button @click="page++; load()" :disabled="loading">下一页</button>
  </main>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import Library from './views/Library.vue'
import Report from './views/Report.vue'
import Search from './views/Search.vue'
import { api } from './api.js'

const route = ref(parse(location.hash))
const repoUrl = ref('')
const busy = ref(false)
const err = ref('')

function parse(hash) {
  const raw = (hash || '').replace(/^#\/?/, '')
  const [name, id] = raw.split('/')
  if (name === 'report' && id) return { name: 'report', id }
  if (name === 'search') return { name: 'search' }
  return { name: 'library' }
}
function go(name, id) {
  location.hash = name === 'report' ? `#/report/${id}` : `#/${name}`
}
function onHash() { route.value = parse(location.hash) }

onMounted(() => window.addEventListener('hashchange', onHash))
onUnmounted(() => window.removeEventListener('hashchange', onHash))

async function add() {
  const url = repoUrl.value.trim()
  if (!url || busy.value) return
  busy.value = true; err.value = ''
  try {
    const res = await api.add(url)
    repoUrl.value = ''
    go('report', res.project.id)
  } catch (e) {
    err.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <header class="topbar">
    <div class="brand" @click="go('library')">
      <div class="glyph">脉</div>
      <b>脉络</b>
      <small>开源项目的接手说明书</small>
    </div>
    <nav class="nav">
      <button :class="{ on: route.name === 'library' }" @click="go('library')">公开库</button>
      <button :class="{ on: route.name === 'search' }" @click="go('search')">检索</button>
    </nav>
    <div class="spacer"></div>
    <div class="addbox">
      <input v-model="repoUrl" placeholder="粘贴 GitHub 仓库链接，回车生成报告" style="width: 330px"
             @keyup.enter="add" :disabled="busy" />
      <button class="btn primary" @click="add" :disabled="busy || !repoUrl.trim()">
        {{ busy ? '索引中…' : '投入仓库' }}
      </button>
    </div>
  </header>
  <div v-if="err" class="page"><div class="error">⚠ {{ err }}</div></div>
  <Library v-if="route.name === 'library'" @open="(id) => go('report', id)" />
  <Report v-else-if="route.name === 'report'" :id="route.id" @back="go('library')" />
  <Search v-else />
</template>

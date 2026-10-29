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
  <header class="masthead">
    <div class="masthead-inner">
      <div class="wordmark" @click="go('library')">
        <b>脉络</b><span>MAILUO / HANDOVER DOSSIER</span>
      </div>
      <nav class="nav">
        <a :aria-current="route.name === 'library' ? 'page' : null" @click="go('library')">公开库</a>
        <a :aria-current="route.name === 'search' ? 'page' : null" @click="go('search')">检索</a>
      </nav>
      <div class="take-in">
        <input class="field" v-model="repoUrl" :disabled="busy"
               placeholder="github.com/owner/repo · 回车投入"
               aria-label="仓库链接" @keyup.enter="add" />
        <button class="btn btn-accent" @click="add" :disabled="busy || !repoUrl.trim()">
          {{ busy ? '索引中…' : '投入仓库' }}
        </button>
      </div>
    </div>
  </header>

  <div v-if="err" class="shell">
    <div class="state error"><h3>接入失败</h3><p>{{ err }}</p></div>
  </div>

  <Library v-if="route.name === 'library'" @open="(id) => go('report', id)" />
  <Report v-else-if="route.name === 'report'" :id="route.id" @back="go('library')" />
  <Search v-else />

  <footer class="colophon">
    <span>脉络 mailuo · 一个仓库只索引一次，每晚 00:00 保鲜</span>
    <span>模板 v1 · 12 槽位 · 引用回查 100% · MIT</span>
  </footer>
</template>

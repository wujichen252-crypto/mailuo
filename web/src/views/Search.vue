<script setup>
import { onMounted, ref, computed } from 'vue'
import { api } from '../api.js'

const q = ref('')
const projectId = ref('')
const results = ref([])
const meta = ref(null)
const loading = ref(false)
const err = ref('')
const projects = ref([])

onMounted(async () => {
  try { projects.value = (await api.list()).items } catch { /* 忽略 */ }
})

async function run() {
  if (!q.value.trim() || loading.value) return
  loading.value = true; err.value = ''; results.value = []; meta.value = null
  try {
    const res = await api.search(q.value.trim(), projectId.value || undefined)
    results.value = res.results
    meta.value = res
  } catch (e) { err.value = e.message } finally { loading.value = false }
}

const highlighted = computed(() => (text) => {
  const toks = q.value.trim().split(/\s+/).filter((t) => t.length >= 2)
  let out = text || ''
  for (const t of toks) {
    out = out.replaceAll(t, `\u0001${t}\u0002`)
  }
  return out
})
</script>

<template>
  <main class="page">
    <h2 style="margin:0 0 6px;font-size:18px">检索</h2>
    <p class="hint" style="margin:0 0 16px">
      搜的是我们自建的索引（文件块 + 符号），每条结果都带 <code>path#Lx-Ly</code> —— 可点开核对原文。
    </p>

    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px">
      <input v-model="q" placeholder="例如：怎么跑起来 / 配置在哪 / 数据库迁移" style="flex:1;min-width:280px"
             @keyup.enter="run" />
      <select v-model="projectId" style="background:var(--bg-soft);border:1px solid var(--line);color:var(--ink);border-radius:10px;padding:9px 10px">
        <option value="">全部项目</option>
        <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
      <button class="btn primary" @click="run" :disabled="loading">{{ loading ? '检索中…' : '检索' }}</button>
    </div>

    <div v-if="err" class="error">⚠ {{ err }}</div>
    <div v-if="meta" class="hint" style="margin-bottom:12px">
      意图 {{ meta.intent }} · {{ meta.hits }} 条 · {{ meta.latency_ms }}ms
    </div>

    <div class="results">
      <div v-for="(r, i) in results" :key="i" class="card result">
        <div class="head">
          <span class="path">{{ r.cited }}</span>
          <span v-if="r.project" class="chip">{{ r.project }}</span>
          <span class="chip">{{ r.lang }}</span>
          <span class="chip">score {{ r.score }}</span>
        </div>
        <div class="snip" v-html="highlighted(r.snippet).replace(/\u0001/g, '<mark>').replace(/\u0002/g, '</mark>')"></div>
      </div>
    </div>
    <div v-if="!loading && meta && !results.length" class="empty">没有命中。换一个说法，或者确认该项目已索引。</div>
  </main>
</template>

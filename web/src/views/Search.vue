<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'

const q = ref('')
const projectId = ref('')
const results = ref([])
const meta = ref(null)
const loading = ref(false)
const err = ref('')
const projects = ref([])
const picked = ref(null)

onMounted(async () => {
  try { projects.value = (await api.list()).items } catch { /* 忽略 */ }
})

async function run() {
  if (!q.value.trim() || loading.value) return
  loading.value = true; err.value = ''; results.value = []; meta.value = null; picked.value = null
  try {
    const res = await api.search(q.value.trim(), projectId.value || undefined)
    results.value = res.results
    meta.value = res
  } catch (e) { err.value = e.message } finally { loading.value = false }
}

function pick(r, i) {
  picked.value = { cite: r.cited, snippet: r.snippet, project: r.project || '', score: r.score, index: i + 1 }
}

function marked(text) {
  const toks = q.value.trim().split(/\s+/).filter((t) => t.length >= 2)
  let out = text || ''
  for (const t of toks) out = out.replaceAll(t, `\u0001${t}\u0002`)
  return out
}
const no = (i) => String(i + 1).padStart(2, '0')
</script>

<template>
  <main class="shell">
    <div class="page-head">
      <div>
        <p class="eyebrow">LOOKUP / 检索</p>
        <h1>查索引，不查代码</h1>
        <p class="dek">搜的是我们自建的索引（文件块 + 符号）。中文问题会先做术语扩展再召回，每条结果都带行号。</p>
      </div>
      <div class="aside">
        {{ meta ? `${meta.hits} 条 · ${meta.latency_ms}ms · 意图 ${meta.intent}` : '等待提问' }}
      </div>
    </div>

    <div class="lookup">
      <input v-model="q" placeholder="配置在哪 · 中间件怎么挂 · 数据库迁移" aria-label="检索问题"
             @keyup.enter="run" />
      <select v-model="projectId" aria-label="检索范围">
        <option value="">全部仓库</option>
        <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
      <button class="btn" @click="run" :disabled="loading">{{ loading ? '检索中…' : '检索' }}</button>
    </div>

    <div v-if="err" class="state error"><h3>检索失败</h3><p>{{ err }}</p></div>

    <div v-if="!meta && !loading && !err" class="state">
      <h3>问一句就能定位</h3>
      <p>例如「配置在哪」「中间件怎么挂」「怎么跑起来」。命中结果会给到 <code style="font-family:var(--mono)">path#Lx-Ly</code>，点开就看原文。</p>
    </div>

    <div v-if="results.length" class="report-grid" style="grid-template-columns:minmax(0,1fr) 392px">
      <div>
        <div v-for="(r, i) in results" :key="i" class="result" @click="pick(r, i)">
          <div class="n">{{ no(i) }}</div>
          <div>
            <div class="path">{{ r.cited }}</div>
            <div class="snip" v-html="marked(r.snippet).replace(/\u0001/g, '<mark>').replace(/\u0002/g, '</mark>')"></div>
          </div>
          <div class="meta">
            <span v-if="r.project">{{ r.project }}</span><br />
            {{ r.lang }}<br />
            {{ r.score }}
          </div>
        </div>
      </div>

      <aside class="evidence">
        <div class="label">Evidence / 原文</div>
        <template v-if="picked">
          <div class="cite-line">{{ picked.cite }}</div>
          <div class="verify">✓ 命中第 {{ picked.index }} 条 · 得分 {{ picked.score }}</div>
          <pre>{{ picked.snippet }}</pre>
        </template>
        <div v-else class="empty">点左侧任意一条，原文会出现在这里。</div>
      </aside>
    </div>
  </main>
</template>

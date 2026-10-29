<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api.js'

const emit = defineEmits(['open'])
const items = ref([])
const loading = ref(true)
const err = ref('')

async function load() {
  loading.value = true; err.value = ''
  try {
    const res = await api.list()
    items.value = res.items
  } catch (e) { err.value = e.message } finally { loading.value = false }
}
onMounted(load)

const langChips = (p) => Object.keys(p.languages || {}).slice(0, 3)
const pct = (v) => (v == null ? '–' : Math.round(v * 100) + '%')
</script>

<template>
  <main class="page">
    <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:18px">
      <h2 style="margin:0;font-size:18px">公开库</h2>
      <span class="hint">一个仓库只索引一次，每晚自动保鲜</span>
      <button class="btn" style="margin-left:auto" @click="load">刷新列表</button>
    </div>

    <div v-if="loading" class="loading">正在读取…</div>
    <div v-else-if="err" class="error">⚠ {{ err }}</div>
    <div v-else-if="!items.length" class="empty">
      还没有项目。把仓库链接粘到右上角，30 秒后这里就会出现一份可核查的报告。
    </div>

    <div v-else class="grid">
      <div v-for="p in items" :key="p.id" class="card clickable" @click="emit('open', p.id)">
        <h3>{{ p.name }}
          <span class="chip" :class="{ ok: p.has_report }">{{ p.has_report ? '报告就绪' : '未分析' }}</span>
        </h3>
        <div class="sub">{{ p.repo_url || '本地目录 · ' + p.local_path }}</div>
        <div class="chips">
          <span v-for="l in langChips(p)" :key="l" class="chip">{{ l }}</span>
          <span class="chip">{{ p.chunks }} chunk</span>
          <span v-if="p.head_sha" class="chip">{{ p.head_sha.slice(0, 7) }}</span>
        </div>
        <div class="metrics">
          <div class="metric"><b>{{ p.metrics?.slot_hit ?? '–' }}/11</b>槽位</div>
          <div class="metric"><b>{{ pct(p.metrics?.cite_resolve_rate) }}</b>引用可回查</div>
          <div class="metric"><b>{{ p.metrics?.grey_claims ?? 0 }}</b>推测句</div>
        </div>
      </div>
    </div>
  </main>
</template>

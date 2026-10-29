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
    items.value = (await api.list()).items
  } catch (e) { err.value = e.message } finally { loading.value = false }
}
onMounted(load)

const tagsOf = (p) => Object.keys(p.languages || {}).filter((l) => l !== 'Other').slice(0, 3)
const pct = (v) => (v == null ? '—' : Math.round(v * 100) + '%')
const no = (i) => String(i + 1).padStart(3, '0')
</script>

<template>
  <main class="shell">
    <div class="page-head">
      <div>
        <p class="eyebrow">INDEX / 公开库</p>
        <h1>仓库台账</h1>
        <p class="dek">每个仓库只索引一次，报告对应创建时的 HEAD；每晚 00:00 自动重分析，sha 未变的仓库直接跳过。</p>
      </div>
      <div class="aside">
        条目 {{ items.length }}<br />
        模板 v1 · 12 槽位<br />
        <button class="btn btn-quiet" style="margin-top:10px" @click="load">刷新台账</button>
      </div>
    </div>

    <div v-if="loading" class="skeleton"><i></i><i></i><i></i></div>

    <div v-else-if="err" class="state error">
      <h3>读取失败</h3><p>{{ err }}</p>
    </div>

    <div v-else-if="!items.length" class="state">
      <h3>台账是空的</h3>
      <p>把 GitHub 仓库链接粘到右上角，几十秒后这里会出现一条记录，以及一份可以逐句核查的接手说明书。</p>
    </div>

    <div v-else class="ledger">
      <div class="ledger-head">
        <span>No.</span><span>仓库 / 接手说明书</span><span>构成</span><span>核验</span>
      </div>
      <div v-for="(p, i) in items" :key="p.id" class="entry" @click="emit('open', p.id)">
        <div class="no">{{ no(i) }}</div>
        <div>
          <h2>{{ p.name }}
            <span class="tag" :class="{ ok: p.has_report }">{{ p.has_report ? '报告就绪' : '待分析' }}</span>
          </h2>
          <div class="sub">{{ p.source_kind === 'local' ? '本地导入 · 样例仓库' : p.repo_url }}</div>
          <div class="tags">
            <span v-for="l in tagsOf(p)" :key="l" class="tag">{{ l }}</span>
            <span class="tag">{{ p.chunks }} chunk</span>
            <span v-if="p.head_sha" class="tag">{{ p.head_sha.slice(0, 7) }}</span>
          </div>
        </div>
        <div class="stat-row" style="align-self:center">
          <div class="stat"><b>{{ p.metrics?.slot_hit ?? '—' }}/11</b>槽位</div>
          <div class="stat"><b>{{ pct(p.metrics?.cite_resolve_rate) }}</b>引用可回查</div>
          <div class="stat"><b>{{ p.metrics?.grey_claims ?? 0 }}</b>推测句</div>
        </div>
        <div class="go" style="align-self:center">阅读报告 →</div>
      </div>
    </div>
  </main>
</template>

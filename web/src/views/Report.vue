<script setup>
import { ref, watch, onMounted } from 'vue'
import { api } from '../api.js'
import CitationDrawer from '../components/CitationDrawer.vue'

const props = defineProps({ id: { type: String, required: true } })
const emit = defineEmits(['back'])

const report = ref(null)
const loading = ref(true)
const err = ref('')
const busy = ref(false)
const drawer = ref(null)

async function load() {
  loading.value = true; err.value = ''
  try {
    const res = await api.report(props.id)
    report.value = res.report
  } catch (e) { err.value = e.message } finally { loading.value = false }
}
onMounted(load)
watch(() => props.id, load)

async function refresh() {
  busy.value = true
  try {
    await api.refresh(props.id, true)
    await load()
  } catch (e) { err.value = e.message } finally { busy.value = false }
}

const pct = (v) => (v == null ? '–' : Math.round(v * 100) + '%')
const open = (cite) => { drawer.value = { snapshot: report.value.snapshot_id, cite } }
</script>

<template>
  <main class="page">
    <button class="btn" @click="emit('back')">← 返回公开库</button>

    <div v-if="loading" class="loading" style="margin-top:20px">正在生成/读取报告…</div>
    <div v-else-if="err" class="error" style="margin-top:20px">⚠ {{ err }}</div>

    <template v-else-if="report">
      <div class="report-head" style="margin-top:18px">
        <div>
          <h1>{{ report.project }}</h1>
          <div class="sub">
            模板 {{ report.template_version }} · 填槽 {{ report.model }} · 快照 {{ report.snapshot_id }}
          </div>
        </div>
        <div class="strip">
          <div class="metric"><b>{{ report.metrics.slot_hit }}/{{ report.metrics.slot_total }}</b>槽位命中</div>
          <div class="metric"><b>{{ pct(report.metrics.cite_resolve_rate) }}</b>引用可回查</div>
          <div class="metric"><b>{{ pct(report.metrics.evidence_rate) }}</b>有证据</div>
          <div class="metric"><b>{{ report.metrics.grey_claims }}</b>推测句</div>
          <div class="metric"><b>{{ report.metrics.findings }}</b>障碍点</div>
          <button class="btn" @click="refresh" :disabled="busy">{{ busy ? '重算中…' : '重新分析' }}</button>
        </div>
      </div>

      <div class="bar" style="margin-bottom:18px">
        <i :style="{ width: (report.metrics.slot_hit / report.metrics.slot_total * 100) + '%' }"></i>
      </div>

      <section v-for="(s, i) in report.sections" :key="s.id" class="card section">
        <div class="title">
          <span class="idx">{{ String(i + 1).padStart(2, '0') }}</span>
          <h3>{{ s.title }}</h3>
          <span v-if="s.missing" class="chip mid">信息缺失</span>
        </div>
        <div v-if="!s.claims.length" class="hint">这一槽位证据不足，已列入底部“信息缺失清单”。</div>
        <div v-for="(c, j) in s.claims" :key="j" class="claim" :class="{ grey: c.confidence === 'inferred' }">
          <div class="text">
            {{ c.text }}
            <span v-if="c.confidence === 'inferred'" class="tag">AI 推测 · 无证据</span>
          </div>
          <div class="cites">
            <span v-for="cite in c.citations" :key="cite" class="cite" @click="open(cite)">{{ cite }}</span>
          </div>
        </div>
      </section>

      <section v-if="report.gaps.length" class="card section">
        <div class="title"><span class="idx">✳</span><h3>信息缺失清单</h3></div>
        <div v-for="g in report.gaps" :key="g.section" class="claim">
          <div class="text"><b>{{ g.title }}</b> —— {{ g.reason }}</div>
        </div>
      </section>
    </template>

    <CitationDrawer v-if="drawer" :snapshot="drawer.snapshot" :cite="drawer.cite" @close="drawer = null" />
  </main>
</template>

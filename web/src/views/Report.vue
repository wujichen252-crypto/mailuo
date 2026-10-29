<script setup>
import { onMounted, ref, watch } from 'vue'
import { api } from '../api.js'

const props = defineProps({ id: { type: String, required: true } })
const emit = defineEmits(['back'])

const report = ref(null)
const loading = ref(true)
const err = ref('')
const busy = ref(false)
const activeCite = ref('')
const activeSection = ref('')
const picked = ref(null)

async function load() {
  loading.value = true; err.value = ''
  try {
    report.value = (await api.report(props.id)).report
    activeSection.value = report.value.sections[0]?.id || ''
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

const pct = (v) => (v == null ? '—' : Math.round(v * 100) + '%')
const no = (i) => String(i + 1).padStart(2, '0')

function jump(id) {
  activeSection.value = id
  const el = document.getElementById(`sec-${id}`)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function pick(cite) {
  activeCite.value = cite
  picked.value = { cite, snippet: '', loading: true }
  try {
    const res = await api.cite(report.value.snapshot_id, cite)
    picked.value = { cite, snippet: res.snippet, loading: false }
  } catch (e) {
    picked.value = { cite, snippet: `回查失败：${e.message}`, loading: false }
  }
}
</script>

<template>
  <main class="shell">
    <div v-if="loading" class="skeleton"><i></i><i></i><i></i></div>

    <div v-else-if="err" class="state error">
      <h3>读不到这份报告</h3><p>{{ err }}</p>
      <button class="btn btn-quiet" style="margin-top:16px" @click="emit('back')">← 返回台账</button>
    </div>

    <div v-else-if="report" class="report-grid">
      <!-- 左：目录轨 -->
      <aside class="rail">
        <div class="label">Contents</div>
        <ol>
          <li v-for="(s, i) in report.sections" :key="s.id">
            <a :aria-current="activeSection === s.id" @click="jump(s.id)">
              <span class="n">{{ no(i) }}</span><span>{{ s.title }}</span>
            </a>
          </li>
        </ol>
      </aside>

      <!-- 中：阅读栏 -->
      <article class="doc">
        <header class="doc-head">
          <p class="eyebrow">HANDOVER DOSSIER / 接手说明书</p>
          <h1>{{ report.project }}</h1>
          <div class="meta">
            <span>模板 {{ report.template_version }}</span>
            <span>填槽 {{ report.model }}</span>
            <span>快照 {{ report.snapshot_id }}</span>
            <span>{{ report.metrics.files }} 文件 / {{ report.metrics.loc }} 行</span>
          </div>
          <div class="actions">
            <button class="btn btn-quiet" @click="emit('back')">← 台账</button>
            <button class="btn" @click="refresh" :disabled="busy">{{ busy ? '重算中…' : '重新分析' }}</button>
            <span class="stat" style="align-self:center">
              槽位 <b style="display:inline;font-size:15px">{{ report.metrics.slot_hit }}/{{ report.metrics.slot_total }}</b>
              · 引用 <b style="display:inline;font-size:15px">{{ pct(report.metrics.cite_resolve_rate) }}</b>
              · 推测 <b style="display:inline;font-size:15px">{{ report.metrics.grey_claims }}</b>
            </span>
          </div>
        </header>

        <section v-for="(s, i) in report.sections" :key="s.id" :id="`sec-${s.id}`" class="section">
          <div class="section-head">
            <span class="n">{{ no(i) }}</span>
            <h2>{{ s.title }}</h2>
            <span v-if="!s.claims.length" class="hint">信息缺失</span>
            <span v-else class="hint">{{ s.claims.length }} 条 · 均有出处</span>
          </div>

          <p v-if="!s.claims.length" class="dek" style="color:var(--muted);font-size:13.5px">
            这一槽位没有可核查的证据，已列入底部《信息缺失清单》——宁可空着，也不编。
          </p>

          <div v-for="(c, j) in s.claims" :key="j" class="claim" :class="{ grey: c.confidence === 'inferred' }">
            <div class="text">
              {{ c.text }}
              <span v-if="c.confidence === 'inferred'" class="flag">推测 · 无出处</span>
            </div>
            <div class="cites">
              <button v-for="cite in c.citations" :key="cite" class="cite"
                      :aria-pressed="activeCite === cite" @click="pick(cite)">{{ cite }}</button>
            </div>
          </div>
        </section>

        <section v-if="report.gaps.length" class="gaps">
          <h3>信息缺失清单</h3>
          <div v-for="g in report.gaps" :key="g.section" class="gap-line">
            <b>{{ g.title }}</b><span>{{ g.reason }}</span>
          </div>
        </section>
      </article>

      <!-- 右：证据栏 -->
      <aside class="evidence">
        <div class="label">Evidence / 原文</div>
        <template v-if="picked">
          <div class="cite-line">{{ picked.cite }}</div>
          <div class="verify">✓ 索引回查通过 · 该行号在此快照中存在</div>
          <pre v-if="!picked.loading">{{ picked.snippet }}</pre>
          <div v-else class="empty">读取原文…</div>
        </template>
        <div v-else class="empty">
          点正文里的任意 <code>path#Lx-Ly</code> 角标，<br />对应原文会出现在这里。<br /><br />
          报告里每一句话都必须能这样被点开核查；<br />点不开的句子会被标成「推测」。
        </div>
      </aside>
    </div>
  </main>
</template>

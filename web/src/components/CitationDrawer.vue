<script setup>
import { onMounted, ref, watch } from 'vue'
import { api } from '../api.js'

const props = defineProps({
  snapshot: { type: String, required: true },
  cite: { type: String, required: true }
})
const emit = defineEmits(['close'])

const body = ref('')
const loading = ref(true)
const err = ref('')

async function load() {
  loading.value = true; err.value = ''
  try {
    const res = await api.cite(props.snapshot, props.cite)
    body.value = res.snippet
  } catch (e) { err.value = e.message } finally { loading.value = false }
}
onMounted(load)
watch(() => props.cite, load)
</script>

<template>
  <aside class="drawer">
    <header>
      <span class="cite">{{ cite }}</span>
      <span class="hint">原文（索引回查命中）</span>
      <button class="btn close" @click="emit('close')">关闭</button>
    </header>
    <div v-if="loading" class="loading" style="padding:16px">读取原文…</div>
    <div v-else-if="err" class="error" style="padding:16px">⚠ {{ err }}</div>
    <pre v-else>{{ body }}</pre>
  </aside>
</template>

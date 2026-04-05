<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  batchTranslate,
  getEngines,
  getTestCases,
  translate,
  type EngineName,
  type EngineResult,
  type TestCase,
  type TranslateResponse,
} from './services/api'

const text = ref('这个问题有点难搞。')
const srcLang = ref('zh')
const tgtLang = ref('en')
const reference = ref('This problem is a bit tricky.')

const loading = ref(false)
const batchLoading = ref(false)
const error = ref('')
const batchError = ref('')

const engineOptions: EngineName[] = ['rbmt', 'smt', 'nmt', 'transformer', 'llm_api']
const selectedEngines = ref<EngineName[]>(['rbmt', 'nmt', 'llm_api'])
const engineStatus = ref<Record<string, { ready: boolean; message: string }>>({})

const results = ref<EngineResult[]>([])
const batchResults = ref<TranslateResponse[]>([])

const testCases = ref<TestCase[]>([])
const selectedCase = ref('')

const canRun = computed(() => text.value.trim().length > 0 && selectedEngines.value.length > 0)
const canRunBatch = computed(() => testCases.value.length > 0 && selectedEngines.value.length > 0)

const readyEngineCount = computed(() =>
  Object.values(engineStatus.value).filter((item) => item.ready).length,
)

const selectedReadyCount = computed(
  () => selectedEngines.value.filter((name) => engineStatus.value[name]?.ready).length,
)

const batchRows = computed(() => {
  return batchResults.value.flatMap((item, index) => {
    const caseItem = testCases.value[index]
    const caseLabel = caseItem ? caseItem.id : `case_${index + 1}`
    return item.results.map((result) => ({
      caseLabel,
      source: item.text,
      engine: result.engine,
      translation: result.translation,
      latencyMs: result.latency_ms,
      bleu: result.bleu,
      chrf: result.chrf,
      status: result.ready ? 'ok' : result.error || 'not ready',
      ready: result.ready,
    }))
  })
})

const toggleEngine = (engine: EngineName) => {
  if (selectedEngines.value.includes(engine)) {
    selectedEngines.value = selectedEngines.value.filter((item) => item !== engine)
    return
  }
  selectedEngines.value = [...selectedEngines.value, engine]
}

const applyCase = (id: string) => {
  const hit = testCases.value.find((item) => item.id === id)
  if (!hit) {
    return
  }
  text.value = hit.source
  reference.value = hit.reference
  srcLang.value = hit.src_lang
  tgtLang.value = hit.tgt_lang
}

const refreshStatus = async () => {
  engineStatus.value = await getEngines()
}

const runTranslate = async () => {
  loading.value = true
  error.value = ''
  try {
    const data = await translate({
      text: text.value,
      src_lang: srcLang.value,
      tgt_lang: tgtLang.value,
      engines: selectedEngines.value,
      reference: reference.value.trim() ? reference.value : undefined,
    })
    results.value = data.results
  } catch (err) {
    error.value = err instanceof Error ? err.message : '请求失败'
  } finally {
    loading.value = false
  }
}

const runBatchTranslate = async () => {
  if (testCases.value.length === 0) {
    batchError.value = '没有可用测试句。'
    return
  }

  const langPairs = new Set(testCases.value.map((item) => `${item.src_lang}->${item.tgt_lang}`))
  if (langPairs.size > 1) {
    batchError.value = '批量测试仅支持同一个语言方向，请先统一测试句语种。'
    return
  }

  const first = testCases.value[0]
  batchLoading.value = true
  batchError.value = ''
  try {
    const data = await batchTranslate({
      texts: testCases.value.map((item) => item.source),
      references: testCases.value.map((item) => item.reference),
      src_lang: first.src_lang,
      tgt_lang: first.tgt_lang,
      engines: selectedEngines.value,
    })
    batchResults.value = data.items
  } catch (err) {
    batchError.value = err instanceof Error ? err.message : '批量测试请求失败'
  } finally {
    batchLoading.value = false
  }
}

const exportBatchCsv = () => {
  if (batchRows.value.length === 0) {
    return
  }

  const headers = ['case', 'source', 'engine', 'translation', 'latency_ms', 'bleu', 'chrf', 'status']
  const escapeCsv = (value: unknown) => {
    const raw = value === null || value === undefined ? '' : String(value)
    return `"${raw.replace(/"/g, '""')}"`
  }

  const lines = [
    headers.join(','),
    ...batchRows.value.map((row) =>
      [
        row.caseLabel,
        row.source,
        row.engine,
        row.translation,
        row.latencyMs,
        row.bleu ?? '',
        row.chrf ?? '',
        row.status,
      ]
        .map(escapeCsv)
        .join(','),
    ),
  ]

  const blob = new Blob([`\uFEFF${lines.join('\n')}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `mt_batch_results_${Date.now()}.csv`
  anchor.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  await refreshStatus()
  testCases.value = await getTestCases()
})
</script>

<template>
  <div class="page-shell">
    <div class="orb orb-a" />
    <div class="orb orb-b" />

    <main class="container">
      <header class="hero-card">
        <div>
          <p class="hero-kicker">Round-Corner Philosophy</p>
          <h1>MT-Lab Live · Vue Demo</h1>
          <p class="desc">多引擎机器翻译对比平台，支持本地模型与 OpenAI 兼容 API。</p>
        </div>
        <div class="hero-metrics">
          <div class="metric-card">
            <span class="metric-label">引擎在线</span>
            <strong>{{ readyEngineCount }} / {{ engineOptions.length }}</strong>
          </div>
          <div class="metric-card">
            <span class="metric-label">已选引擎</span>
            <strong>{{ selectedEngines.length }}（就绪 {{ selectedReadyCount }}）</strong>
          </div>
          <div class="metric-card">
            <span class="metric-label">测试样本</span>
            <strong>{{ testCases.length }} 条</strong>
          </div>
        </div>
      </header>

      <section class="panel glass">
        <div class="panel-head">
          <h2>翻译配置</h2>
          <button class="ghost" @click="refreshStatus">刷新引擎状态</button>
        </div>

        <div class="row">
          <div>
            <label for="caseSelector">测试句</label>
            <select id="caseSelector" v-model="selectedCase" @change="applyCase(selectedCase)">
              <option value="">手动输入</option>
              <option v-for="item in testCases" :key="item.id" :value="item.id">
                {{ item.id }} - {{ item.source }}
              </option>
            </select>
          </div>
          <div>
            <label for="srcLang">语言方向</label>
            <div class="lang-row">
              <input id="srcLang" v-model="srcLang" placeholder="zh" />
              <span>→</span>
              <input id="tgtLang" v-model="tgtLang" placeholder="en" />
            </div>
          </div>
        </div>

        <label for="text">源文本</label>
        <textarea id="text" v-model="text" rows="4" />

        <label for="reference">参考译文（可选，用于 BLEU / chrF）</label>
        <textarea id="reference" v-model="reference" rows="2" />

        <label>引擎选择</label>
        <div class="chips">
          <button
            v-for="engine in engineOptions"
            :key="engine"
            class="chip"
            :class="{ active: selectedEngines.includes(engine) }"
            @click="toggleEngine(engine)"
          >
            {{ engine }}
          </button>
        </div>

        <div class="actions">
          <button :disabled="loading || !canRun" @click="runTranslate">
            {{ loading ? '翻译中...' : '开始翻译对比' }}
          </button>
          <button class="ghost" :disabled="batchLoading || !canRunBatch" @click="runBatchTranslate">
            {{ batchLoading ? '批量测试中...' : '一键批量测试' }}
          </button>
          <button class="ghost" :disabled="batchRows.length === 0" @click="exportBatchCsv">
            导出批量 CSV
          </button>
        </div>

        <p v-if="!canRun" class="hint">请输入文本并至少选择一个引擎。</p>
        <p v-if="batchError" class="error">{{ batchError }}</p>
      </section>

      <section class="panel glass">
        <div class="panel-head">
          <h2>引擎状态</h2>
          <span class="badge">实时健康检查</span>
        </div>

        <div class="table-shell">
          <table>
            <thead>
              <tr>
                <th>Engine</th>
                <th>Ready</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(status, name) in engineStatus" :key="name">
                <td>{{ name }}</td>
                <td>
                  <span class="status-pill" :class="status.ready ? 'ok' : 'down'">
                    {{ status.ready ? 'ready' : 'not ready' }}
                  </span>
                </td>
                <td>{{ status.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel glass">
        <h2>单句翻译结果</h2>
        <p v-if="error" class="error">{{ error }}</p>
        <p v-else-if="results.length === 0" class="hint">还没有结果，点击“开始翻译对比”。</p>
        <div v-else class="table-shell">
          <table>
            <thead>
              <tr>
                <th>Engine</th>
                <th>Translation</th>
                <th>Latency (ms)</th>
                <th>BLEU</th>
                <th>chrF</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in results" :key="item.engine">
                <td>{{ item.engine }}</td>
                <td>{{ item.translation }}</td>
                <td>{{ item.latency_ms }}</td>
                <td>{{ item.bleu ?? '-' }}</td>
                <td>{{ item.chrf ?? '-' }}</td>
                <td>
                  <span class="status-pill" :class="item.ready ? 'ok' : 'down'">
                    {{ item.ready ? 'ok' : item.error || 'not ready' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel glass">
        <h2>批量测试结果</h2>
        <p v-if="batchRows.length === 0" class="hint">还没有批量结果，点击“一键批量测试”。</p>
        <div v-else class="table-shell">
          <table>
            <thead>
              <tr>
                <th>Case</th>
                <th>Source</th>
                <th>Engine</th>
                <th>Translation</th>
                <th>Latency (ms)</th>
                <th>BLEU</th>
                <th>chrF</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in batchRows" :key="`${row.caseLabel}-${row.engine}-${index}`">
                <td>{{ row.caseLabel }}</td>
                <td>{{ row.source }}</td>
                <td>{{ row.engine }}</td>
                <td>{{ row.translation }}</td>
                <td>{{ row.latencyMs }}</td>
                <td>{{ row.bleu ?? '-' }}</td>
                <td>{{ row.chrf ?? '-' }}</td>
                <td>
                  <span class="status-pill" :class="row.ready ? 'ok' : 'down'">
                    {{ row.status }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>
  </div>
</template>


<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import {
  getEngines,
  getLlmSettings,
  processLlmMultimodal,
  translate,
  type EngineName,
  type InputModality,
  type LlmSettings,
  updateLlmSettings,
} from './services/api'

type SlotState = 'empty' | 'pending' | 'ready' | 'error' | 'skipped'
type MethodLevel = 'ready' | 'download' | 'config'

interface EngineSlot {
  engine: EngineName
  state: SlotState
  translation: string
  latency_ms: number
  error?: string
  bleu?: number | null
  chrf?: number | null
  meteor?: number | null
  ter?: number | null
}

interface TranslateRecord {
  id: number
  created_at: string
  modality: InputModality
  input_preview: string
  reference?: string
  slots: EngineSlot[]
}

interface CurrentTaskInfo {
  created_at: string
  modality: InputModality
  input_preview: string
  reference?: string
}

interface MethodStatusMeta {
  ready: boolean
  level: MethodLevel
  label: string
  message: string
}

interface DemoScenario {
  id: string
  title: string
  src_lang: string
  tgt_lang: string
  text: string
  reference?: string
  note?: string
}

const demoScenarios: DemoScenario[] = [
  {
    id: 'zh-en-main',
    title: '基准句（中→英）',
    src_lang: 'zh',
    tgt_lang: 'en',
    text: '我喜欢人工智能，我对这片大地爱得深沉。',
    reference: 'I love artificial intelligence, and I deeply love this land.',
    note: '用于稳定比较五种方法的译文质量与速度。',
  },
  {
    id: 'bank-river',
    title: '歧义样例：bank（河岸）',
    src_lang: 'en',
    tgt_lang: 'zh',
    text: 'He sat on the bank and watched the river flow.',
    reference: '他坐在河岸上，看着河水流淌。',
    note: '用于验证在歧义场景中的语义判别能力。',
  },
  {
    id: 'bank-finance',
    title: '歧义样例：bank（银行）',
    src_lang: 'en',
    tgt_lang: 'zh',
    text: 'She went to the bank to deposit money.',
    reference: '她去银行存钱。',
    note: '与“河岸”样例构成对照，检验语境建模能力。',
  },
  {
    id: 'long-order',
    title: '长句语序样例',
    src_lang: 'zh',
    tgt_lang: 'en',
    text: '尽管昨晚下了很大的雨，但我们今天早上仍然按计划出发去山里进行实地调研。',
    reference:
      'Although it rained heavily last night, we still set out this morning as planned to conduct field research in the mountains.',
    note: '用于观察 NMT 与 Transformer 在长句翻译中的表现差异。',
  },
]

const seq = ref(0)
const records = ref<TranslateRecord[]>([])

const sourceText = ref('')
const referenceText = ref('')
const srcLang = ref('zh')
const tgtLang = ref('en')
const activeScenarioId = ref<string | null>(null)

const attachmentBase64 = ref('')
const attachmentMimeType = ref('')
const attachmentName = ref('')
const attachmentModality = ref<InputModality | null>(null)
const attachmentLoading = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const composerInputRef = ref<HTMLTextAreaElement | null>(null)

const loading = ref(false)
const error = ref('')

const engineOptions: EngineName[] = ['rbmt', 'nmt', 'transformer', 'llm_api']
const selectedEngines = ref<EngineName[]>(['rbmt', 'nmt', 'transformer', 'llm_api'])
const engineStatus = ref<Record<string, { ready: boolean; message: string }>>({})

const currentTaskInfo = ref<CurrentTaskInfo | null>(null)
const currentSlots = ref<EngineSlot[]>([])

const settingsLoading = ref(false)
const settingsSaving = ref(false)
const settingsError = ref('')
const llmSettingsDraft = ref<LlmSettings | null>(null)

const classifyMethodLevel = (ready: boolean, message: string): MethodLevel => {
  if (ready) return 'ready'
  const lowered = message.toLowerCase()
  if (
    lowered.includes('missing') ||
    lowered.includes('not found') ||
    lowered.includes('local model path') ||
    lowered.includes('please download') ||
    lowered.includes('moses.ini')
  ) {
    return 'download'
  }
  return 'config'
}

const methodStatusMap = computed<Record<EngineName, MethodStatusMeta>>(() => {
  const output = {} as Record<EngineName, MethodStatusMeta>
  for (const engine of engineOptions) {
    const status = engineStatus.value[engine]
    if (!status) {
      output[engine] = { ready: false, level: 'config', label: '待配置', message: '状态未加载' }
      continue
    }
    const level = classifyMethodLevel(status.ready, status.message)
    const label = level === 'ready' ? '可用' : level === 'download' ? '待下载' : '待配置'
    output[engine] = { ready: status.ready, level, label, message: status.message }
  }
  return output
})

const readyEngineCount = computed(() => engineOptions.filter((name) => methodStatusMap.value[name].ready).length)
const selectedReadyCount = computed(
  () => selectedEngines.value.filter((name) => methodStatusMap.value[name].ready).length,
)

const canRun = computed(() => {
  const hasAttachment = attachmentBase64.value.trim().length > 0
  if (hasAttachment) return !attachmentLoading.value
  const hasText = sourceText.value.trim().length > 0
  return hasText && selectedReadyCount.value > 0 && !attachmentLoading.value
})

const modeSummary = computed(() =>
  attachmentModality.value
    ? `已检测到 ${attachmentModality.value} 文件，当前请求将使用 llm_api。`
    : `文本模式：已选 ${selectedReadyCount.value} 种可用方法，支持自动评测指标展示。`,
)

const activeScenario = computed(() => demoScenarios.find((item) => item.id === activeScenarioId.value) || null)

const transformerInsight = computed(() => {
  if (!currentTaskInfo.value || currentTaskInfo.value.modality !== 'text') return null
  const nmt = currentSlots.value.find((slot) => slot.engine === 'nmt' && slot.state === 'ready')
  const transformer = currentSlots.value.find((slot) => slot.engine === 'transformer' && slot.state === 'ready')

  if (!nmt && !transformer) return null
  if (nmt && transformer) {
    return {
      type: 'both',
      faster: nmt.latency_ms <= transformer.latency_ms ? 'nmt' : 'transformer',
      richer: nmt.translation.length >= transformer.translation.length ? 'nmt' : 'transformer',
    } as const
  }
  if (transformer) return { type: 'transformer_only' } as const
  return { type: 'nmt_only' } as const
})

const createEmptySlots = (): EngineSlot[] =>
  engineOptions.map((engine) => ({
    engine,
    state: 'empty',
    translation: '',
    latency_ms: 0,
    error: undefined,
    bleu: null,
    chrf: null,
    meteor: null,
    ter: null,
  }))

const resetCurrentBoard = () => {
  currentTaskInfo.value = null
  currentSlots.value = createEmptySlots()
}

const markSlotIn = (target: EngineSlot[], engine: EngineName, patch: Partial<EngineSlot>) => {
  const index = target.findIndex((slot) => slot.engine === engine)
  if (index < 0) return
  target[index] = { ...target[index], ...patch }
}

const markCurrentSlot = (engine: EngineName, patch: Partial<EngineSlot>) => {
  markSlotIn(currentSlots.value, engine, patch)
}

const stateText = (state: SlotState) => {
  if (state === 'empty') return '无数据'
  if (state === 'pending') return '处理中'
  if (state === 'ready') return '完成'
  if (state === 'error') return '失败'
  return '未启用'
}

const resultText = (slot: EngineSlot) => {
  if (slot.state === 'error' && slot.error) return `[ERROR] ${slot.error}`
  if (slot.translation) return slot.translation
  if (slot.error) return slot.error
  if (slot.state === 'empty') return '--'
  if (slot.state === 'pending') return '等待返回...'
  return '--'
}

const latencyText = (slot: EngineSlot) => (slot.latency_ms ? `${slot.latency_ms.toFixed(2)} ms` : '--')
const metricText = (value: number | null | undefined) =>
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '--'

const applyScenario = async (scenario: DemoScenario) => {
  activeScenarioId.value = scenario.id
  srcLang.value = scenario.src_lang
  tgtLang.value = scenario.tgt_lang
  sourceText.value = scenario.text
  referenceText.value = scenario.reference || ''
  clearAttachment()
  await nextTick()
  resizeComposerInput()
}

const toggleEngine = (engine: EngineName) => {
  const meta = methodStatusMap.value[engine]
  if (!meta.ready) {
    error.value = `${engine} 当前状态为${meta.label}：${meta.message}`
    return
  }
  if (selectedEngines.value.includes(engine)) {
    selectedEngines.value = selectedEngines.value.filter((item) => item !== engine)
    return
  }
  selectedEngines.value = [...selectedEngines.value, engine]
}

const syncSelectedEngines = () => {
  const readyEngines = engineOptions.filter((engine) => methodStatusMap.value[engine].ready)
  selectedEngines.value = selectedEngines.value.filter((engine) => readyEngines.includes(engine))
  if (selectedEngines.value.length === 0) selectedEngines.value = [...readyEngines]
}

const getPromptByModality = (settings: LlmSettings | null, modality: InputModality) => {
  if (!settings) return undefined
  if (modality === 'image') return settings.image_prompt
  if (modality === 'audio') return settings.audio_prompt
  if (modality === 'video') return settings.video_prompt
  return settings.text_prompt
}

const detectModalityByFile = (file: File): InputModality | null => {
  const mimeType = (file.type || '').toLowerCase()
  if (mimeType.startsWith('image/')) return 'image'
  if (mimeType.startsWith('audio/')) return 'audio'
  if (mimeType.startsWith('video/')) return 'video'

  const loweredName = file.name.toLowerCase()
  if (/\.(png|jpg|jpeg|gif|bmp|webp|heic|heif)$/.test(loweredName)) return 'image'
  if (/\.(mp3|wav|m4a|aac|flac|ogg|opus)$/.test(loweredName)) return 'audio'
  if (/\.(mp4|mov|avi|mkv|webm|m4v)$/.test(loweredName)) return 'video'
  return null
}

const resizeComposerInput = () => {
  const textarea = composerInputRef.value
  if (!textarea) return
  textarea.style.height = 'auto'
  const maxHeight = 220
  const nextHeight = Math.min(textarea.scrollHeight, maxHeight)
  textarea.style.height = `${nextHeight}px`
  textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
}

const clearAttachment = () => {
  attachmentBase64.value = ''
  attachmentMimeType.value = ''
  attachmentName.value = ''
  attachmentModality.value = null
  if (fileInputRef.value) fileInputRef.value.value = ''
}

const openFilePicker = () => {
  fileInputRef.value?.click()
}

const readAttachmentFile = async (file: File) => {
  const modality = detectModalityByFile(file)
  if (!modality) {
    clearAttachment()
    error.value = '仅支持 image / audio / video 文件。'
    return
  }

  attachmentLoading.value = true
  error.value = ''
  try {
    const reader = new FileReader()
    const content = await new Promise<string>((resolve, reject) => {
      reader.onload = () => resolve(String(reader.result || ''))
      reader.onerror = () => reject(new Error('文件读取失败'))
      reader.readAsDataURL(file)
    })
    const splitAt = content.indexOf(',')
    attachmentBase64.value = splitAt >= 0 ? content.slice(splitAt + 1) : content
    attachmentMimeType.value = file.type || 'application/octet-stream'
    attachmentName.value = file.name || 'clipboard-file'
    attachmentModality.value = modality
  } catch (exception) {
    clearAttachment()
    error.value = exception instanceof Error ? exception.message : '文件读取失败'
  } finally {
    attachmentLoading.value = false
  }
}

const onMediaFileChange = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) {
    clearAttachment()
    return
  }
  await readAttachmentFile(file)
}

const onComposerPaste = (event: ClipboardEvent) => {
  const items = event.clipboardData?.items
  if (!items || items.length === 0) return
  const fileItem = Array.from(items).find((item) => item.kind === 'file')
  if (!fileItem) return
  const file = fileItem.getAsFile()
  if (!file) return
  const modality = detectModalityByFile(file)
  if (!modality) return
  event.preventDefault()
  void readAttachmentFile(file)
}

const onComposerInput = () => {
  resizeComposerInput()
}

const refreshStatus = async () => {
  engineStatus.value = await getEngines()
  syncSelectedEngines()
}

const loadLlmSettings = async () => {
  settingsLoading.value = true
  settingsError.value = ''
  try {
    const data = await getLlmSettings()
    llmSettingsDraft.value = { ...data }
  } catch (exception) {
    settingsError.value = exception instanceof Error ? exception.message : '读取 LLM 配置失败'
  } finally {
    settingsLoading.value = false
  }
}

const saveLlmSettings = async () => {
  if (!llmSettingsDraft.value) return
  settingsSaving.value = true
  settingsError.value = ''
  try {
    const updated = await updateLlmSettings(llmSettingsDraft.value)
    llmSettingsDraft.value = { ...updated }
  } catch (exception) {
    settingsError.value = exception instanceof Error ? exception.message : '保存 LLM 配置失败'
  } finally {
    settingsSaving.value = false
  }
}

const runTextTranslate = async (rawText: string, reference: string | undefined) => {
  const selectedReady = selectedEngines.value.filter((engine) => methodStatusMap.value[engine].ready)
  const selectedSet = new Set(selectedEngines.value)

  for (const engine of engineOptions) {
    if (selectedReady.includes(engine)) {
      markCurrentSlot(engine, {
        state: 'pending',
        translation: '',
        error: undefined,
        latency_ms: 0,
        bleu: null,
        chrf: null,
        meteor: null,
        ter: null,
      })
      continue
    }
    if (selectedSet.has(engine)) {
      markCurrentSlot(engine, {
        state: 'skipped',
        translation: '',
        error: `方法未就绪：${methodStatusMap.value[engine].message}`,
        latency_ms: 0,
        bleu: null,
        chrf: null,
        meteor: null,
        ter: null,
      })
      continue
    }
    markCurrentSlot(engine, {
      state: 'skipped',
      translation: '',
      error: '未选择该方法',
      latency_ms: 0,
      bleu: null,
      chrf: null,
      meteor: null,
      ter: null,
    })
  }

  const jobs = selectedReady.map(async (engine) => {
    try {
      const data = await translate({
        text: rawText,
        src_lang: srcLang.value,
        tgt_lang: tgtLang.value,
        engines: [engine],
        reference,
      })
      const result = data.results?.[0]
      if (!result) {
        markCurrentSlot(engine, {
          state: 'error',
          error: 'empty result',
          translation: '',
          latency_ms: 0,
          bleu: null,
          chrf: null,
          meteor: null,
          ter: null,
        })
        return
      }
      markCurrentSlot(engine, {
        state: result.ready ? 'ready' : 'error',
        translation: result.translation,
        error: result.error || undefined,
        latency_ms: result.latency_ms || 0,
        bleu: result.bleu ?? null,
        chrf: result.chrf ?? null,
        meteor: null,
        ter: null,
      })
    } catch (exception) {
      markCurrentSlot(engine, {
        state: 'error',
        error: exception instanceof Error ? exception.message : '请求失败',
        translation: '',
        latency_ms: 0,
        bleu: null,
        chrf: null,
        meteor: null,
        ter: null,
      })
    }
  })

  await Promise.allSettled(jobs)
}

const runMultimodalTranslate = async (modality: InputModality, rawText: string) => {
  const llmReady = methodStatusMap.value.llm_api.ready
  for (const engine of engineOptions) {
    if (engine === 'llm_api') {
      markCurrentSlot(engine, {
        state: llmReady ? 'pending' : 'error',
        translation: '',
        error: llmReady ? undefined : `llm_api 未就绪：${methodStatusMap.value.llm_api.message}`,
        latency_ms: 0,
        bleu: null,
        chrf: null,
        meteor: null,
        ter: null,
      })
      continue
    }
    markCurrentSlot(engine, {
      state: 'skipped',
      translation: '',
      error: '当前模态仅支持 llm_api',
      latency_ms: 0,
      bleu: null,
      chrf: null,
      meteor: null,
      ter: null,
    })
  }

  if (!llmReady) return

  try {
    const data = await processLlmMultimodal({
      modality,
      text: rawText || undefined,
      src_lang: srcLang.value,
      tgt_lang: tgtLang.value,
      prompt: getPromptByModality(llmSettingsDraft.value, modality),
      media_base64: attachmentBase64.value,
      media_mime_type: attachmentMimeType.value,
    })
    markCurrentSlot('llm_api', {
      state: data.result.ready ? 'ready' : 'error',
      translation: data.result.translation,
      error: data.result.error || undefined,
      latency_ms: data.result.latency_ms || 0,
      bleu: null,
      chrf: null,
      meteor: null,
      ter: null,
    })
  } catch (exception) {
    markCurrentSlot('llm_api', {
      state: 'error',
      translation: '',
      error: exception instanceof Error ? exception.message : '请求失败',
      latency_ms: 0,
      bleu: null,
      chrf: null,
      meteor: null,
      ter: null,
    })
  }
}

const snapshotCurrentToHistory = () => {
  if (!currentTaskInfo.value) return
  records.value.unshift({
    id: ++seq.value,
    created_at: currentTaskInfo.value.created_at,
    modality: currentTaskInfo.value.modality,
    input_preview: currentTaskInfo.value.input_preview,
    reference: currentTaskInfo.value.reference,
    slots: currentSlots.value.map((slot) => ({ ...slot })),
  })
}

const runTranslate = async () => {
  if (!canRun.value || loading.value) return

  loading.value = true
  error.value = ''
  const rawText = sourceText.value.trim()
  const reference = referenceText.value.trim() || undefined
  const now = new Date().toLocaleString()
  currentSlots.value = createEmptySlots()

  try {
    if (attachmentBase64.value && attachmentModality.value) {
      const inputPreview = rawText
        ? `文件：${attachmentName.value}（${attachmentMimeType.value}）\n附加文本：${rawText}`
        : `文件：${attachmentName.value}（${attachmentMimeType.value}）`

      currentTaskInfo.value = {
        created_at: now,
        modality: attachmentModality.value,
        input_preview: inputPreview,
      }
      await runMultimodalTranslate(attachmentModality.value, rawText)
    } else {
      if (!rawText) {
        error.value = '请输入文本或上传文件。'
        return
      }
      if (selectedReadyCount.value === 0) {
        error.value = '当前未选择可用方法，请先在“文本模式方法选择”中勾选至少一种可用方法。'
        return
      }
      currentTaskInfo.value = {
        created_at: now,
        modality: 'text',
        input_preview: rawText,
        reference,
      }
      await runTextTranslate(rawText, reference)
    }

    snapshotCurrentToHistory()
    sourceText.value = ''
    clearAttachment()
    await nextTick()
    resizeComposerInput()
  } catch (exception) {
    error.value = exception instanceof Error ? exception.message : '请求失败'
  } finally {
    loading.value = false
  }
}

const onComposerEnter = (event: KeyboardEvent) => {
  if (event.isComposing) return
  event.preventDefault()
  void runTranslate()
}

onMounted(async () => {
  resetCurrentBoard()
  await refreshStatus()
  await loadLlmSettings()
  await nextTick()
  resizeComposerInput()
})
</script>

<template>
  <div class="app-shell">
    <main class="layout-grid">
      <div class="left-column">
        <section class="module-card input-module">
          <header class="module-head">
          <div>
            <h1>MT-Lab Live</h1>
            <p class="desc">{{ modeSummary }}</p>
          </div>
          <div class="metric-group">
            <span class="metric">在线引擎 {{ readyEngineCount }}/{{ engineOptions.length }}</span>
          </div>
          </header>
          <h2 class="module-title">输入区</h2>
          <div class="scenario-shell">
            <label>演示案例</label>
            <div class="scenario-list">
              <button
                v-for="scenario in demoScenarios"
                :key="scenario.id"
                class="scenario-btn"
                :class="{ active: activeScenarioId === scenario.id }"
                @click="applyScenario(scenario)"
              >
                {{ scenario.title }}
              </button>
            </div>
            <p v-if="activeScenario?.note" class="hint">{{ activeScenario.note }}</p>
          </div>

          <div class="row compact">
            <div>
              <label>源语言</label>
              <input v-model="srcLang" @keydown.enter="onComposerEnter" />
            </div>
            <div>
              <label>目标语言</label>
              <input v-model="tgtLang" @keydown.enter="onComposerEnter" />
            </div>
          </div>

          <label>参考译文（可选，用于 BLEU / chrF 计算）</label>
          <input v-model="referenceText" placeholder="如需评测 BLEU / chrF，请填写参考译文" />

          <label>文本模式方法选择</label>
          <div class="chips">
            <button
              v-for="engine in engineOptions"
              :key="engine"
              class="chip"
              :class="{
                active: selectedEngines.includes(engine),
                'chip-disabled': !methodStatusMap[engine].ready,
              }"
              @click="toggleEngine(engine)"
            >
              <span class="chip-name">{{ engine }}</span>
              <span class="chip-flag" :class="`flag-${methodStatusMap[engine].level}`">
                {{ methodStatusMap[engine].label }}
              </span>
            </button>
          </div>

          <div v-if="attachmentName" class="attachment-pill">
            <span>{{ attachmentName }} · {{ attachmentModality }}</span>
            <button class="ghost small" @click="clearAttachment">移除</button>
          </div>

          <div class="composer-box">
            <textarea
              ref="composerInputRef"
              v-model="sourceText"
              rows="1"
              placeholder="输入内容；支持粘贴图片/音频/视频文件；Enter 发送，Shift+Enter 换行"
              @input="onComposerInput"
              @paste="onComposerPaste"
              @keydown.enter.exact.prevent="onComposerEnter"
            />
            <div class="composer-footer">
              <button class="icon-btn plus-btn" :disabled="attachmentLoading || loading" @click="openFilePicker">+</button>
              <button class="icon-btn send-btn" :disabled="loading || !canRun" @click="runTranslate">&#8593;</button>
            </div>
            <input
              ref="fileInputRef"
              type="file"
              class="hidden-file"
              accept="image/*,audio/*,video/*"
              @change="onMediaFileChange"
            />
          </div>

          <p v-if="error" class="error">{{ error }}</p>
        </section>

        <section class="module-card result-module">
          <h2 class="module-title">当前任务结果表</h2>
          <p v-if="currentTaskInfo" class="hint">
            {{ currentTaskInfo.created_at }} · {{ currentTaskInfo.modality }} · {{ currentTaskInfo.input_preview }}
          </p>
          <p v-if="currentTaskInfo?.reference" class="hint">参考译文：{{ currentTaskInfo.reference }}</p>
          <div class="table-shell">
            <table class="result-table">
              <thead>
                <tr>
                  <th>方法</th>
                  <th>状态</th>
                  <th>耗时</th>
                  <th>BLEU</th>
                  <th>chrF</th>
                  <th>METEOR</th>
                  <th>TER</th>
                  <th>结果</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="slot in currentSlots" :key="`current-${slot.engine}`">
                  <td><strong>{{ slot.engine }}</strong></td>
                  <td><span class="state-badge" :class="`state-${slot.state}`">{{ stateText(slot.state) }}</span></td>
                  <td>{{ latencyText(slot) }}</td>
                  <td>{{ metricText(slot.bleu) }}</td>
                  <td>{{ metricText(slot.chrf) }}</td>
                  <td>{{ metricText(slot.meteor) }}</td>
                  <td>{{ metricText(slot.ter) }}</td>
                  <td class="result-cell">{{ resultText(slot) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="transformerInsight" class="insight-shell">
            <h2>Transformer 观察</h2>
            <p v-if="transformerInsight.type === 'both'" class="hint">
              本轮 NMT 与 Transformer 均成功。速度更快的方法为 {{ transformerInsight.faster }}，
              输出更长的方法为 {{ transformerInsight.richer }}。
            </p>
            <p v-if="transformerInsight.type === 'transformer_only'" class="hint">
              本轮仅 Transformer 成功，建议检查 NMT 模型路径与语言对配置。
            </p>
            <p v-if="transformerInsight.type === 'nmt_only'" class="hint">
              本轮仅 NMT 成功，建议检查 Transformer 模型加载状态。
            </p>
          </div>
        </section>

        <section class="module-card history-module">
          <h2 class="module-title">历史记录</h2>
          <div v-if="records.length === 0" class="hint">暂无历史记录。</div>
          <div v-else class="record-list">
            <article v-for="record in records" :key="record.id" class="record-card">
              <div class="record-head">
                <strong>#{{ record.id }} · {{ record.modality }}</strong>
                <span>{{ record.created_at }}</span>
              </div>
              <p class="record-input">{{ record.input_preview }}</p>
              <p v-if="record.reference" class="hint">参考译文：{{ record.reference }}</p>
              <div class="table-shell">
                <table class="result-table">
                  <thead>
                    <tr>
                      <th>方法</th>
                      <th>状态</th>
                      <th>耗时</th>
                      <th>BLEU</th>
                      <th>chrF</th>
                      <th>METEOR</th>
                      <th>TER</th>
                      <th>结果</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="slot in record.slots" :key="`${record.id}-${slot.engine}`">
                      <td><strong>{{ slot.engine }}</strong></td>
                      <td><span class="state-badge" :class="`state-${slot.state}`">{{ stateText(slot.state) }}</span></td>
                      <td>{{ latencyText(slot) }}</td>
                      <td>{{ metricText(slot.bleu) }}</td>
                      <td>{{ metricText(slot.chrf) }}</td>
                      <td>{{ metricText(slot.meteor) }}</td>
                      <td>{{ metricText(slot.ter) }}</td>
                      <td class="result-cell">{{ resultText(slot) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </article>
          </div>
        </section>
      </div>

      <aside class="right-column">
        <section class="panel status-panel">
          <div class="panel-head">
            <h2>引擎状态</h2>
            <button class="ghost" @click="refreshStatus">刷新</button>
          </div>
          <div class="status-list">
            <article v-for="name in engineOptions" :key="name" class="status-card">
              <div class="status-top">
                <div class="status-main">
                  <span class="status-dot" :class="methodStatusMap[name].ready ? 'dot-ready' : 'dot-error'" />
                  <strong>{{ name }}</strong>
                </div>
                <span class="status-pill" :class="methodStatusMap[name].ready ? 'pill-ready' : 'pill-error'">
                  {{ methodStatusMap[name].ready ? '可用' : '不可用' }}
                </span>
              </div>
              <p class="status-msg">{{ methodStatusMap[name].message }}</p>
            </article>
          </div>
        </section>

        <section class="panel config-panel">
          <div class="panel-head">
            <h2>LLM 配置</h2>
            <div class="actions">
              <button class="ghost" :disabled="settingsLoading" @click="loadLlmSettings">
                {{ settingsLoading ? '读取中...' : '刷新配置' }}
              </button>
              <button :disabled="settingsSaving || !llmSettingsDraft" @click="saveLlmSettings">
                {{ settingsSaving ? '保存中...' : '保存配置' }}
              </button>
            </div>
          </div>
          <p v-if="settingsError" class="error">{{ settingsError }}</p>

          <template v-if="llmSettingsDraft">
            <div class="row compact">
              <div>
                <label>text_model</label>
                <input v-model="llmSettingsDraft.text_model" />
              </div>
              <div>
                <label>image_model</label>
                <input v-model="llmSettingsDraft.image_model" />
              </div>
            </div>
            <div class="row compact">
              <div>
                <label>audio_model</label>
                <input v-model="llmSettingsDraft.audio_model" />
              </div>
              <div>
                <label>video_model</label>
                <input v-model="llmSettingsDraft.video_model" />
              </div>
            </div>
            <label>media_max_base64_chars</label>
            <input type="number" min="1024" v-model.number="llmSettingsDraft.media_max_base64_chars" />
            <label>text_prompt</label>
            <textarea v-model="llmSettingsDraft.text_prompt" rows="2" />
            <label>image_prompt</label>
            <textarea v-model="llmSettingsDraft.image_prompt" rows="2" />
            <label>audio_prompt</label>
            <textarea v-model="llmSettingsDraft.audio_prompt" rows="2" />
            <label>video_prompt</label>
            <textarea v-model="llmSettingsDraft.video_prompt" rows="2" />
          </template>
        </section>
      </aside>
    </main>
  </div>
</template>

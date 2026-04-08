import { useEffect, useMemo, useState } from 'react'
import {
  batchTranslate,
  getEngines,
  getLlmSettings,
  getTestCases,
  processLlmMultimodal,
  translate,
  type EngineName,
  type EngineResult,
  type InputModality,
  type LlmSettings,
  type TestCase,
  type TranslateResponse,
  updateLlmSettings,
} from './services/api'

const engineOptions: EngineName[] = ['rbmt', 'nmt', 'transformer', 'llm_api']

function App() {
  const [text, setText] = useState('这个问题有点难搞。')
  const [srcLang, setSrcLang] = useState('zh')
  const [tgtLang, setTgtLang] = useState('en')
  const [reference, setReference] = useState('This problem is a bit tricky.')
  const [selectedEngines, setSelectedEngines] = useState<EngineName[]>(['rbmt', 'nmt', 'llm_api'])

  const [inputModality, setInputModality] = useState<InputModality>('text')
  const [mediaUrl, setMediaUrl] = useState('')
  const [mediaBase64, setMediaBase64] = useState('')
  const [mediaMimeType, setMediaMimeType] = useState('image/png')
  const [mediaFileName, setMediaFileName] = useState('')
  const [llmPrompt, setLlmPrompt] = useState('')

  const [engineStatus, setEngineStatus] = useState<Record<string, { ready: boolean; message: string }>>({})
  const [testCases, setTestCases] = useState<TestCase[]>([])
  const [selectedCase, setSelectedCase] = useState('')
  const [llmSettings, setLlmSettings] = useState<LlmSettings | null>(null)
  const [llmSettingsDraft, setLlmSettingsDraft] = useState<LlmSettings | null>(null)

  const [results, setResults] = useState<EngineResult[]>([])
  const [batchResults, setBatchResults] = useState<TranslateResponse[]>([])

  const [loading, setLoading] = useState(false)
  const [batchLoading, setBatchLoading] = useState(false)
  const [mediaLoading, setMediaLoading] = useState(false)
  const [settingsLoading, setSettingsLoading] = useState(false)
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [error, setError] = useState('')
  const [batchError, setBatchError] = useState('')
  const [settingsError, setSettingsError] = useState('')

  const canRun = useMemo(() => {
    if (inputModality === 'text') {
      return text.trim().length > 0 && selectedEngines.length > 0
    }
    return (mediaUrl.trim().length > 0 || mediaBase64.trim().length > 0) && !mediaLoading
  }, [inputModality, mediaBase64, mediaLoading, mediaUrl, selectedEngines, text])

  const canRunBatch = useMemo(
    () => inputModality === 'text' && testCases.length > 0 && selectedEngines.length > 0,
    [inputModality, testCases, selectedEngines],
  )

  const batchRows = useMemo(() => {
    return batchResults.flatMap((item, index) => {
      const caseItem = testCases[index]
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
      }))
    })
  }, [batchResults, testCases])

  const visibleEngineStatus = useMemo(
    () =>
      engineOptions.map((name) => ({
        name,
        status: engineStatus[name] ?? { ready: false, message: '状态未加载' },
      })),
    [engineStatus],
  )

  const modalityFileAccept = useMemo(() => {
    if (inputModality === 'image') return 'image/*'
    if (inputModality === 'audio') return 'audio/*'
    if (inputModality === 'video') return 'video/*'
    return '*/*'
  }, [inputModality])

  const defaultPromptByModality = (settings: LlmSettings | null, modality: InputModality) => {
    if (!settings) return ''
    if (modality === 'image') return settings.image_prompt
    if (modality === 'audio') return settings.audio_prompt
    if (modality === 'video') return settings.video_prompt
    return settings.text_prompt
  }

  const loadLlmSettings = async () => {
    setSettingsLoading(true)
    setSettingsError('')
    try {
      const data = await getLlmSettings()
      setLlmSettings(data)
      setLlmSettingsDraft({ ...data })
      setLlmPrompt(defaultPromptByModality(data, inputModality))
    } catch (err) {
      setSettingsError(err instanceof Error ? err.message : '读取 LLM 设置失败')
    } finally {
      setSettingsLoading(false)
    }
  }

  useEffect(() => {
    const init = async () => {
      const [status, cases] = await Promise.all([getEngines(), getTestCases()])
      setEngineStatus(status)
      setTestCases(cases)
      await loadLlmSettings()
    }
    void init()
  }, [])

  useEffect(() => {
    setLlmPrompt(defaultPromptByModality(llmSettings, inputModality))
    if (inputModality === 'image' && !mediaMimeType.startsWith('image/')) {
      setMediaMimeType('image/png')
    }
    if (inputModality === 'audio' && !mediaMimeType.startsWith('audio/')) {
      setMediaMimeType('audio/mpeg')
    }
    if (inputModality === 'video' && !mediaMimeType.startsWith('video/')) {
      setMediaMimeType('video/mp4')
    }
  }, [inputModality, llmSettings, mediaMimeType])

  const onToggleEngine = (engine: EngineName) => {
    setSelectedEngines((prev) => {
      if (prev.includes(engine)) {
        return prev.filter((item) => item !== engine)
      }
      return [...prev, engine]
    })
  }

  const onApplyCase = (caseId: string) => {
    setSelectedCase(caseId)
    const hit = testCases.find((item) => item.id === caseId)
    if (!hit) {
      return
    }
    setText(hit.source)
    setReference(hit.reference)
    setSrcLang(hit.src_lang)
    setTgtLang(hit.tgt_lang)
  }

  const onRefreshStatus = async () => {
    setEngineStatus(await getEngines())
  }

  const onMediaFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      setMediaBase64('')
      setMediaFileName('')
      return
    }
    setMediaLoading(true)
    setError('')
    try {
      const content = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result || ''))
        reader.onerror = () => reject(new Error('文件读取失败'))
        reader.readAsDataURL(file)
      })
      const splitAt = content.indexOf(',')
      setMediaBase64(splitAt >= 0 ? content.slice(splitAt + 1) : content)
      setMediaMimeType(file.type || mediaMimeType)
      setMediaFileName(file.name)
    } catch (err) {
      setError(err instanceof Error ? err.message : '文件读取失败')
    } finally {
      setMediaLoading(false)
    }
  }

  const onRun = async () => {
    if (!canRun) {
      return
    }
    setLoading(true)
    setError('')
    try {
      if (inputModality !== 'text') {
        const data = await processLlmMultimodal({
          modality: inputModality,
          text: text.trim() ? text : undefined,
          src_lang: srcLang,
          tgt_lang: tgtLang,
          prompt: llmPrompt.trim() ? llmPrompt : undefined,
          media_url: mediaUrl.trim() ? mediaUrl : undefined,
          media_base64: mediaBase64.trim() ? mediaBase64 : undefined,
          media_mime_type: mediaMimeType.trim() ? mediaMimeType : undefined,
        })
        setResults([data.result])
        return
      }

      const data = await translate({
        text,
        src_lang: srcLang,
        tgt_lang: tgtLang,
        engines: selectedEngines,
        reference: reference.trim() ? reference : undefined,
      })
      setResults(data.results ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }

  const onRunBatch = async () => {
    if (!canRunBatch) {
      return
    }

    const langPairs = new Set(testCases.map((item) => `${item.src_lang}->${item.tgt_lang}`))
    if (langPairs.size > 1) {
      setBatchError('批量测试仅支持同一个语言方向，请先统一测试句语种。')
      return
    }

    const first = testCases[0]
    setBatchLoading(true)
    setBatchError('')

    try {
      const data = await batchTranslate({
        texts: testCases.map((item) => item.source),
        references: testCases.map((item) => item.reference),
        src_lang: first.src_lang,
        tgt_lang: first.tgt_lang,
        engines: selectedEngines,
      })
      setBatchResults(data.items)
    } catch (err) {
      setBatchError(err instanceof Error ? err.message : '批量请求失败')
    } finally {
      setBatchLoading(false)
    }
  }

  const onSaveLlmSettings = async () => {
    if (!llmSettingsDraft) {
      return
    }
    setSettingsSaving(true)
    setSettingsError('')
    try {
      const updated = await updateLlmSettings(llmSettingsDraft)
      setLlmSettings(updated)
      setLlmSettingsDraft({ ...updated })
      setLlmPrompt(defaultPromptByModality(updated, inputModality))
    } catch (err) {
      setSettingsError(err instanceof Error ? err.message : '保存 LLM 设置失败')
    } finally {
      setSettingsSaving(false)
    }
  }

  const onExportBatchCsv = () => {
    if (batchRows.length === 0) {
      return
    }

    const headers = ['case', 'source', 'engine', 'translation', 'latency_ms', 'bleu', 'chrf', 'status']
    const escapeCsv = (value: unknown) => {
      const raw = value === null || value === undefined ? '' : String(value)
      const escaped = raw.replace(/"/g, '""')
      return `"${escaped}"`
    }

    const lines = [
      headers.join(','),
      ...batchRows.map((row) =>
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

  return (
    <main className="container">
      <h1>MT-Lab Live · React Demo</h1>
      <p className="desc">React 前端已支持文本翻译、三类多模态输入和 LLM 设置配置。</p>

      <section className="panel">
        <div className="row">
          <div>
            <label htmlFor="caseSelector">测试句</label>
            <select
              id="caseSelector"
              value={selectedCase}
              disabled={inputModality !== 'text'}
              onChange={(event) => onApplyCase(event.target.value)}
            >
              <option value="">手动输入</option>
              {testCases.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.id} - {item.source}
                </option>
              ))}
            </select>
          </div>
          <div className="inline-end">
            <button className="ghost" onClick={onRefreshStatus}>
              刷新引擎状态
            </button>
          </div>
        </div>

        <div className="row">
          <div>
            <label htmlFor="inputModality">输入模态</label>
            <select id="inputModality" value={inputModality} onChange={(e) => setInputModality(e.target.value as InputModality)}>
              <option value="text">text（文本）</option>
              <option value="image">image（图片）</option>
              <option value="audio">audio（音频）</option>
              <option value="video">video（视频）</option>
            </select>
          </div>
          <div>
            <label htmlFor="mediaUrl">媒体 URL（可选）</label>
            <input id="mediaUrl" value={mediaUrl} onChange={(event) => setMediaUrl(event.target.value)} placeholder="https://..." />
          </div>
        </div>

        <label htmlFor="sourceText">{inputModality === 'text' ? '源文本' : '附加文字上下文（可选）'}</label>
        <textarea id="sourceText" rows={4} value={text} onChange={(event) => setText(event.target.value)} />

        {inputModality === 'text' ? (
          <>
            <label htmlFor="reference">参考译文（可选，用于 BLEU/chrF）</label>
            <textarea id="reference" rows={2} value={reference} onChange={(event) => setReference(event.target.value)} />
          </>
        ) : (
          <>
            <div className="row">
              <div>
                <label htmlFor="mediaFile">媒体文件</label>
                <input id="mediaFile" type="file" accept={modalityFileAccept} onChange={onMediaFileChange} />
                {mediaFileName && <p className="hint">已加载：{mediaFileName}</p>}
              </div>
              <div>
                <label htmlFor="mediaMime">媒体 MIME（可改）</label>
                <input
                  id="mediaMime"
                  value={mediaMimeType}
                  onChange={(event) => setMediaMimeType(event.target.value)}
                  placeholder="image/png | audio/mpeg | video/mp4"
                />
              </div>
            </div>

            <label htmlFor="llmPrompt">LLM Prompt（当前模态）</label>
            <textarea id="llmPrompt" rows={3} value={llmPrompt} onChange={(event) => setLlmPrompt(event.target.value)} />
          </>
        )}

        <div className="row">
          <div>
            <label htmlFor="srcLang">源语言</label>
            <input id="srcLang" value={srcLang} onChange={(event) => setSrcLang(event.target.value)} />
          </div>
          <div>
            <label htmlFor="tgtLang">目标语言</label>
            <input id="tgtLang" value={tgtLang} onChange={(event) => setTgtLang(event.target.value)} />
          </div>
        </div>

        {inputModality === 'text' ? (
          <>
            <label>引擎选择</label>
            <div className="chips">
              {engineOptions.map((engine) => (
                <button
                  key={engine}
                  className={`chip ${selectedEngines.includes(engine) ? 'active' : ''}`}
                  onClick={() => onToggleEngine(engine)}
                >
                  {engine}
                </button>
              ))}
            </div>
          </>
        ) : (
          <p className="hint">非文本模态固定走 `llm_api`。</p>
        )}

        <div className="actions">
          <button disabled={loading || !canRun} onClick={onRun}>
            {loading ? '处理中...' : inputModality === 'text' ? '开始翻译对比' : '开始多模态处理'}
          </button>
          <button className="ghost" disabled={batchLoading || !canRunBatch} onClick={onRunBatch}>
            {batchLoading ? '批量测试中...' : '一键批量测试'}
          </button>
          <button className="ghost" disabled={batchRows.length === 0} onClick={onExportBatchCsv}>
            导出批量 CSV
          </button>
        </div>

        {!canRun && (
          <p className="hint">{inputModality === 'text' ? '请输入文本并至少选择一个引擎。' : '请上传媒体文件或填写媒体 URL。'}</p>
        )}
        {batchError && <p className="error">{batchError}</p>}
      </section>

      <section className="panel">
        <div className="row">
          <h2>LLM 多模态设置</h2>
          <div className="inline-end">
            <div className="actions">
              <button className="ghost" disabled={settingsLoading} onClick={() => void loadLlmSettings()}>
                {settingsLoading ? '读取中...' : '刷新设置'}
              </button>
              <button disabled={settingsSaving || !llmSettingsDraft} onClick={() => void onSaveLlmSettings()}>
                {settingsSaving ? '保存中...' : '保存设置'}
              </button>
            </div>
          </div>
        </div>
        {settingsError && <p className="error">{settingsError}</p>}
        {llmSettingsDraft && (
          <>
            <div className="row">
              <div>
                <label>text_model</label>
                <input
                  value={llmSettingsDraft.text_model}
                  onChange={(e) => setLlmSettingsDraft((prev) => (prev ? { ...prev, text_model: e.target.value } : prev))}
                />
              </div>
              <div>
                <label>image_model</label>
                <input
                  value={llmSettingsDraft.image_model}
                  onChange={(e) => setLlmSettingsDraft((prev) => (prev ? { ...prev, image_model: e.target.value } : prev))}
                />
              </div>
            </div>
            <div className="row">
              <div>
                <label>audio_model</label>
                <input
                  value={llmSettingsDraft.audio_model}
                  onChange={(e) => setLlmSettingsDraft((prev) => (prev ? { ...prev, audio_model: e.target.value } : prev))}
                />
              </div>
              <div>
                <label>video_model</label>
                <input
                  value={llmSettingsDraft.video_model}
                  onChange={(e) => setLlmSettingsDraft((prev) => (prev ? { ...prev, video_model: e.target.value } : prev))}
                />
              </div>
            </div>
            <div className="row">
              <div>
                <label>media_max_base64_chars</label>
                <input
                  type="number"
                  min={1024}
                  value={llmSettingsDraft.media_max_base64_chars}
                  onChange={(e) =>
                    setLlmSettingsDraft((prev) =>
                      prev
                        ? {
                            ...prev,
                            media_max_base64_chars: Number(e.target.value || prev.media_max_base64_chars),
                          }
                        : prev,
                    )
                  }
                />
              </div>
            </div>
            <label>text_prompt</label>
            <textarea
              rows={2}
              value={llmSettingsDraft.text_prompt}
              onChange={(e) => setLlmSettingsDraft((prev) => (prev ? { ...prev, text_prompt: e.target.value } : prev))}
            />
            <label>image_prompt</label>
            <textarea
              rows={2}
              value={llmSettingsDraft.image_prompt}
              onChange={(e) => setLlmSettingsDraft((prev) => (prev ? { ...prev, image_prompt: e.target.value } : prev))}
            />
            <label>audio_prompt</label>
            <textarea
              rows={2}
              value={llmSettingsDraft.audio_prompt}
              onChange={(e) => setLlmSettingsDraft((prev) => (prev ? { ...prev, audio_prompt: e.target.value } : prev))}
            />
            <label>video_prompt</label>
            <textarea
              rows={2}
              value={llmSettingsDraft.video_prompt}
              onChange={(e) => setLlmSettingsDraft((prev) => (prev ? { ...prev, video_prompt: e.target.value } : prev))}
            />
          </>
        )}
      </section>

      <section className="panel">
        <h2>引擎状态</h2>
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>Engine</th>
                <th>Ready</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {visibleEngineStatus.map(({ name, status }) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{status.ready ? 'yes' : 'no'}</td>
                  <td>{status.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h2>{inputModality === 'text' ? '单句翻译结果' : '多模态处理结果（LLM API）'}</h2>
        {error && <p className="error">{error}</p>}
        {results.length === 0 ? (
          <p>{inputModality === 'text' ? '还没有结果，点击“开始翻译对比”。' : '还没有结果，点击“开始多模态处理”。'}</p>
        ) : (
          <div className="table-shell">
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
                {results.map((item) => (
                  <tr key={item.engine}>
                    <td>{item.engine}</td>
                    <td>{item.translation}</td>
                    <td>{item.latency_ms}</td>
                    <td>{item.bleu ?? '-'}</td>
                    <td>{item.chrf ?? '-'}</td>
                    <td>{item.ready ? 'ok' : item.error ?? 'not ready'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <h2>批量测试结果</h2>
        {batchRows.length === 0 ? (
          <p>还没有批量结果，点击“一键批量测试”。</p>
        ) : (
          <div className="table-shell">
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
                {batchRows.map((row, index) => (
                  <tr key={`${row.caseLabel}-${row.engine}-${index}`}>
                    <td>{row.caseLabel}</td>
                    <td>{row.source}</td>
                    <td>{row.engine}</td>
                    <td>{row.translation}</td>
                    <td>{row.latencyMs}</td>
                    <td>{row.bleu ?? '-'}</td>
                    <td>{row.chrf ?? '-'}</td>
                    <td>{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  )
}

export default App

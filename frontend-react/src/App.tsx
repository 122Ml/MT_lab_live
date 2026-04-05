import { useEffect, useMemo, useState } from 'react'
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

const engineOptions: EngineName[] = ['rbmt', 'smt', 'nmt', 'transformer', 'llm_api']

function App() {
  const [text, setText] = useState('这个问题有点难搞。')
  const [srcLang, setSrcLang] = useState('zh')
  const [tgtLang, setTgtLang] = useState('en')
  const [reference, setReference] = useState('This problem is a bit tricky.')
  const [selectedEngines, setSelectedEngines] = useState<EngineName[]>(['rbmt', 'nmt', 'llm_api'])

  const [engineStatus, setEngineStatus] = useState<Record<string, { ready: boolean; message: string }>>({})
  const [testCases, setTestCases] = useState<TestCase[]>([])
  const [selectedCase, setSelectedCase] = useState('')

  const [results, setResults] = useState<EngineResult[]>([])
  const [batchResults, setBatchResults] = useState<TranslateResponse[]>([])

  const [loading, setLoading] = useState(false)
  const [batchLoading, setBatchLoading] = useState(false)
  const [error, setError] = useState('')
  const [batchError, setBatchError] = useState('')

  const canRun = useMemo(() => text.trim().length > 0 && selectedEngines.length > 0, [text, selectedEngines])
  const canRunBatch = useMemo(() => testCases.length > 0 && selectedEngines.length > 0, [testCases, selectedEngines])

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

  useEffect(() => {
    const init = async () => {
      const [status, cases] = await Promise.all([getEngines(), getTestCases()])
      setEngineStatus(status)
      setTestCases(cases)
    }
    void init()
  }, [])

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

  const onRun = async () => {
    if (!canRun) {
      return
    }
    setLoading(true)
    setError('')
    try {
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
      <p className="desc">备选 React 前端，支持单句翻译、批量对比和 CSV 导出。</p>

      <section className="panel">
        <div className="row">
          <div>
            <label htmlFor="caseSelector">测试句</label>
            <select id="caseSelector" value={selectedCase} onChange={(event) => onApplyCase(event.target.value)}>
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

        <label htmlFor="sourceText">源文本</label>
        <textarea id="sourceText" rows={4} value={text} onChange={(event) => setText(event.target.value)} />

        <label htmlFor="reference">参考译文（可选，用于 BLEU/chrF）</label>
        <textarea id="reference" rows={2} value={reference} onChange={(event) => setReference(event.target.value)} />

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

        <div className="actions">
          <button disabled={loading || !canRun} onClick={onRun}>
            {loading ? '翻译中...' : '开始翻译对比'}
          </button>
          <button className="ghost" disabled={batchLoading || !canRunBatch} onClick={onRunBatch}>
            {batchLoading ? '批量测试中...' : '一键批量测试'}
          </button>
          <button className="ghost" disabled={batchRows.length === 0} onClick={onExportBatchCsv}>
            导出批量 CSV
          </button>
        </div>

        {!canRun && <p className="hint">请输入文本并至少选择一个引擎。</p>}
        {batchError && <p className="error">{batchError}</p>}
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
              {Object.entries(engineStatus).map(([name, status]) => (
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
        <h2>单句翻译结果</h2>
        {error && <p className="error">{error}</p>}
        {results.length === 0 ? (
          <p>还没有结果，点击“开始翻译对比”。</p>
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

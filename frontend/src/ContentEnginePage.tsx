import { useEffect, useState } from 'react'

type ContentTab = 'planner' | 'library' | 'templates' | 'analytics'

type ContentItem = {
  id: string
  content_type: string
  status: string
  rendered_text: string
  audience_interest_score: number | null
  internal_grade: string | null
  vqs: number | null
  feed_score: number | null
  editorial_signal: string | null
  visual_template: string | null
  creative_context: Record<string, unknown>
  visual: Record<string, unknown>
  scheduled_at: string | null
  published_at: string | null
  vacancy_id: string | null
}

type Marker = { key: string; label: string; primary_signal: string; description: string }
type Family = { key: string; layouts: string[]; active: boolean }
type AnalyticsRow = {
  key: string
  publications: number
  avg_reach: number | null
  reactions_per_1000: number | null
}

export function ContentEnginePage() {
  const [tab, setTab] = useState<ContentTab>('planner')
  const [items, setItems] = useState<ContentItem[]>([])
  const [markers, setMarkers] = useState<Marker[]>([])
  const [families, setFamilies] = useState<Family[]>([])
  const [analytics, setAnalytics] = useState<AnalyticsRow[]>([])
  const [selected, setSelected] = useState<ContentItem | null>(null)
  const [planMsg, setPlanMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function loadLibrary() {
    const res = await fetch('/api/content/items?limit=50')
    if (!res.ok) throw new Error(`items HTTP ${res.status}`)
    setItems((await res.json()) as ContentItem[])
  }

  async function loadTemplates() {
    const [m, f] = await Promise.all([
      fetch('/api/content/markers'),
      fetch('/api/content/templates'),
    ])
    if (m.ok) setMarkers((await m.json()) as Marker[])
    if (f.ok) setFamilies((await f.json()) as Family[])
  }

  async function loadAnalytics() {
    const res = await fetch('/api/content/analytics?dimension=visual_family&days=30')
    if (!res.ok) throw new Error(`analytics HTTP ${res.status}`)
    setAnalytics((await res.json()) as AnalyticsRow[])
  }

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        setError(null)
        if (tab === 'library' || tab === 'planner') await loadLibrary()
        if (tab === 'templates') await loadTemplates()
        if (tab === 'analytics') await loadAnalytics()
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'load failed')
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [tab])

  async function runPlan() {
    setBusy(true)
    setPlanMsg(null)
    try {
      const res = await fetch('/api/content/plan?city_slug=nizhny-novgorod', { method: 'POST' })
      if (!res.ok) throw new Error(`plan HTTP ${res.status}`)
      const data = (await res.json()) as {
        created: string[]
        skipped: string[]
        mix_snapshot: Record<string, number>
      }
      setPlanMsg(
        `Создано: ${data.created.length}. Пропуски: ${data.skipped.join(', ') || '—'}. Mix: ${JSON.stringify(data.mix_snapshot)}`,
      )
      await loadLibrary()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'plan failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="content-engine" data-testid="content-engine">
      <header className="page-header">
        <h1>Content Engine</h1>
        <p className="subtitle">Планировщик, библиотека, шаблоны и аналитика публикаций Радара</p>
      </header>

      <div className="content-tabs" role="tablist">
        {(
          [
            ['planner', 'Planner'],
            ['library', 'Library'],
            ['templates', 'Templates'],
            ['analytics', 'Analytics'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            className={`nav-item${tab === id ? ' active' : ''}`}
            data-testid={`content-tab-${id}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <p className="status error">{error}</p>}

      {tab === 'planner' && (
        <section className="panel">
          <h2>Content Planner</h2>
          <p>Мягкое распределение слотов внутри дневного лимита города. Подборки по умолчанию выключены флагом.</p>
          <button type="button" className="btn" disabled={busy} onClick={() => void runPlan()} data-testid="run-plan">
            Спланировать день
          </button>
          {planMsg && <p className="status ok">{planMsg}</p>}
          <table className="data-table" data-testid="planner-table">
            <thead>
              <tr>
                <th>Тип</th>
                <th>Статус</th>
                <th>Маркер</th>
                <th>Шаблон</th>
                <th>AIS</th>
              </tr>
            </thead>
            <tbody>
              {items.slice(0, 20).map((item) => (
                <tr key={item.id}>
                  <td>{item.content_type}</td>
                  <td>{item.status}</td>
                  <td>{item.editorial_signal || '—'}</td>
                  <td>{item.visual_template || '—'}</td>
                  <td>{item.audience_interest_score != null ? Math.round(item.audience_interest_score) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {tab === 'library' && (
        <section className="panel">
          <h2>Content Library</h2>
          <div className="split">
            <ul className="feed-list">
              {items.map((item) => (
                <li key={item.id}>
                  <button type="button" className="feed-row" onClick={() => setSelected(item)}>
                    <strong>{item.content_type}</strong> · {item.status}
                    <span className="muted">
                      {' '}
                      · {item.editorial_signal || '—'} · {item.visual_template || '—'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {selected && (
              <div className="preview-panel" data-testid="creative-preview">
                <h3>Creative Preview</h3>
                <p>
                  VQS {selected.vqs ?? '—'} · Feed {selected.feed_score ?? '—'} · AIS{' '}
                  {selected.audience_interest_score != null
                    ? Math.round(selected.audience_interest_score)
                    : '—'}
                  {selected.internal_grade ? ` · grade ${selected.internal_grade} (internal)` : ''}
                </p>
                <p>
                  Context: {String(selected.creative_context.creative_type || '—')} /{' '}
                  {String(selected.visual.family || '—')}
                </p>
                {selected.vacancy_id && (
                  <img
                    src={`/api/content/images/${selected.vacancy_id}`}
                    alt="Composed card"
                    className="brand-preview"
                    onError={(e) => {
                      ;(e.target as HTMLImageElement).style.display = 'none'
                    }}
                  />
                )}
                <pre className="post-preview">{selected.rendered_text || '—'}</pre>
              </div>
            )}
          </div>
        </section>
      )}

      {tab === 'templates' && (
        <section className="panel">
          <h2>Creative Templates</h2>
          <h3>Редакционные маркеры</h3>
          <ul data-testid="markers-list">
            {markers.map((m) => (
              <li key={m.key}>
                <strong>{m.label}</strong> — {m.description}
              </li>
            ))}
          </ul>
          <h3>Визуальные семейства</h3>
          <ul data-testid="families-list">
            {families.map((f) => (
              <li key={f.key}>
                {f.key} {f.active ? `(${f.layouts.join(', ')})` : '(inactive / future)'}
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === 'analytics' && (
        <section className="panel">
          <h2>Content Analytics</h2>
          <p>Только факты из VK API. Пустые метрики = данных ещё нет.</p>
          <table className="data-table" data-testid="analytics-table">
            <thead>
              <tr>
                <th>Ключ</th>
                <th>Публикаций</th>
                <th>Ср. охват</th>
                <th>Реакций / 1000</th>
              </tr>
            </thead>
            <tbody>
              {analytics.length === 0 ? (
                <tr>
                  <td colSpan={4}>Нет опубликованных материалов с метриками</td>
                </tr>
              ) : (
                analytics.map((row) => (
                  <tr key={row.key}>
                    <td>{row.key}</td>
                    <td>{row.publications}</td>
                    <td>{row.avg_reach ?? '—'}</td>
                    <td>{row.reactions_per_1000 ?? '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}

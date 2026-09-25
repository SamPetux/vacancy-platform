import { useEffect, useState } from 'react'
import './App.css'

type HealthPayload = {
  status: string
  app: string
  env: string
  version: string
}

type VacancyItem = {
  id: string
  ranked_position: number | null
  title: string | null
  company_name: string | null
  category: string | null
  salary_from: number | null
  salary_to: number | null
  schedule: string | null
  experience_required: string | null
  quality_score: number | null
  feed_score: number | null
  flags: string[]
  moderation_status: string
  source_url: string | null
  source_type: string | null
  media?: Array<{ type: string; url: string }>
  has_media?: boolean
}

type DashboardStats = {
  system_status: string
  last_collection_at: string | null
  vk_posts: number
  vacancies_detected: number
  superjob_fetched: number
  trudvsem_fetched: number
  duplicates: number
  rejected: number
  ready: number
  scored: number
  not_vacancy: number
  avg_vqs: number | null
  avg_feed_score: number | null
}

type PublicationPreview = {
  vacancy_id: string
  source: Record<string, unknown>
  draft: Record<string, unknown>
  rendered_text: string
  mode: string
  variant: number
  status: string
  manually_edited: boolean
  default_image_url: string
  has_media: boolean
}

function formatSalary(from: number | null, to: number | null): string {
  if (from && to) return `${Math.round(from).toLocaleString('ru-RU')}–${Math.round(to).toLocaleString('ru-RU')} ₽`
  if (from) return `от ${Math.round(from).toLocaleString('ru-RU')} ₽`
  if (to) return `до ${Math.round(to).toLocaleString('ru-RU')} ₽`
  return 'не указана'
}

function scoreTier(value: number | null | undefined): 'high' | 'mid' | 'low' | 'none' {
  if (value == null || Number.isNaN(value)) return 'none'
  if (value >= 75) return 'high'
  if (value >= 55) return 'mid'
  return 'low'
}

function ScoreMeter({
  label,
  value,
  testId,
}: {
  label: string
  value: number | null | undefined
  testId?: string
}) {
  const tier = scoreTier(value)
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value))
  return (
    <div className={`score-meter score-meter--${tier}`} data-testid={testId}>
      <div className="score-meter-head">
        <span className="score-meter-label">{label}</span>
        <span className="score-meter-value">{value == null ? '—' : Math.round(value)}</span>
      </div>
      <div className="score-meter-track" aria-hidden>
        <div className="score-meter-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function sourceField(source: Record<string, unknown>, key: string): string {
  const value = source[key]
  if (value == null || value === '') return '—'
  return String(value)
}

function App() {
  const [health, setHealth] = useState<HealthPayload | null>(null)
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [feed, setFeed] = useState<VacancyItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [preview, setPreview] = useState<PublicationPreview | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [healthRes, dashRes, feedRes] = await Promise.all([
          fetch('/health'),
          fetch('/api/dashboard'),
          fetch('/api/feed?limit=30'),
        ])
        if (!healthRes.ok) throw new Error(`health HTTP ${healthRes.status}`)
        const healthData = (await healthRes.json()) as HealthPayload
        const dashData = dashRes.ok ? ((await dashRes.json()) as DashboardStats) : null
        const feedData = feedRes.ok ? ((await feedRes.json()) as VacancyItem[]) : []
        if (!cancelled) {
          setHealth(healthData)
          setStats(dashData)
          setFeed(feedData)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to reach API')
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!selectedId) return
    let cancelled = false
    async function loadPreview() {
      setPreviewError(null)
      try {
        const res = await fetch(`/api/vacancies/${selectedId}/publication`)
        if (!res.ok) throw new Error(`publication HTTP ${res.status}`)
        const data = (await res.json()) as PublicationPreview
        if (!cancelled) {
          setPreview(data)
          setEditText(data.rendered_text)
          setEditing(false)
        }
      } catch (err) {
        if (!cancelled) {
          setPreviewError(err instanceof Error ? err.message : 'preview failed')
        }
      }
    }
    void loadPreview()
    return () => {
      cancelled = true
    }
  }, [selectedId])

  async function runAction(action: 'regenerate' | 'approve' | 'save') {
    if (!selectedId) return
    setBusy(true)
    setPreviewError(null)
    try {
      let res: Response
      if (action === 'regenerate') {
        res = await fetch(`/api/vacancies/${selectedId}/publication/regenerate`, {
          method: 'POST',
        })
      } else if (action === 'approve') {
        res = await fetch(`/api/vacancies/${selectedId}/publication/approve`, {
          method: 'POST',
        })
      } else {
        res = await fetch(`/api/vacancies/${selectedId}/publication`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rendered_text: editText }),
        })
      }
      if (!res.ok) throw new Error(`${action} HTTP ${res.status}`)
      if (action === 'approve') {
        const approved = (await res.json()) as { publication_status: string }
        setPreview((prev) =>
          prev
            ? { ...prev, status: approved.publication_status || 'approved' }
            : prev,
        )
        setFeed((items) =>
          items.map((item) =>
            item.id === selectedId
              ? { ...item, moderation_status: 'approved_for_publication' }
              : item,
          ),
        )
      } else {
        const data = (await res.json()) as PublicationPreview
        setPreview(data)
        setEditText(data.rendered_text)
        setEditing(false)
      }
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : 'action failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="layout">
      <aside className="sidebar" aria-label="Main navigation">
        <div className="brand">Vacancy Platform</div>
        <nav>
          <a className="nav-item active" href="/">
            Dashboard
          </a>
          <span className="nav-item muted">Vacancies</span>
          <span className="nav-item muted">Sources</span>
          <span className="nav-item muted">Cities</span>
          <span className="nav-item muted">Scoring</span>
        </nav>
      </aside>
      <main className="content">
        <header className="page-header">
          <h1>Подборка Нижний Новгород</h1>
          <p className="subtitle">Очередь READY_FOR_PUBLICATION — порядок будущей VK-ленты</p>
        </header>

        <section className="status-panel" aria-live="polite">
          <h2>Система</h2>
          {error ? (
            <p className="status error" data-testid="api-status">
              OFFLINE — {error}
            </p>
          ) : health ? (
            <p className="status ok" data-testid="api-status">
              {health.status.toUpperCase()} · {health.app} v{health.version}
            </p>
          ) : (
            <p className="status" data-testid="api-status">
              Checking…
            </p>
          )}
        </section>

        {stats && (
          <section className="stats-grid" data-testid="collection-stats">
            <div className="stat">
              <span className="stat-label">VK постов</span>
              <span className="stat-value">{stats.vk_posts}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Вакансий</span>
              <span className="stat-value">{stats.vacancies_detected}</span>
            </div>
            <div className="stat">
              <span className="stat-label">SuperJob</span>
              <span className="stat-value">{stats.superjob_fetched}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Работа России</span>
              <span className="stat-value">{stats.trudvsem_fetched}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Дубли</span>
              <span className="stat-value">{stats.duplicates}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Отклонено</span>
              <span className="stat-value">{stats.rejected}</span>
            </div>
            <div className="stat">
              <span className="stat-label">В ленту</span>
              <span className="stat-value">{stats.ready}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Ср. VQS</span>
              <span className={`stat-value score-text score-text--${scoreTier(stats.avg_vqs)}`}>
                {stats.avg_vqs != null ? Math.round(stats.avg_vqs) : '—'}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Ср. FeedScore</span>
              <span className={`stat-value score-text score-text--${scoreTier(stats.avg_feed_score)}`}>
                {stats.avg_feed_score != null ? Math.round(stats.avg_feed_score) : '—'}
              </span>
            </div>
          </section>
        )}

        <section className="feed-section">
          <h2>Топ ленты ({feed.length})</h2>
          <ol className="feed-list" data-testid="feed-list">
            {feed.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={`feed-item feed-item-button${selectedId === item.id ? ' selected' : ''}`}
                  onClick={() => {
                    setSelectedId(item.id)
                    setPreview(null)
                    setEditing(false)
                  }}
                >
                  <div className="feed-rank">#{item.ranked_position ?? '—'}</div>
                  <div className="feed-body">
                    <div className="feed-title-row">
                      <div className="feed-title">{item.title || 'Без названия'}</div>
                      <div
                        className={`feed-score-badge score-text--${scoreTier(item.feed_score)}`}
                        title="FeedScore — итоговый приоритет в ленте"
                      >
                        {item.feed_score != null ? Math.round(item.feed_score) : '—'}
                      </div>
                    </div>
                    <div className="feed-meta">
                      {item.company_name || 'Компания не указана'} · {item.category || 'other'} ·{' '}
                      {item.source_type || 'source'}
                      {item.has_media ? ' · медиа' : ''}
                    </div>
                    <div className="feed-meta">
                      {formatSalary(item.salary_from, item.salary_to)}
                      {item.schedule ? ` · ${item.schedule}` : ''}
                      {item.experience_required ? ` · ${item.experience_required}` : ''}
                    </div>
                    <div className="feed-scores" data-testid="feed-scores">
                      <ScoreMeter label="VQS" value={item.quality_score} />
                      <ScoreMeter label="FeedScore" value={item.feed_score} />
                    </div>
                    {item.flags?.length ? (
                      <div className="feed-flags">{item.flags.join(' · ')}</div>
                    ) : null}
                    {item.source_url && (
                      <a
                        className="feed-link"
                        href={item.source_url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                      >
                        Открыть оригинал
                      </a>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ol>
          {!feed.length && !error && <p className="empty">Пока нет вакансий в очереди публикации.</p>}
        </section>

        {selectedId && (
          <section className="publication-preview" data-testid="publication-preview">
            <div className="publication-header">
              <h2>Превью VK-поста</h2>
              <p className="subtitle">
                {preview
                  ? `${preview.mode.toUpperCase()} · variant ${preview.variant} · ${preview.status}`
                  : 'Загрузка…'}
              </p>
            </div>
            {previewError && <p className="status error">{previewError}</p>}
            {preview && (
              <>
                <div className="publication-actions">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void runAction('regenerate')}
                  >
                    Regenerate
                  </button>
                  <button type="button" disabled={busy} onClick={() => setEditing((v) => !v)}>
                    Edit
                  </button>
                  {editing && (
                    <button type="button" disabled={busy} onClick={() => void runAction('save')}>
                      Save
                    </button>
                  )}
                  <button
                    type="button"
                    className="approve"
                    disabled={busy || preview.status === 'approved'}
                    onClick={() => void runAction('approve')}
                  >
                    Approve
                  </button>
                </div>
                <div className="publication-grid">
                  <div className="publication-pane">
                    <h3>SOURCE DATA</h3>
                    {!preview.has_media && (
                      <img
                        className="publication-default-image"
                        src={preview.default_image_url}
                        alt="Работа / Нижний — изображение по умолчанию"
                      />
                    )}
                    <dl className="source-dl">
                      <dt>Title</dt>
                      <dd>{sourceField(preview.source, 'title')}</dd>
                      <dt>Company</dt>
                      <dd>{sourceField(preview.source, 'company_name')}</dd>
                      <dt>Salary</dt>
                      <dd>
                        {formatSalary(
                          preview.source.salary_from as number | null,
                          preview.source.salary_to as number | null,
                        )}
                      </dd>
                      <dt>Schedule</dt>
                      <dd>{sourceField(preview.source, 'schedule')}</dd>
                      <dt>Experience</dt>
                      <dd>{sourceField(preview.source, 'experience_required')}</dd>
                      <dt>Duties</dt>
                      <dd className="source-long">{sourceField(preview.source, 'duties')}</dd>
                      <dt>Requirements</dt>
                      <dd className="source-long">{sourceField(preview.source, 'requirements')}</dd>
                      <dt>Benefits</dt>
                      <dd className="source-long">{sourceField(preview.source, 'benefits')}</dd>
                      <dt>VQS / Feed</dt>
                      <dd>
                        {sourceField(preview.source, 'quality_score')} /{' '}
                        {sourceField(preview.source, 'feed_score')}
                      </dd>
                    </dl>
                  </div>
                  <div className="publication-pane">
                    <h3>GENERATED POST</h3>
                    {editing ? (
                      <textarea
                        className="publication-editor"
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        rows={22}
                      />
                    ) : (
                      <pre className="publication-post">{preview.rendered_text}</pre>
                    )}
                  </div>
                </div>
              </>
            )}
          </section>
        )}
      </main>
    </div>
  )
}

export default App

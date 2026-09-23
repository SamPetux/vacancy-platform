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

function formatSalary(from: number | null, to: number | null): string {
  if (from && to) return `${Math.round(from).toLocaleString('ru-RU')}–${Math.round(to).toLocaleString('ru-RU')} ₽`
  if (from) return `от ${Math.round(from).toLocaleString('ru-RU')} ₽`
  if (to) return `до ${Math.round(to).toLocaleString('ru-RU')} ₽`
  return 'не указана'
}

function App() {
  const [health, setHealth] = useState<HealthPayload | null>(null)
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [feed, setFeed] = useState<VacancyItem[]>([])
  const [error, setError] = useState<string | null>(null)

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
          </section>
        )}

        <section className="feed-section">
          <h2>Топ ленты ({feed.length})</h2>
          <ol className="feed-list" data-testid="feed-list">
            {feed.map((item) => (
              <li key={item.id} className="feed-item">
                <div className="feed-rank">#{item.ranked_position ?? '—'}</div>
                <div className="feed-body">
                  <div className="feed-title">{item.title || 'Без названия'}</div>
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
                  <div className="feed-scores">
                    VQS {item.quality_score?.toFixed(0) ?? '—'} · FeedScore{' '}
                    {item.feed_score?.toFixed(0) ?? '—'}
                    {item.flags?.length ? ` · ${item.flags.join(', ')}` : ''}
                  </div>
                  {item.source_url && (
                    <a className="feed-link" href={item.source_url} target="_blank" rel="noreferrer">
                      Открыть оригинал
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ol>
          {!feed.length && !error && <p className="empty">Пока нет вакансий в очереди публикации.</p>}
        </section>
      </main>
    </div>
  )
}

export default App

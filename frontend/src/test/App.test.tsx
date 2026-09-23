import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from '../App'

describe('App', () => {
  it('renders dashboard shell and API status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (url: string) => {
        if (url.includes('/health')) {
          return {
            ok: true,
            json: async () => ({
              status: 'ok',
              app: 'vacancy-platform',
              env: 'test',
              version: '0.1.0',
            }),
          }
        }
        if (url.includes('/api/dashboard')) {
          return {
            ok: true,
            json: async () => ({
              system_status: 'ok',
              last_collection_at: null,
              vk_posts: 10,
              vacancies_detected: 5,
              superjob_fetched: 3,
              trudvsem_fetched: 1,
              duplicates: 1,
              rejected: 0,
              ready: 2,
              scored: 4,
              not_vacancy: 2,
              avg_vqs: 70,
              avg_feed_score: 72,
            }),
          }
        }
        return {
          ok: true,
          json: async () => [
            {
              id: '11111111-1111-1111-1111-111111111111',
              ranked_position: 1,
              title: 'Аналитик',
              company_name: 'ООО Тест',
              category: 'office',
              salary_from: 100000,
              salary_to: 120000,
              schedule: '5/2',
              experience_required: 'от 1 года',
              quality_score: 78,
              feed_score: 81,
              flags: [],
              moderation_status: 'ready_for_publication',
              source_url: 'https://example.com',
              source_type: 'superjob',
            },
          ],
        }
      }),
    )

    render(<App />)

    expect(screen.getByRole('heading', { name: /Нижний Новгород/i })).toBeInTheDocument()
    expect(await screen.findByTestId('api-status')).toHaveTextContent('OK')
    expect(await screen.findByTestId('feed-list')).toHaveTextContent('Аналитик')
    expect(await screen.findByTestId('feed-scores')).toHaveTextContent('VQS')
    expect(screen.getByTestId('feed-scores')).toHaveTextContent('81')
    expect(screen.getByTestId('collection-stats')).toHaveTextContent('Ср. FeedScore')
  })
})

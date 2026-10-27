import { expect, it } from 'vitest'
import type { ClaimDetail } from './api'
import { daysLeft, missingPhotos, reminder } from './claims'

const DAY = 24 * 60 * 60 * 1000
const NOW = Date.parse('2026-10-27T12:00:00Z')
const due = (days: number) => new Date(NOW + days * DAY).toISOString()

it('daysLeft rounds a part day up and never goes below zero', () => {
  expect(daysLeft(due(14), NOW)).toBe(14)
  expect(daysLeft(due(13.2), NOW)).toBe(14)
  expect(daysLeft(due(-1), NOW)).toBe(0)
})

it('reminds from day 10 of 14 and warns from day 13, as PLAN.md §6 sets', () => {
  expect(reminder(due(5), NOW)).toBeNull()
  expect(reminder(due(4), NOW)).toBe('nudge')
  expect(reminder(due(1), NOW)).toBe('warning')
})

it('missingPhotos names every before and after a submission still needs', () => {
  const claim = {
    photos: [{ id: 'a', phase: 'before', point: 1, url: '', created_at: '' }],
  } as unknown as ClaimDetail
  expect(missingPhotos(claim)).toEqual([
    'after photo at point 1',
    'before photo at point 2',
    'after photo at point 2',
  ])
})

it('after a send-back, an after photo taken before it no longer counts', () => {
  const claim = {
    sent_back_at: '2026-10-27T12:00:00.000Z',
    photos: [1, 2].flatMap((point) => [
      {
        id: `b${point}`,
        phase: 'before',
        point,
        url: '',
        created_at: '2026-10-27T10:00:00.000Z',
      },
      {
        id: `a${point}`,
        phase: 'after',
        point,
        url: '',
        created_at: '2026-10-27T11:00:00.000Z',
      },
    ]),
  } as unknown as ClaimDetail
  expect(missingPhotos(claim)).toEqual([
    'after photo at point 1',
    'after photo at point 2',
  ])
})

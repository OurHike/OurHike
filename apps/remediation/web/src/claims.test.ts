import { expect, it } from 'vitest'
import type { ClaimDetail } from './api'
import { daysLeft, missingPhotos } from './claims'

const DAY = 24 * 60 * 60 * 1000
const NOW = Date.parse('2026-10-27T12:00:00Z')
const due = (days: number) => new Date(NOW + days * DAY).toISOString()

it('daysLeft rounds a part day up and never goes below zero', () => {
  expect(daysLeft(due(14), NOW)).toBe(14)
  expect(daysLeft(due(13.2), NOW)).toBe(14)
  expect(daysLeft(due(-1), NOW)).toBe(0)
})

it('missingPhotos names every before and after a restoration still needs', () => {
  const claim = {
    kind: 'restore',
    photos: [{ id: 'a', phase: 'before', point: 1, url: '', created_at: '' }],
  } as unknown as ClaimDetail
  expect(missingPhotos(claim)).toEqual([
    'after photo at point 1',
    'before photo at point 2',
    'after photo at point 2',
  ])
})

it('a follow-up visit needs only the after photos again, as the API asks', () => {
  const claim = {
    kind: 'follow_up',
    photos: [{ id: 'a', phase: 'after', point: 2, url: '', created_at: '' }],
  } as unknown as ClaimDetail
  expect(missingPhotos(claim)).toEqual(['after photo at point 1'])
})

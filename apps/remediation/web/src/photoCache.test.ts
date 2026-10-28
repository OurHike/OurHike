import { expect, it } from 'vitest'
import { photoLinkPattern } from './photoCache'

it("matches a signed link to a photo on this build's project and nothing else", () => {
  const pattern = photoLinkPattern('https://abcd.supabase.co/')
  const link =
    'https://abcd.supabase.co/storage/v1/object/sign/remediation-photos/c/u/p.jpg?token=t'
  expect(pattern.test(link)).toBe(true)
  for (const other of [
    'https://abcd.supabase.co/storage/v1/object/public/remediation-photos/c/u/p.jpg',
    'https://abcd.supabase.co/storage/v1/object/sign/other-bucket/p.jpg?token=t',
    'https://evil.example/https://abcd.supabase.co/storage/v1/object/sign/remediation-photos/p.jpg',
    'https://abcdXsupabase.co/storage/v1/object/sign/remediation-photos/p.jpg',
  ])
    expect(pattern.test(other)).toBe(false)
  expect(photoLinkPattern(undefined).test(link)).toBe(false)
})

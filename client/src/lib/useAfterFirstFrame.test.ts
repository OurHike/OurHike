import { describe, expect, it } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useAfterFirstFrame } from './useAfterFirstFrame'

describe('useAfterFirstFrame', () => {
  it('is false in the first render and true a frame later', async () => {
    const { result } = renderHook(() => useAfterFirstFrame())
    expect(result.current).toBe(false)
    await waitFor(() => expect(result.current).toBe(true))
  })
})

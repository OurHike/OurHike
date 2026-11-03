import { describe, it, expect } from 'vitest'
import {
  namesOnOffer,
  reportSignature,
  signatureFields,
  signatureWords,
} from './reporterSignature'

// Which name a report is signed with (#1563). The load-bearing properties:
//
//   - the default is the trail name, and a hiker who never touches the
//     control signs exactly as before
//   - a kind without a name sends nothing, never a kind on its own
//   - a name of spaces is not a name

const PREFS = { trail_name: 'Switchback', real_name: 'Jane Doe' }

describe('the names on offer', () => {
  it('trims both and treats an empty or blank name as none', () => {
    expect(namesOnOffer({ trail_name: '  Switchback ', real_name: '   ' })).toEqual({
      trail: 'Switchback',
      real: null,
    })
    expect(namesOnOffer({ trail_name: null, real_name: null })).toEqual({
      trail: null,
      real: null,
    })
  })
})

describe('what the wire carries', () => {
  it('sends the chosen name with its kind', () => {
    expect(signatureFields(reportSignature(PREFS, 'trail'))).toEqual({
      signed_name: 'Switchback',
      signed_name_kind: 'trail',
    })
    expect(signatureFields(reportSignature(PREFS, 'real'))).toEqual({
      signed_name: 'Jane Doe',
      signed_name_kind: 'real',
    })
  })

  it('sends neither when the chosen kind has no name - never a kind on its own', () => {
    expect(
      signatureFields(reportSignature({ ...PREFS, real_name: null }, 'real')),
    ).toEqual({})
    expect(
      signatureFields(reportSignature({ trail_name: null, real_name: null }, 'trail')),
    ).toEqual({})
  })
})

describe('how it reads', () => {
  it('names the name and which one it is, and says when it is not set', () => {
    expect(signatureWords(reportSignature(PREFS, 'real'))).toBe('Jane Doe (real name)')
    expect(signatureWords(reportSignature({ ...PREFS, trail_name: null }, 'trail'))).toBe(
      'not set (trail name)',
    )
  })
})

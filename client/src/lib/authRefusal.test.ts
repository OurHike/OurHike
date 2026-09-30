import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { refusalIn, urlWithoutRefusal, clearRefusalFromUrl } from './authRefusal'

// A sign-in refused at Google or GitHub, read back off the URL (#1573).
//
// THE SHAPES HERE ARE THE ONES SUPABASE REDIRECTS WITH, taken from GoTrue's
// `api/external.go` and OAuth2 RFC 6749 §4.1.2.1 rather than from a refusal
// seen against the live project - the same `@unvalidated` footing
// authMessages.ts's header gives the two patterns they map to. What that
// means for these tests is that they pin the PARSING, which is entirely this
// repository's own work, and not the claim that Google spells it this way.
//
// The parsing is worth its own file because it is the half that has an edge
// on every side: two halves of a URL, three keys, a key present and empty, a
// description that says nothing beside a code that says everything.

describe('reading a refusal off a returned-to URL', () => {
  it('finds one in the fragment, which is where the implicit flow puts it', () => {
    const said = refusalIn('#error=access_denied&error_code=403', '')

    expect(said).not.toBe(null)
    expect(said).toMatch(/was not finished/i)
  })

  it('finds one in the query, which is where the PKCE flow puts it', () => {
    // Both halves are read because which one carries it is Supabase's
    // choice, not ours - a build that read only the fragment would go silent
    // again the day the default flow changes underneath it.
    const said = refusalIn('', '?error=access_denied&error_code=403')

    expect(said).toMatch(/was not finished/i)
  })

  it('works whether or not the caller strips the leading # or ?', () => {
    expect(refusalIn('error=access_denied', '')).toMatch(/was not finished/i)
    expect(refusalIn('', 'error=access_denied')).toMatch(/was not finished/i)
  })

  it('is null for a URL with nothing on it, which is nearly every launch', () => {
    expect(refusalIn('', '')).toBe(null)
  })

  it('is null for the fragment a SUCCESSFUL sign-in comes back on', () => {
    // The defect this whole file exists for would be cheap to swap for a
    // worse one: an alert in front of somebody who just signed in fine.
    // supabase-js reads and clears this fragment itself.
    expect(
      refusalIn(
        '#access_token=eyJhbGci.fake.token&expires_in=3600&token_type=bearer',
        '',
      ),
    ).toBe(null)
  })

  it('is null for an error key present and empty, which carries no information', () => {
    expect(refusalIn('#error=&error_description=', '')).toBe(null)
    expect(refusalIn('#error=%20%20', '')).toBe(null)
  })

  it('prefers the key that says something over the key that came first', () => {
    // THE CASE THAT MADE THIS A LOOP RATHER THAN A LOOKUP. `error_
    // description` is the wordiest value and is tried first, but a provider
    // writing its own prose for a cancellation produces a description this
    // app cannot recognise beside a code it can. Taking the first key
    // PRESENT would answer with the general case and throw away the one
    // value in the URL that had a real sentence behind it.
    const said = refusalIn(
      '#error=server_error&error_code=access_denied&error_description=The+user+denied+the+request',
      '',
    )

    expect(said).toMatch(/was not finished/i)
    expect(said).not.toMatch(/did not go through/i)
  })

  it('decodes a description that arrived form-encoded', () => {
    const said = refusalIn(
      '#error=server_error&error_description=Error+getting+user+email+from+external+provider',
      '',
    )

    expect(said).toMatch(/verified email address/i)
  })

  it('decodes one that arrived percent-encoded instead', () => {
    const said = refusalIn(
      '#error_description=Error%20getting%20user%20email%20from%20external%20provider',
      '',
    )

    expect(said).toMatch(/verified email address/i)
  })

  it('falls back to a true sentence for a refusal nothing here recognises', () => {
    // The known failure mode of matching on text, and the reason it is
    // acceptable: a reworded upstream message gets vaguer, never confidently
    // wrong. What it must never do is stay silent, which is the defect.
    const said = refusalIn('#error=teapot&error_description=I+am+a+teapot', '')

    expect(said).toMatch(/did not go through/i)
  })

  it('never puts a raw provider code in front of a hiker', () => {
    expect(refusalIn('#error=unauthorized_client', '')).not.toMatch(/unauthorized_client/)
  })
})

describe('taking the refusal back off the URL', () => {
  it('leaves a URL that never had one exactly as it was', () => {
    expect(urlWithoutRefusal('https://ourhike.org/app/')).toBe('https://ourhike.org/app/')
  })

  it('drops the whole fragment when the refusal was all of it', () => {
    // And drops the `#` with it. A bare trailing hash is a URL that looks
    // like it still has something on it.
    expect(
      urlWithoutRefusal('https://ourhike.org/app/#error=access_denied&error_code=403'),
    ).toBe('https://ourhike.org/app/')
  })

  it('drops it from the query too', () => {
    expect(urlWithoutRefusal('https://ourhike.org/app/?error=access_denied')).toBe(
      'https://ourhike.org/app/',
    )
  })

  it('keeps what it did not put there', () => {
    // THREE NAMED KEYS, NOT THE WHOLE URL. The first version rebuilt the
    // address from `location.pathname` alone - correct today, since nothing
    // in this app reads the query or the fragment, and a trap for the first
    // deep link somebody adds.
    expect(
      urlWithoutRefusal(
        'https://ourhike.org/app/?trail=at&error=access_denied#mile=1088',
      ),
    ).toBe('https://ourhike.org/app/?trail=at#mile=1088')
  })

  it('leaves the successful sign-in fragment for supabase-js to clear', () => {
    const href = 'https://ourhike.org/app/#access_token=fake&token_type=bearer'

    expect(urlWithoutRefusal(href)).toBe(href)
  })
})

describe('clearing it from the address bar', () => {
  const replaceState = vi.fn()

  beforeEach(() => {
    replaceState.mockClear()
    vi.stubGlobal('window', {
      location: { href: 'https://ourhike.org/app/#error=access_denied' },
      history: { state: { sentinel: 1 }, replaceState },
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('replaces rather than pushes, so Back does not walk through it again', () => {
    clearRefusalFromUrl()

    expect(replaceState).toHaveBeenCalledTimes(1)
    expect(replaceState).toHaveBeenCalledWith(
      { sentinel: 1 },
      '',
      'https://ourhike.org/app/',
    )
  })

  it('does nothing at all when there is nothing to clear', () => {
    vi.stubGlobal('window', {
      location: { href: 'https://ourhike.org/app/' },
      history: { state: null, replaceState },
    })

    clearRefusalFromUrl()

    expect(replaceState).not.toHaveBeenCalled()
  })
})

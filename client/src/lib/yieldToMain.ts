// Give the event loop a turn, so a long loop on the main thread is many short
// tasks rather than one long one (#1192).
//
// `scheduler.yield()` where the browser has it: it resumes ahead of other
// queued work, so a loop sliced with it finishes about as soon as it would
// have unsliced while every tap in between is answered. Elsewhere a macrotask
// turn through a MessageChannel, which resumes behind whatever else is queued
// - slower to finish, still responsive, and what older WebViews get. Not
// setTimeout: browsers clamp nested timeouts to 4 ms, which over a few
// hundred slices is a second of nothing, and a test suite that fakes timers
// (vi.useFakeTimers) would never see one fire at all - the build would wait
// forever on a clock nobody advances. A message port is neither clamped nor
// faked. setTimeout is the last resort, for a runtime with no ports.
//
// This is what makes the fallback in lib/trailIndexBuild.ts tolerable rather
// than what makes the launch fast: the fast path is a worker, and a phone
// only reaches a sliced main-thread build where there is no worker to give
// the work to. The measured cost being sliced is the one #1192 records.

interface SchedulerLike {
  yield?: () => Promise<void>
}

export function yieldToMain(): Promise<void> {
  const scheduler = (globalThis as { scheduler?: SchedulerLike }).scheduler
  if (scheduler?.yield !== undefined) return scheduler.yield()
  if (typeof MessageChannel !== 'undefined') {
    return new Promise((resolve) => {
      const channel = new MessageChannel()
      channel.port1.onmessage = () => {
        channel.port1.close()
        resolve()
      }
      channel.port2.postMessage(null)
    })
  }
  return new Promise((resolve) => setTimeout(resolve, 0))
}

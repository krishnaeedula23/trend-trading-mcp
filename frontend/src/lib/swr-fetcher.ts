/**
 * Shared SWR fetcher that throws on HTTP error so SWR's `error` slot is populated.
 * Without this check, a 500 response body silently parses and renders as "no data".
 */
export async function jsonFetcher<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) {
    let detail = `HTTP ${r.status}`
    try {
      const body = await r.json()
      detail = body.detail ?? body.error ?? detail
    } catch {
      // non-JSON body; keep HTTP code
    }
    throw new Error(detail)
  }
  return r.json() as Promise<T>
}

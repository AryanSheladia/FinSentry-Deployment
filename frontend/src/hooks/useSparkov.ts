import { useCallback, useEffect, useRef, useState } from 'react'
import type { PaymentInput, SparkovInvestigation, SparkovOptions } from '../sparkovTypes'
import { sparkovApi } from '../services/sparkovApi'

export function useSparkov() {
  const [options, setOptions] = useState<SparkovOptions | null>(null)
  const [rows, setRows] = useState<SparkovInvestigation[]>([])
  const [focused, setFocused] = useState<SparkovInvestigation | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [paused, setPaused] = useState(false)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const deletedIds = useRef(new Set<string>())
  const saveRows = useCallback((recent: SparkovInvestigation[]) => setRows(recent.filter(row => !deletedIds.current.has(row.investigation_id))), [])
  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [data, recent] = await Promise.all([sparkovApi.options(), sparkovApi.investigations()])
      setOptions(data); saveRows(recent); setLastUpdated(new Date()); setError('')
    } catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }, [])
  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    let cancelled = false
    let running = false
    const timer = window.setInterval(async () => {
      if (document.hidden || running) return
      running = true
      try {
        const recent = await sparkovApi.investigations()
        if (!cancelled) { saveRows(recent); setFocused(current => current && !deletedIds.current.has(current.investigation_id) ? recent.find(row => row.investigation_id === current.investigation_id) ?? current : null); setLastUpdated(new Date()) }
      } catch (e) { if (!cancelled) setError((e as Error).message) }
      finally { running = false }
    }, 20000)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [])
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('investigation')
    if (!id || !/^SPINV_[a-f0-9]{32}$/.test(id)) return
    let cancelled = false
    void sparkovApi.get(id).then(row => { if (!cancelled && !deletedIds.current.has(id)) setFocused(row) }).catch(e => { if (!cancelled) setError((e as Error).message) })
    return () => { cancelled = true }
  }, [])
  const open = useCallback(async (id: string) => {
    try { setFocused(null); setPaused(false); const row = await sparkovApi.get(id); if (!deletedIds.current.has(id)) setFocused(row); setError('') }
    catch (e) { setError((e as Error).message) }
  }, [])
  const pending = focused?.status === 'QUEUED' || focused?.status === 'RUNNING'
  useEffect(() => {
    if (!focused || !pending || paused) return
    let cancelled = false
    let running = false
    const deadline = Date.now() + 120000
    const timer = window.setInterval(async () => {
      if (running) return
      if (Date.now() > deadline) { setPaused(true); setError('This assessment is taking longer than expected. Reopen the case from the review queue to check its progress.'); return }
      running = true
      try {
        const row = await sparkovApi.get(focused.investigation_id)
        if (!cancelled && !deletedIds.current.has(row.investigation_id)) {
          setFocused(row)
          if (row.status === 'COMPLETED' || row.status === 'FAILED') saveRows(await sparkovApi.investigations())
        }
      } catch (e) { if (!cancelled) { setError((e as Error).message); setPaused(true) } }
      finally { running = false }
    }, 850)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [focused?.investigation_id, focused?.status, pending, paused])
  async function start(payment: PaymentInput) {
    if (submitting || (pending && !paused)) return
    setSubmitting(true); setError('')
    try { const accepted = await sparkovApi.start(payment); await open(accepted.investigation_id); return accepted.investigation_id }
    catch (e) { setError((e as Error).message); return null } finally { setSubmitting(false) }
  }
  async function review(body: { reviewer: string; action: string; notes: string }) {
    if (!focused) return
    const row = await sparkovApi.review(focused.investigation_id, body)
    if (!deletedIds.current.has(row.investigation_id)) setFocused(row)
    saveRows(await sparkovApi.investigations())
  }
  async function remove(id: string) {
    const result = await sparkovApi.delete(id)
    result.deleted_case_ids.forEach(identifier => deletedIds.current.add(identifier))
    setRows(current => current.filter(row => !deletedIds.current.has(row.investigation_id)))
    setFocused(current => current && deletedIds.current.has(current.investigation_id) ? null : current)
    const linked = new URLSearchParams(window.location.search).get('investigation')
    if (linked && deletedIds.current.has(linked)) window.history.replaceState(null, '', window.location.pathname)
    setLastUpdated(new Date()); setError('')
    // Refill the latest 100 after deletion; a refresh failure must not undo success.
    try { saveRows(await sparkovApi.investigations()) } catch { /* The next scheduled refresh retries. */ }
  }
  return { options, rows, focused, error, loading, refresh, open, start, review, remove, lastUpdated, busy: submitting || (pending && !paused) }
}

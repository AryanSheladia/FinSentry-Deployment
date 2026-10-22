import { useState } from 'react'
import { Search, ChevronRight, Inbox, Trash2 } from 'lucide-react'
import type { SparkovInvestigation } from '../sparkovTypes'
import { money, customerName, merchantName, caseName, needsAttention, isUrgent, statusLabel } from '../services/analyst'

export function CaseQueue({ rows, onOpen, onDelete, compact = false, initialFilter = 'all' }: { rows: SparkovInvestigation[]; onOpen: (id: string) => void; onDelete?: (id: string) => Promise<void>; compact?: boolean; initialFilter?: string }) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState(initialFilter)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState('')
  const [notice, setNotice] = useState('')
  async function remove(row: SparkovInvestigation) {
    if (!onDelete || deleting || row.status === 'QUEUED' || row.status === 'RUNNING') return
    const confirmed = window.confirm(`Permanently delete ${caseName(row.investigation_id)}?\n\n${money(row.payment.amount)} at ${merchantName(row.payment.merchant)}\n${customerName(row.payment.customer_id)}\n\nThis removes the submitted transaction, all its investigations and review notes from the queue and database. It cannot be undone. The original training dataset is unchanged.`)
    if (!confirmed) return
    setDeleting(row.investigation_id); setDeleteError(''); setNotice('')
    try { await onDelete(row.investigation_id); setNotice('Transaction, case and review notes deleted.') }
    catch (error) { setDeleteError((error as Error).message) }
    finally { setDeleting(null) }
  }
  const filtered = rows.filter(row => (filter === 'all' || filter === 'attention' && needsAttention(row) || filter === 'urgent' && isUrgent(row) || filter === 'reviewed' && row.reviews.length > 0 || filter === 'cleared' && row.reviews.at(-1)?.action === 'CLEAR') && `${row.investigation_id} ${row.payment.customer_id} ${customerName(row.payment.customer_id)} ${row.payment.merchant}`.toLowerCase().includes(search.toLowerCase()))
  const visible = [...filtered].sort((a, b) => Number(isUrgent(b)) - Number(isUrgent(a)) || Number(needsAttention(b)) - Number(needsAttention(a)) || b.created_at.localeCompare(a.created_at)).slice(0, compact ? 6 : 100)
  return <section className="card queue-card"><div className="card-heading"><div><h2>{compact ? 'Priority case list' : 'Payment review queue'}</h2><p>Escalations and unreviewed findings appear first.</p></div><span className="count-badge">{filtered.length} cases</span></div>
    {deleteError && <p className="queue-delete-error" role="alert">{deleteError}</p>}
    <p className="queue-delete-notice" role="status">{notice}</p>
    {!compact && <div className="queue-tools"><div className="filter-tabs" role="group" aria-label="Filter cases">{[['all', 'All cases'], ['attention', 'Needs attention'], ['urgent', 'Escalations'], ['reviewed', 'Review recorded']].map(([id, title]) => <button key={id} aria-pressed={filter === id} className={filter === id ? 'active' : ''} onClick={() => setFilter(id)}>{title}</button>)}</div><label className="search-box"><Search size={17} /><input aria-label="Search cases" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search case, customer or merchant" /></label></div>}
    <div className="queue-scroll"><table><thead><tr><th>Case / customer</th><th>Payment</th><th>Assessment</th><th>Review status</th><th><span className="sr-only">Case actions</span></th></tr></thead><tbody>{visible.map(row => <tr key={row.investigation_id}><td><button className="case-link" onClick={() => onOpen(row.investigation_id)}>{caseName(row.investigation_id)}</button><small>{customerName(row.payment.customer_id)}</small></td><td><strong>{money(row.payment.amount)}</strong><small>{merchantName(row.payment.merchant)}</small></td><td><span className={`label ${row.result?.recommendation === 'ESCALATE' ? 'danger' : row.result?.recommendation === 'FLAG' ? 'warning' : 'calm'}`}>{row.result?.recommendation === 'ESCALATE' ? 'Human review' : row.result?.recommendation === 'FLAG' ? 'Investigate' : row.result ? 'No trigger' : row.status === 'FAILED' ? 'Interrupted' : 'In progress'}</span></td><td>{statusLabel(row)}</td><td><div className="case-actions"><button className="round-button" aria-label={`Open ${caseName(row.investigation_id)}`} onClick={() => onOpen(row.investigation_id)}><ChevronRight size={19} /></button>{onDelete && <button className="delete-case-button" aria-label={`Delete ${caseName(row.investigation_id)}`} title={row.status === 'QUEUED' || row.status === 'RUNNING' ? 'Wait for the investigation to finish before deleting' : 'Delete transaction and case'} disabled={!!deleting || row.status === 'QUEUED' || row.status === 'RUNNING'} onClick={() => void remove(row)}><Trash2 size={15} />{deleting === row.investigation_id ? 'Deleting…' : 'Delete'}</button>}</div></td></tr>)}</tbody></table></div>
    {!visible.length && <div className="empty-state"><Inbox size={32} /><h3>No cases here</h3><p>{search || filter !== 'all' ? 'Try a different search or filter.' : 'Investigate a payment to create the first case.'}</p></div>}
    <div className="card-footnote">Based on the latest {rows.length} submitted cases, up to 100. This is a simulation workspace, not a live bank feed.</div>
  </section>
}

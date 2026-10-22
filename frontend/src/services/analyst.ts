import type { Payment, SparkovInvestigation } from '../sparkovTypes'

export const money = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)
export const customerName = (id: string) => id.startsWith('NEW_') ? id.slice(4).replaceAll('_', ' ') : `Customer ${id.replace('CUST_', '').slice(0, 8).toUpperCase()}`
export const merchantName = (name: string) => name.replace(/^fraud_/, '')
export const caseName = (id: string) => `Case ${id.replace('SPINV_', '').slice(0, 8).toUpperCase()}`
export const paymentDate = (seconds: number) => new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }).format(new Date(seconds * 1000)) + ' UTC'
export const actionLabel = (action?: string) => action === 'ESCALATE' ? 'Escalate for human review' : action === 'FLAG' ? 'Investigate further' : action === 'CLEAR' ? 'No review trigger' : 'Assessment in progress'
export const latestReview = (row: SparkovInvestigation) => row.reviews.at(-1)
export const needsAttention = (row: SparkovInvestigation) => row.status === 'COMPLETED' && latestReview(row)?.action !== 'CLEAR' && (Boolean(latestReview(row)) || row.result?.recommendation !== 'CLEAR')
export const isUrgent = (row: SparkovInvestigation) => needsAttention(row) && (latestReview(row)?.action === 'ESCALATE' || row.result?.recommendation === 'ESCALATE')
export const statusLabel = (row: SparkovInvestigation) => row.status === 'FAILED' ? 'Assessment interrupted' : row.status !== 'COMPLETED' ? 'Assessing payment' : latestReview(row)?.action === 'CLEAR' ? 'Cleared by analyst' : latestReview(row)?.action === 'ESCALATE' ? 'Awaiting senior review' : latestReview(row)?.action === 'FLAG' ? 'Follow-up required' : needsAttention(row) ? 'Awaiting review' : 'No review trigger'
export const categories: Record<string, string> = { grocery_pos: 'Groceries · in person', grocery_net: 'Groceries · online', shopping_pos: 'Shopping · in person', shopping_net: 'Shopping · online', misc_pos: 'Other · in person', misc_net: 'Other · online', gas_transport: 'Fuel & transport', entertainment: 'Entertainment', food_dining: 'Food & dining', health_fitness: 'Health & fitness', home: 'Home', kids_pets: 'Children & pets', personal_care: 'Personal care', travel: 'Travel' }
export function locationLabel(payment: Payment) {
  if (payment.home_lat === undefined || payment.home_lon === undefined) return 'Location details available'
  const radians = (v: number) => v * Math.PI / 180
  const a = Math.sin(radians(payment.merchant_lat - payment.home_lat) / 2) ** 2 + Math.cos(radians(payment.home_lat)) * Math.cos(radians(payment.merchant_lat)) * Math.sin(radians(payment.merchant_lon - payment.home_lon) / 2) ** 2
  const km = 6371.0088 * 2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, a))))
  return km < 5 ? 'Near the customer’s recorded home area' : `About ${Math.round(km).toLocaleString()} km from the recorded home`
}

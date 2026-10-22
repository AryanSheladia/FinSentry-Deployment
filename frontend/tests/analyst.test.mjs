import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { join, dirname } from 'node:path'
import { mkdirSync } from 'node:fs'
import { buildSync } from 'esbuild'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const compiled = join(root, 'node_modules/.cache/finsentry-ui-tests')
mkdirSync(compiled, { recursive: true })
const require = createRequire(import.meta.url)
function load(file, name) {
  const outfile = join(compiled, name + '.cjs')
  buildSync({ entryPoints: [join(root, 'src', file)], outfile, bundle: true, platform: 'node', format: 'cjs', jsx: 'automatic', define: { 'import.meta.env': '{}' }, external: ['react', 'react-dom', 'react/jsx-runtime'], logLevel: 'silent' })
  return require(outfile)
}
const helpers = load('services/analyst.ts', 'helpers')
const { CaseQueue } = load('components/CaseQueue.tsx', 'queue')
const { CaseDetails } = load('components/CaseDetails.tsx', 'details')
const { sparkovApi } = load('services/sparkovApi.ts', 'api')
const row = {
  investigation_id: 'SPINV_12345678901234567890123456789012', transaction_id: 'PAY_TEST', status: 'COMPLETED', created_at: '2020-07-15T03:15:00Z', completed_stages: [], error: null, reviews: [],
  payment: { customer_id: 'CUST_00686b4dd6551bfe', timestamp: 1594782900, amount: 47.72, merchant: 'fraud_Test merchant', category: 'home', merchant_lat: -33.86, merchant_lon: 151.2, device_id: 'SIM_DEVICE_TEST', payment_method: 'CARD' },
  result: { recommendation: 'FLAG', risk_level: 'MEDIUM', risk: { risk_score: .01, threshold: .3272, features: {} }, evidence_confidence: 'HIGH', behavior: { history_count: 99, recent_30d_count: 30, baseline_mean_30d: 50, findings: [{ code: 'UNUSUAL_TIME', detail: 'Only one earlier payment occurred at this hour.' }] }, intelligence: { status: 'NO_MATCH', cases: [], limitations: [] }, quality: { limitations: [] }, explanation: 'Unusual timing warrants a review of this simulated payment.', explanation_mode: 'llm', conflict_remaining: false }
}

test('customer and merchant labels are readable without changing source keys', () => {
  assert.equal(helpers.merchantName('fraud_Test merchant'), 'Test merchant')
  assert.equal(helpers.merchantName('A fraud_review service'), 'A fraud_review service')
  assert.equal(helpers.customerName(row.payment.customer_id), 'Customer 00686B4D')
  assert.equal(row.payment.merchant, 'fraud_Test merchant')
})
test('a follow-up or escalation remains in the attention queue until an analyst clears it', () => {
  assert.equal(helpers.needsAttention(row), true)
  const followUp = { ...row, reviews: [{ action: 'FLAG' }] }
  assert.equal(helpers.needsAttention(followUp), true)
  assert.equal(helpers.statusLabel(followUp), 'Follow-up required')
  const escalated = { ...row, reviews: [{ action: 'ESCALATE' }] }
  assert.equal(helpers.isUrgent(escalated), true)
  const cleared = { ...escalated, reviews: [...escalated.reviews, { action: 'CLEAR' }] }
  assert.equal(helpers.needsAttention(cleared), false)
  assert.equal(helpers.isUrgent(cleared), false)
  assert.equal(helpers.statusLabel(cleared), 'Cleared by analyst')
})
test('no automated trigger does not claim an analyst has cleared the payment', () => {
  const noTrigger = { ...row, result: { ...row.result, recommendation: 'CLEAR' } }
  assert.equal(helpers.needsAttention(noTrigger), false)
  assert.equal(helpers.statusLabel(noTrigger), 'No review trigger')
})
test('payment location is readable without displaying raw coordinates', () => {
  assert.match(helpers.locationLabel({ ...row.payment, home_lat: -33.86, home_lon: 151.2 }), /Near the customer/)
  assert.match(helpers.locationLabel({ ...row.payment, home_lat: 32.37, home_lon: -90.12 }), /km from the recorded home/)
})
test('queue presents analyst actions and can filter cleared cases', () => {
  const cleared = { ...row, investigation_id: 'SPINV_CLEAR', reviews: [{ action: 'CLEAR' }] }
  const html = renderToStaticMarkup(React.createElement(CaseQueue, { rows: [row, cleared], onOpen() {}, initialFilter: 'cleared' }))
  assert.match(html, /Cleared by analyst/)
  assert.doesNotMatch(html, /Case 12345678/)
  assert.doesNotMatch(html, /MySQL|Groq|LangGraph|IEEE-CIS|NO_MATCH/)
})
test('case detail explains evidence, hides developer fields and requires an explicit review decision', () => {
  const html = renderToStaticMarkup(React.createElement(CaseDetails, { row, onReview: async () => {} }))
  assert.match(html, /Unusual payment time/)
  assert.match(html, /Well supported/)
  assert.match(html, /No linked records found/)
  assert.match(html, /Choose your review decision/)
  assert.doesNotMatch(html, /model_version|assessment_index|UNUSUAL_TIME|NO_MATCH|Groq|MySQL|derived inputs|API documentation/)
})

test('queue offers deletion for saved cases and disables it for active investigations', () => {
  const pending = { ...row, investigation_id: 'SPINV_PENDING', status: 'RUNNING' }
  const html = renderToStaticMarkup(React.createElement(CaseQueue, { rows: [row, pending], onOpen() {}, onDelete: async () => {} }))
  assert.match(html, /aria-label="Delete Case 12345678"/)
  assert.match(html, /Wait for the investigation to finish before deleting/)
  assert.match(html, /disabled=""/)
  const withoutDelete = renderToStaticMarkup(React.createElement(CaseQueue, { rows: [row], onOpen() {} }))
  assert.doesNotMatch(withoutDelete, /Delete Case/)
})

test('an older backend cannot make a failed delete look successful', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Method Not Allowed' }), { status: 405 })
  try {
    await assert.rejects(sparkovApi.delete(row.investigation_id), /Nothing was deleted.*Restart the backend/)
  } finally { globalThis.fetch = originalFetch }
})

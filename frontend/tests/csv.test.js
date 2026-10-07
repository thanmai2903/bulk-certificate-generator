import assert from 'node:assert/strict'
import test from 'node:test'
import { parseCsv } from '../src/csv.js'

test('parses plain lines and optional IDs', () => {
  assert.deepEqual(parseCsv('Asha,asha@example.org,P-001\nDev,dev@example.org'), [
    { name: 'Asha', email: 'asha@example.org', recipient_id: 'P-001' },
    { name: 'Dev', email: 'dev@example.org' },
  ])
})

test('accepts BOM, header, quoted commas and CRLF', () => {
  assert.deepEqual(parseCsv('\uFEFFname,email,recipient_id\r\n"Rao, Asha",asha@example.org,P-001'), [
    { name: 'Rao, Asha', email: 'asha@example.org', recipient_id: 'P-001' },
  ])
})

test('reports malformed CSV', () => {
  assert.throws(() => parseCsv('"Unclosed,person@example.org'), /unclosed quote/)
  assert.throws(() => parseCsv('Asha,asha@example.org,P-001,extra'), /Each row needs/)
})

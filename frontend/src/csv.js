export function parseCsv(text) {
  const rows = []
  let row = [], field = '', quoted = false
  text = text.replace(/^\uFEFF/, '')
  for (let i = 0; i < text.length; i++) {
    const char = text[i]
    if (char === '"') {
      if (quoted && text[i + 1] === '"') { field += '"'; i++ }
      else quoted = !quoted
    } else if (char === ',' && !quoted) {
      row.push(field.trim()); field = ''
    } else if ((char === '\n' || char === '\r') && !quoted) {
      if (char === '\r' && text[i + 1] === '\n') i++
      row.push(field.trim())
      if (row.some(Boolean)) rows.push(row)
      row = []; field = ''
    } else field += char
  }
  if (quoted) throw new Error('The recipient list has an unclosed quote.')
  row.push(field.trim())
  if (row.some(Boolean)) rows.push(row)
  if (rows.length && rows[0][0]?.toLowerCase() === 'name' && rows[0][1]?.toLowerCase() === 'email') rows.shift()
  if (rows.some(fields => fields.length > 3)) {
    throw new Error('Each row needs name, email, and optional ID. Quote names containing commas.')
  }
  return rows.map(([name = '', email = '', recipient_id = '']) => ({ name, email, ...(recipient_id ? { recipient_id } : {}) }))
}

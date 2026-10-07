import { useEffect, useMemo, useRef, useState } from 'react'
import { parseCsv } from './csv.js'

const example = 'Asha Rao,asha@example.org,P-001\nDev Shah,dev@example.org,P-002\nMira Patel,mira@example.org'

async function request(path, options) {
  const response = await fetch(`/api${path}`, options)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const data = await response.json()
      message = typeof data.detail === 'string' ? data.detail : message
    } catch { /* Keep the HTTP message. */ }
    throw new Error(message)
  }
  return response.json()
}

function Icon({ name, size = 20 }) {
  const paths = {
    award: <><circle cx="12" cy="8" r="5"/><path d="m8.8 12-1.3 9 4.5-2.5 4.5 2.5-1.3-9"/></>,
    upload: <><path d="M12 16V4m-4 4 4-4 4 4"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/></>,
    arrow: <path d="M5 12h14m-6-6 6 6-6 6"/>,
    download: <><path d="M12 3v12m-4-4 4 4 4-4"/><path d="M4 17v3h16v-3"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    x: <path d="M6 6l12 12M18 6 6 18"/>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    file: <><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h4M9 12h6M9 16h6"/></>,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

export default function App() {
  const [course, setCourse] = useState('')
  const [date, setDate] = useState(new Date().toLocaleDateString('en-CA'))
  const [recipientText, setRecipientText] = useState('')
  const [jobId, setJobId] = useState(new URLSearchParams(location.search).get('job'))
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const fileInput = useRef(null)
  const preview = useMemo(() => {
    try { return { rows: parseCsv(recipientText), error: '' } }
    catch (err) { return { rows: [], error: err.message } }
  }, [recipientText])

  useEffect(() => {
    if (!jobId) return
    let active = true, timer
    const load = async () => {
      try {
        const result = await request(`/jobs/${jobId}`)
        if (!active) return
        setJob(result)
        setError('')
        if (result.status === 'queued' || result.status === 'running') timer = setTimeout(load, 1500)
      } catch (err) { if (active) setError(err.message) }
    }
    load()
    return () => { active = false; clearTimeout(timer) }
  }, [jobId])

  const submit = async event => {
    event.preventDefault()
    setError('')
    if (preview.error) { setError(preview.error); return }
    if (!preview.rows.length) { setError('Add at least one recipient.'); return }
    if (preview.rows.length > 1000) { setError('A job can contain at most 1,000 recipients.'); return }
    setBusy(true)
    try {
      const result = await request('/jobs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course, issue_date: date, recipients: preview.rows }),
      })
      setJob(null)
      setJobId(result.job_id)
      history.replaceState(null, '', `?job=${result.job_id}`)
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  const loadFile = async event => {
    const file = event.target.files?.[0]
    if (!file) return
    setRecipientText(await file.text())
    event.target.value = ''
  }
  const done = (job?.counts.completed || 0) + (job?.counts.failed || 0)
  const progress = job ? Math.round(done / job.total * 100) : 0

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><div className="brand-mark"><Icon name="award" size={23}/></div><span>Certificate<span className="brand-light"> Studio</span></span></div>
      <span className="topbar-label">BULK GENERATION WORKSPACE</span>
    </header>
    <main>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow"><span className="eyebrow-line"/> CREATE &amp; DISTRIBUTE</span>
          <h1>Every achievement<br/><em>deserves a moment.</em></h1>
          <p>Generate polished certificates for your entire group in one go. Add your recipients, submit a job, and follow each result here.</p>
          <div className="hero-note"><span className="note-dot"/> One request. Up to 1,000 certificates.</div>
        </div>
        <div className="certificate-card" aria-label="Certificate design preview">
          <div className="certificate-inner">
            <div className="preview-ornament">✦</div>
            <div className="preview-title">CERTIFICATE OF COMPLETION</div>
            <div className="preview-small">PRESENTED TO</div>
            <div className="preview-name">Your Recipient</div>
            <div className="preview-rule"/>
            <div className="preview-small">FOR SUCCESSFULLY COMPLETING</div>
            <div className="preview-course">Your Course</div>
            <div className="preview-bottom">ISSUED WITH PRIDE <span>✦</span> CERTIFICATE STUDIO</div>
          </div>
          <div className="preview-caption">A preview of your certificate design</div>
        </div>
      </section>
      <section className="workspace-grid">
        <div className="panel form-panel">
          <div className="panel-heading"><div><span className="section-number">01 / NEW JOB</span><h2>Certificate details</h2></div><span className="heading-icon"><Icon name="file"/></span></div>
          <form onSubmit={submit}>
            <label htmlFor="course">Course or event name <span className="required">*</span></label>
            <input id="course" value={course} maxLength={200} onChange={e => setCourse(e.target.value)} placeholder="e.g. Advanced Python Workshop" required />
            <label htmlFor="issue-date">Issue date <span className="required">*</span></label>
            <input id="issue-date" type="date" value={date} onChange={e => setDate(e.target.value)} required />
            <div className="field-heading"><label htmlFor="recipients">Recipients <span className="required">*</span></label><span>{preview.rows.length} / 1,000</span></div>
            <p className="field-hint">One recipient per line: name, email, optional ID. A CSV header row is accepted.</p>
            <textarea id="recipients" rows="7" value={recipientText} onChange={e => setRecipientText(e.target.value)} placeholder={'Asha Rao,asha@example.org,P-001\nDev Shah,dev@example.org,P-002'} />
            <div className="input-actions">
              <button type="button" className="text-button" onClick={() => fileInput.current?.click()}><Icon name="upload" size={16}/> Upload CSV</button>
              <button type="button" className="text-button" onClick={() => setRecipientText(example)}>Use sample data</button>
              <input ref={fileInput} type="file" accept=".csv,.txt,text/csv,text/plain" onChange={loadFile} hidden />
            </div>
            {preview.error && <div className="inline-error">{preview.error}</div>}
            <button className="primary-button" type="submit" disabled={busy}>{busy ? 'Creating job…' : 'Generate certificates'}<Icon name="arrow" size={18}/></button>
          </form>
        </div>
        <div className="panel results-panel">
          <div className="panel-heading"><div><span className="section-number">02 / JOB STATUS</span><h2>Generation progress</h2></div><span className="heading-icon"><Icon name="clock"/></span></div>
          {error && <div className="error-banner" role="alert">{error}</div>}
          {!job && !jobId && <div className="empty-state"><div className="empty-icon"><Icon name="award" size={30}/></div><h3>Ready when you are</h3><p>Your job progress and certificate downloads will appear here after you submit recipients.</p></div>}
          {!job && jobId && <div className="empty-state"><div className="spinner"/><h3>Loading your job</h3><p>Fetching the latest certificate status.</p></div>}
          {job && <>
            <div className="job-summary"><div><span className="muted-label">CURRENT JOB</span><strong>{job.course}</strong><span className="job-id">ID {job.job_id}</span></div><span className={`status-pill ${job.status}`}>{job.status.replaceAll('_', ' ')}</span></div>
            <div className="progress-heading"><strong>{progress}% complete</strong><span>{done} of {job.total} processed</span></div>
            <div className="progress-track"><div className="progress-fill" style={{ width: `${progress}%` }}/></div>
            <div className="stat-grid"><div><strong>{job.counts.completed}</strong><span>Completed</span></div><div><strong>{job.counts.failed}</strong><span>Failed</span></div><div><strong>{job.counts.queued}</strong><span>Queued</span></div></div>
            <div className="recipient-heading"><h3>Recipients</h3><span>{job.total} total</span></div>
            <div className="recipient-list">{job.recipients.map(person => <div className="recipient-row" key={person.id}>
              <div className={`recipient-avatar ${person.status}`}>{person.status === 'completed' ? <Icon name="check" size={17}/> : person.status === 'failed' ? <Icon name="x" size={16}/> : <Icon name="clock" size={16}/>}</div>
              <div className="recipient-info"><strong>{person.name || `Recipient ${person.position + 1}`}</strong><span>{person.error || person.email || 'Invalid recipient data'}</span></div>
              {person.download_url ? <a className="download-button" href={`/api${person.download_url}`} title="Download PDF"><Icon name="download" size={18}/><span>PDF</span></a> : <span className={`row-state ${person.status}`}>{person.status}</span>}
            </div>)}</div>
          </>}
        </div>
      </section>
    </main>
    <footer><span>Certificate Studio</span><span>Made for moments that matter.</span></footer>
  </div>
}

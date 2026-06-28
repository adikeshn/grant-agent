import { useState, useEffect, useRef } from 'react';
import { startIngestion, pollIngestion } from './api';

const POLL_INTERVAL_MS = 3000;

const DEFAULT_FORM = {
  name: '',
  fetch_nsf: true,
  fetch_nih: false,
  keywords: '',   // comma-separated in UI, split to array on submit
  date_from: '',
  date_to: '',
  max_results: 50,
};

export default function IngestPanel({ onDomainReady }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState(null); // 'PENDING' | 'SUCCESS' | 'FAILURE' | null
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const pollRef = useRef(null);

  // Stop polling on unmount
  useEffect(() => () => clearInterval(pollRef.current), []);

  function startPolling(id) {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await pollIngestion(id);
        setStatus(res.status);
        if (res.status === 'SUCCESS') {
          setResult(res.result);
          clearInterval(pollRef.current);
          // Surface the domain name to parent so it can pre-fill the domain field
          if (onDomainReady) onDomainReady(form.name.trim());
        } else if (res.status === 'FAILURE') {
          setError('Ingestion task failed. Check backend logs.');
          clearInterval(pollRef.current);
        }
      } catch (e) {
        setError(e.message);
        clearInterval(pollRef.current);
      }
    }, POLL_INTERVAL_MS);
  }

  async function handleSubmit() {
    setError(null);
    setStatus(null);
    setResult(null);
    setTaskId(null);

    const keywords = form.keywords
      .split(',')
      .map((k) => k.trim())
      .filter(Boolean);

    if (!form.name.trim()) return setError('Domain name is required.');
    if (keywords.length === 0) return setError('Add at least one keyword.');
    if (!form.fetch_nsf && !form.fetch_nih) return setError('Select at least one source (NSF or NIH).');

    const payload = {
      name: form.name.trim(),
      fetch_nsf: form.fetch_nsf,
      fetch_nih: form.fetch_nih,
      keywords,
      date_from: form.date_from || '',
      date_to: form.date_to || '',
      max_results: Number(form.max_results) || 50,
    };

    setSubmitting(true);
    try {
      const res = await startIngestion(payload);
      setTaskId(res.task_id);
      setStatus('PENDING');
      startPolling(res.task_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    clearInterval(pollRef.current);
    setTaskId(null);
    setStatus(null);
    setResult(null);
    setError(null);
    setForm(DEFAULT_FORM);
  }

  const running = status === 'PENDING' || status === 'STARTED';
  const done = status === 'SUCCESS';
  const failed = status === 'FAILURE' || (error && !running);

  return (
    <div className="ingest-panel">
      <button
        className="ingest-toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="ingest-toggle-icon">{open ? '−' : '+'}</span>
        <span>Ingest corpus</span>
      </button>

      {open && (
        <div className="ingest-form">
          {/* Domain name */}
          <div className="ingest-field">
            <label>Domain name</label>
            <input
              className="domain-input"
              placeholder="e.g. reinforcement learning"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              disabled={running}
              spellCheck={false}
            />
          </div>

          {/* Keywords */}
          <div className="ingest-field">
            <label>Keywords <span className="ingest-hint-inline">comma-separated</span></label>
            <input
              className="domain-input"
              placeholder="deep RL, policy gradient, MDP"
              value={form.keywords}
              onChange={(e) => setForm((f) => ({ ...f, keywords: e.target.value }))}
              disabled={running}
              spellCheck={false}
            />
          </div>

          {/* Sources */}
          <div className="ingest-field">
            <label>Sources</label>
            <div className="ingest-checkboxes">
              <label className="ingest-check-label">
                <input
                  type="checkbox"
                  checked={form.fetch_nsf}
                  onChange={(e) => setForm((f) => ({ ...f, fetch_nsf: e.target.checked }))}
                  disabled={running}
                />
                NSF
              </label>
              <label className="ingest-check-label">
                <input
                  type="checkbox"
                  checked={form.fetch_nih}
                  onChange={(e) => setForm((f) => ({ ...f, fetch_nih: e.target.checked }))}
                  disabled={running}
                />
                NIH
              </label>
            </div>
          </div>

          {/* Max results */}
          <div className="ingest-field">
            <label>Max results</label>
            <input
              className="domain-input"
              type="number"
              min={1}
              max={500}
              value={form.max_results}
              onChange={(e) => setForm((f) => ({ ...f, max_results: e.target.value }))}
              disabled={running}
            />
          </div>

          {/* Date range */}
          <div className="ingest-field">
            <label>Date range <span className="ingest-hint-inline">optional</span></label>
            <div className="ingest-date-row">
              <input
                className="domain-input"
                type="date"
                value={form.date_from}
                onChange={(e) => setForm((f) => ({ ...f, date_from: e.target.value }))}
                disabled={running}
              />
              <span className="ingest-date-sep">→</span>
              <input
                className="domain-input"
                type="date"
                value={form.date_to}
                onChange={(e) => setForm((f) => ({ ...f, date_to: e.target.value }))}
                disabled={running}
              />
            </div>
          </div>

          {/* Status / feedback */}
          {error && <div className="ingest-error">{error}</div>}

          {taskId && (
            <div className={`ingest-status ${done ? 'done' : failed ? 'failed' : 'running'}`}>
              {running && (
                <>
                  <span className="ingest-spinner" />
                  <span>Processing… task {taskId.slice(0, 8)}</span>
                </>
              )}
              {done && (
                <span>✓ Done — {result} chunks ingested into <strong>{form.name}</strong></span>
              )}
              {failed && !error && <span>✗ Task failed</span>}
            </div>
          )}

          {/* Actions */}
          <div className="ingest-actions">
            {!running && !done && (
              <button
                className="ingest-submit-btn"
                onClick={handleSubmit}
                disabled={submitting}
              >
                {submitting ? 'Starting…' : 'Start ingestion'}
              </button>
            )}
            {(done || failed) && (
              <button className="ingest-reset-btn" onClick={handleReset}>
                New ingestion
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

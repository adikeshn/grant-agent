const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

/**
 * POST /query
 * @param {string} query
 * @param {string} domain
 * @param {Array<{role: string, content: string}>} history
 * @returns {Promise<{error: boolean, response: string, sources: Array, history: Array}>}
 */
export async function sendQuery(query, domain, history = []) {
  const res = await fetch(`${BASE_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, domain, history }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${text}`);
  }

  return res.json();
}

/**
 * POST /injest  — kicks off a Celery ingestion task
 * @param {object} domainRequest  matches DomainRequest schema
 * @returns {Promise<{task_id: string}>}
 */
export async function startIngestion(domainRequest) {
  const res = await fetch(`${BASE_URL}/injest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(domainRequest),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${text}`);
  }

  return res.json();
}

/**
 * GET /poll_injest?task_id=...
 */
export async function pollIngestion(taskId) {
  const res = await fetch(`${BASE_URL}/poll_injest?task_id=${encodeURIComponent(taskId)}`);
  if (!res.ok) throw new Error(`Poll error ${res.status}`);
  return res.json();
}

/**
 * GET /domains — returns all ingested domain names
 * @returns {Promise<{unique_domains: string[]}>}
 */
export async function getDomains() {
  const res = await fetch(`${BASE_URL}/domains`);
  if (!res.ok) throw new Error(`Domains fetch error ${res.status}`);
  return res.json();
}

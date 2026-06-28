import { useState, useRef, useEffect, useCallback } from 'react';
import { sendQuery, getDomains } from './api';
import SourcesCard from './SourcesCard';
import IngestPanel from './IngestPanel';
import ReactMarkdown from 'react-markdown';
import './index.css';

const STORAGE_KEY = 'grant_agent_history';

function useAutoResize(ref) {
  const resize = useCallback(() => {
    if (!ref.current) return;
    ref.current.style.height = 'auto';
    ref.current.style.height = Math.min(ref.current.scrollHeight, 140) + 'px';
  }, [ref]);
  return resize;
}

export default function App() {
  const [domain, setDomain] = useState('');
  const [domains, setDomains] = useState([]);        // list from /domains
  const [domainsLoading, setDomainsLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]); // [{role, content, sources, error}]
  const [apiHistory, setApiHistory] = useState([]); // [{role, content}] — sent to API
  const [loading, setLoading] = useState(false);

  const threadRef = useRef(null);
  const textareaRef = useRef(null);
  const resize = useAutoResize(textareaRef);

  // Scroll to bottom when messages change
  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // Persist to sessionStorage whenever anything relevant changes
  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ domain, messages, apiHistory }));
  }, [messages, domain, apiHistory]);

  async function fetchDomains() {
    setDomainsLoading(true);
    try {
      const res = await getDomains();
      const list = res.unique_domains || [];
      setDomains(list);
      // If the saved domain is still valid keep it; otherwise default to first
      setDomain((prev) => {
        if (prev && list.includes(prev)) return prev;
        return list[0] || '';
      });
    } catch {
      // API unreachable — leave domains empty, user sees the empty state
    } finally {
      setDomainsLoading(false);
    }
  }

  // Restore session + fetch domains on mount
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) {
        const { domain: d, messages: m, apiHistory: h } = JSON.parse(saved);
        setDomain(d || '');
        setMessages(m || []);
        setApiHistory(h || []);
      }
    } catch {}
    fetchDomains();
  }, []);

  const canSend = domain.trim() && query.trim() && !loading;

  async function handleSend() {
    if (!canSend) return;

    const userQuery = query.trim();
    setQuery('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    // Optimistically add the user message
    setMessages((prev) => [...prev, { role: 'user', content: userQuery }]);
    setLoading(true);

    try {
      const result = await sendQuery(userQuery, domain.trim(), apiHistory);

      const assistantMsg = {
        role: 'assistant',
        content: result.response,
        sources: result.sources || [],
        error: result.error,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setApiHistory(result.history || []);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: err.message || 'Could not reach the API. Is the server running?',
          sources: [],
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleClear() {
    setMessages([]);
    setApiHistory([]);
    sessionStorage.removeItem(STORAGE_KEY);
  }

  // Derive conversation history for the sidebar (just user turns)
  const userTurns = messages.filter((m) => m.role === 'user');

  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>Grant Intelligence</h1>
          <p>NSF · NIH award explorer</p>
        </div>

        <div className="sidebar-section">
          <label>Domain</label>
          {domainsLoading ? (
            <div className="domain-select-loading">loading…</div>
          ) : domains.length === 0 ? (
            <div className="domain-select-empty">No domains yet — ingest a corpus first.</div>
          ) : (
            <select
              className="domain-select"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
            >
              {domains.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          )}
        </div>

        <IngestPanel onDomainReady={(name) => { setDomain(name); fetchDomains(); }} />

        {userTurns.length > 0 && (
          <div className="sidebar-section">
            <label>This session</label>
            <div className="history-list">
              {userTurns.slice(-8).map((m, i) => (
                <button
                  key={i}
                  className="history-item"
                  title={m.content}
                  onClick={() => {
                    if (threadRef.current) {
                      // Scroll to the message at that index
                      const pairs = threadRef.current.querySelectorAll('.message-pair');
                      if (pairs[i]) pairs[i].scrollIntoView({ behavior: 'smooth' });
                    }
                  }}
                >
                  {m.content}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.length > 0 && (
          <button className="clear-btn" onClick={handleClear}>
            Clear session
          </button>
        )}
      </aside>

      {/* ── Main ── */}
      <div className="main">
        <div className="thread" ref={threadRef}>
          {messages.length === 0 && !loading && (
            <div className="empty-state">
              <div className="icon">⬡</div>
              <p>Set a domain, then ask a question.</p>
            </div>
          )}

          {/* Pair up user + assistant messages */}
          {messages.reduce((acc, msg, i) => {
            if (msg.role === 'user') {
              const next = messages[i + 1];
              acc.push(
                <div className="message-pair" key={i}>
                  <div className="user-bubble">{msg.content}</div>
                  {next && next.role === 'assistant' && (
                    <div className="assistant-block">
                      <span className="assistant-label">
                        {next.error ? 'Error' : 'Grant Intelligence'}
                      </span>
                      {next.error ? (
                        <div className="error-body">{next.content}</div>
                      ) : (
                        <div className="assistant-body">
                          <ReactMarkdown>{next.content}</ReactMarkdown>
                        </div>
                      )}
                      <SourcesCard sources={next.sources} />
                    </div>
                  )}
                </div>
              );
            }
            return acc;
          }, [])}

          {loading && (
            <div className="loading-block">
              <span className="assistant-label">Grant Intelligence</span>
              <div className="loading-dots">
                <span /><span /><span />
              </div>
              <span className="loading-hint">querying {domain || 'database'}…</span>
            </div>
          )}
        </div>

        {/* ── Input zone ── */}
        <div className="input-zone">
          <div className="domain-badge">
            <div className="domain-badge-dot" />
            <span>domain: </span>
            <strong>{domain || 'not set'}</strong>
          </div>

          <div className="input-row">
            <span className="prompt-prefix">&gt;</span>
            <textarea
              ref={textareaRef}
              className="query-textarea"
              placeholder={
                domain
                  ? `Ask about ${domain} grants…`
                  : 'Set a domain in the sidebar first'
              }
              value={query}
              rows={1}
              onChange={(e) => {
                setQuery(e.target.value);
                resize();
              }}
              onKeyDown={handleKeyDown}
              disabled={loading}
              spellCheck={false}
            />
            <button className="send-btn" onClick={handleSend} disabled={!canSend}>
              Send
            </button>
          </div>
          <div className="input-hint">↵ send · shift+↵ newline</div>
        </div>
      </div>
    </div>
  );
}

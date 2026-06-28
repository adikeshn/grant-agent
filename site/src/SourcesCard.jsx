/**
 * Sources returned from the API are either:
 *   - chunk path: list of metadata dicts with award_id, source, year, amount, institution, pi_name
 *   - graph path: list of title strings
 *
 * We normalise both into a uniform display.
 */
export default function SourcesCard({ sources }) {
  if (!sources || sources.length === 0) return null;

  const normalised = sources.map((s) => {
    if (typeof s === 'string') return { title: s };
    return {
      title: s.title || s.award_id || '—',
      pi: s.pi_name,
      institution: s.institution,
      year: s.year,
      amount: s.amount,
      agency: s.source,
      award_id: s.award_id,
    };
  });

  return (
    <div className="sources-card">
      <div className="sources-header">
        <span>Sources</span>
        <span className="sources-count">{normalised.length}</span>
      </div>
      <div className="sources-list">
        {normalised.map((s, i) => (
          <div className="source-row" key={i}>
            <span className="source-index">{String(i + 1).padStart(2, '0')}</span>
            <div className="source-meta">
              <span className="source-title">{s.title}</span>
              {(s.pi || s.institution || s.year) && (
                <span className="source-detail">
                  {[
                    s.pi,
                    s.institution,
                    s.year && String(s.year),
                    s.amount && `$${Number(s.amount).toLocaleString()}`,
                    s.agency && s.agency.toUpperCase(),
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

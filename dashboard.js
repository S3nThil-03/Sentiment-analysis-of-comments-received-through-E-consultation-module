import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { API_BASE_URL, loadCommentsCsvWithFallback, loadLiveComments } from './dataLoader';
import Charts from './components/Charts';
import WordCloudPanel from './components/WordCloudPanel';
import CommentsTable from './components/CommentsTable';
import './enhanced-ui.css'; // <-- ENSURE YOU IMPORT THE NEW CSS

const csvMap = {
    site1: [
      '/outputs/comments_processed_site1.csv',
      '/outputs/comments_raw_site1.csv',
    ],
    site2: [
      '/outputs/comments_processed_site2.csv',
      '/outputs/comments_raw_site2.csv',
    ],
};

function toFriendlyLiveError(message) {
  const raw = String(message || '');
  if (raw.includes('ECONNREFUSED') || raw.includes('Failed to fetch') || raw.includes('NetworkError')) {
    return 'Live backend is not running on port 5000. Showing local CSV data.';
  }
  if (raw.includes('500')) {
    return 'Live backend returned an internal error. Showing local CSV data.';
  }
  return `Live API unavailable, showing local CSV data. (${raw})`;
}

export default function Dashboard() {
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [source, setSource] = useState('site1');
  const [liveState, setLiveState] = useState({
    inProgress: false,
    lastUpdated: null,
    lastError: null,
    sourceName: '',
    geminiEnabled: false,
  });

  const loadData = useCallback(async (src, options = {}) => {
    const { background = false } = options;

    if (!background) {
      setLoading(true);
    }
    setError(null);

    try {
      const liveData = await loadLiveComments(src);
      setComments(liveData.comments);
      setLiveState({
        inProgress: liveData.inProgress,
        lastUpdated: liveData.lastUpdated,
        lastError: liveData.lastError,
        sourceName: liveData.sourceName,
        geminiEnabled: liveData.geminiEnabled,
      });
    } catch (err) {
      // Backend API unavailable: fallback to static CSV files.
      try {
        const paths = csvMap[src];
        const data = await loadCommentsCsvWithFallback(paths);
        setComments(data);
        setLiveState((prev) => ({
          ...prev,
          inProgress: false,
          lastError: toFriendlyLiveError(err.message),
          sourceName: prev.sourceName || (src === 'site1' ? 'Mann Ki Baat (English)' : 'Akshar Hindi (Hindi)'),
        }));
      } catch (fallbackErr) {
        setError('Failed to load data: ' + fallbackErr.message);
      }
    } finally {
      if (!background) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadData(source);
  }, [loadData, source]);

  useEffect(() => {
    const timer = setInterval(() => {
      loadData(source, { background: true });
    }, 5000);

    return () => clearInterval(timer);
  }, [loadData, source]);

  const onManualRefresh = useCallback(async () => {
    try {
      await fetch(`${API_BASE_URL}/api/refresh-now?source=${encodeURIComponent(source)}`);
    } catch (e) {
      // Ignore errors here; periodic polling and loadData handle real errors.
    }
    loadData(source);
  }, [loadData, source]);

  const metrics = useMemo(() => {
    const counts = comments.reduce((acc, c) => {
      const key = String(c.sentiment || 'unknown').toLowerCase();
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, { positive: 0, negative: 0, neutral: 0, unknown: 0 });

    return [
      { label: 'Total Comments', value: comments.length, tone: 'neutral' },
      { label: 'Positive', value: counts.positive, tone: 'positive' },
      { label: 'Negative', value: counts.negative, tone: 'negative' },
      { label: 'Neutral', value: counts.neutral, tone: 'neutral' },
      { label: 'Unknown', value: counts.unknown, tone: 'unknown' },
    ];
  }, [comments]);

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div className="header-title">
          <h1>MyGov Comments Dashboard</h1>
          <p>Analyze public feedback with sentiment, summary, and word cloud.</p>
          <p className="live-meta">
            Live update: every 5 seconds
            {liveState.lastUpdated ? ` | Last update: ${new Date(liveState.lastUpdated).toLocaleString()}` : ''}
            {liveState.inProgress ? ' | Scraping in progress...' : ''}
            {liveState.sourceName ? ` | Source: ${liveState.sourceName}` : ''}
            {liveState.geminiEnabled ? ' | Gemini Assist: ON' : ' | Gemini Assist: OFF'}
          </p>
          {liveState.lastError ? <p className="live-warning">{liveState.lastError}</p> : null}
        </div>
        <div className="controls">
          <select value={source} onChange={(e) => setSource(e.target.value)} disabled={loading} className="select">
            <option value="site1">Mann Ki Baat (English)</option>
            <option value="site2">Akshar Hindi (Hindi)</option>
          </select>
          <button onClick={onManualRefresh} disabled={loading} className="btn">
            {loading ? 'Loading...' : 'Refresh Data'}
          </button>
        </div>
      </header>

      {error && <div className="card" style={{backgroundColor: '#fee2e2', color: '#b91c1c'}}>{error}</div>}

      {!loading && !error && (
        <>
          <section className="kpi-grid">
            {metrics.map((item) => (
              <div key={item.label} className={`kpi-card kpi-${item.tone}`}>
                <span className="kpi-label">{item.label}</span>
                <strong className="kpi-value">{item.value}</strong>
              </div>
            ))}
          </section>

          <div className="card">
            <h2 className="card-title">Sentiment Analysis Overview</h2>
            <Charts comments={comments} />
          </div>

          <div className="grid">
            <div className="card">
              <h2 className="card-title">Word Cloud</h2>
              <WordCloudPanel comments={comments} />
            </div>
            <div className="card">
              <CommentsTable comments={comments} sourceName={liveState.sourceName || source} />
            </div>
          </div>
        </>
      )}
    </main>
  );
}

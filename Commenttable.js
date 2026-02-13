import React, { useMemo, useState } from 'react';
import Papa from 'papaparse';

const languageMap = {
  af: 'English',
  en: 'English',
  hi: 'Hindi',
  mr: 'Marathi',
  bn: 'Bengali',
  gu: 'Gujarati',
  ta: 'Tamil',
  te: 'Telugu',
  kn: 'Kannada',
  ml: 'Malayalam',
  pa: 'Punjabi',
  or: 'Odia',
  ur: 'Urdu',
};

const getLanguageName = (value) => {
  const text = String(value || '').trim();
  if (!text) return 'Unknown';

  const code = text.toLowerCase();
  if (languageMap[code]) return languageMap[code];
  if (text.length > 3) return text;
  return code.toUpperCase();
};

const normalizeSentimentClass = (sentiment) => {
  const label = String(sentiment || '').trim().toLowerCase();
  if (['positive', 'negative', 'neutral', 'unknown'].includes(label)) return label;
  if (label.includes('pos')) return 'positive';
  if (label.includes('neg')) return 'negative';
  if (label.includes('neu')) return 'neutral';
  return 'unknown';
};

function formatDateForFilename(date) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

export default function CommentsTable({ comments, sourceName }) {
  const [authorFilter, setAuthorFilter] = useState('All');
  const [query, setQuery] = useState('');

  const authors = useMemo(() => {
    const unique = new Set(comments.map((c) => c.author || 'Unknown'));
    return ['All', ...Array.from(unique).sort((a, b) => a.localeCompare(b))];
  }, [comments]);

  const filteredComments = useMemo(() => {
    const q = query.trim().toLowerCase();
    return comments.filter((comment) => {
      const authorMatch = authorFilter === 'All' || (comment.author || 'Unknown') === authorFilter;
      if (!authorMatch) return false;
      if (!q) return true;
      return (
        String(comment.text || '').toLowerCase().includes(q) ||
        String(comment.summary || '').toLowerCase().includes(q) ||
        String(comment.author || '').toLowerCase().includes(q)
      );
    });
  }, [comments, authorFilter, query]);

  const onExportCsv = () => {
    const rows = filteredComments.map((comment) => ({
      source: sourceName || 'MyGov',
      author: comment.author || 'Unknown',
      language: getLanguageName(comment.lang),
      sentiment: normalizeSentimentClass(comment.sentiment).toUpperCase(),
      sentiment_score: (Number(comment.sentiment_score) || 0).toFixed(4),
      timestamp: comment.timestamp || '',
      comment: comment.text || '',
      summary: comment.summary || '',
    }));

    const csv = Papa.unparse(rows, { header: true, quotes: true });
    const blob = new Blob(['\uFEFF', csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `mygov_comments_${formatDateForFilename(new Date())}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div className="comments-table-header">
        <h2 className="card-title" style={{ margin: 0 }}>Comments ({filteredComments.length})</h2>
        <div className="table-actions">
          <input
            className="search-input"
            type="text"
            placeholder="Search comments..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select className="select" value={authorFilter} onChange={(e) => setAuthorFilter(e.target.value)}>
            {authors.map((author) => <option key={author} value={author}>{author}</option>)}
          </select>
          <button className="btn btn-secondary" type="button" onClick={onExportCsv}>
            Export CSV
          </button>
        </div>
      </div>

      <div className="comments-list">
        {filteredComments.length === 0 ? (
          <div className="empty-state">No comments found for current filters.</div>
        ) : null}

        {filteredComments.map((comment) => {
          const sentimentClass = normalizeSentimentClass(comment.sentiment);
          return (
            <div className="comment-item" key={comment.id}>
              <div className="comment-header">
                <span className="author">{comment.author}</span>
                <div className="comment-meta">
                  <span className={`sentiment-badge sentiment-${sentimentClass}`}>{sentimentClass}</span>
                  <span className={`sentiment-score-text score-${sentimentClass}`}>
                    {(Number(comment.sentiment_score) || 0).toFixed(2)}
                  </span>
                  <span className="lang-badge">{getLanguageName(comment.lang)}</span>
                </div>
              </div>

              <p className="comment-text">{comment.text}</p>

              {comment.summary && comment.summary !== comment.text ? (
                <p className="comment-summary">
                  <strong>Summary:</strong> {comment.summary}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
    </>
  );
}

import Papa from 'papaparse';
import Sentiment from 'sentiment';

const VALID_SENTIMENTS = new Set(['positive', 'negative', 'neutral', 'unknown']);
const sentimentAnalyzer = new Sentiment();
export const API_BASE_URL = process.env.REACT_APP_API_BASE || 'http://localhost:5000';

const clamp = (v, min, max) => Math.max(min, Math.min(v, max));

function normalizeSentiment(raw) {
  const label = String(raw || '').trim().toLowerCase();
  if (VALID_SENTIMENTS.has(label)) return label;

  const aliases = {
    pos: 'positive',
    neg: 'negative',
    neu: 'neutral',
    label_0: 'negative',
    label_1: 'neutral',
    label_2: 'positive',
  };

  if (aliases[label]) return aliases[label];
  if (label.includes('pos')) return 'positive';
  if (label.includes('neg')) return 'negative';
  if (label.includes('neu')) return 'neutral';

  return 'unknown';
}

function deriveSentimentFromText(text) {
  const cleaned = String(text || '').trim();
  if (!cleaned) {
    return { sentiment: 'unknown', score: 0 };
  }
  if (cleaned.length <= 3) {
    return { sentiment: 'unknown', score: 0 };
  }

  // Sentiment.js works best for latin text; if not, fall back to neutral.
  const latinLike = /[a-zA-Z]/.test(cleaned);
  if (!latinLike) {
    return { sentiment: 'neutral', score: 0.5 };
  }

  const result = sentimentAnalyzer.analyze(cleaned);
  const rawScore = Number(result.score) || 0;
  if (rawScore > 0) {
    return { sentiment: 'positive', score: clamp(0.55 + (rawScore * 0.06), 0, 1) };
  }
  if (rawScore < 0) {
    return { sentiment: 'negative', score: clamp(0.55 + (Math.abs(rawScore) * 0.06), 0, 1) };
  }
  return { sentiment: 'neutral', score: 0.5 };
}

function normalizeRow(row, index, sourceUrl) {
  const text = (row.text || '').trim();
  if (!text) {
    return null;
  }

  let sentiment = normalizeSentiment(row.sentiment);
  const parsedScore = parseFloat(row.sentiment_score);
  let sentimentScore = Number.isFinite(parsedScore) ? parsedScore : null;

  if (sentiment === 'unknown' || sentimentScore === null) {
    const guessed = deriveSentimentFromText(text);
    if (sentiment === 'unknown') {
      sentiment = guessed.sentiment;
    }
    if (sentimentScore === null) {
      sentimentScore = guessed.score;
    }
  }

  if (sentimentScore === null) {
    sentimentScore = 0;
  }

  return {
    id: `${sourceUrl}-${index}`,
    author: (row.author || '').trim() || 'Unknown',
    timestamp: (row.timestamp || '').trim() || '',
    text,
    lang: (row.lang || '').trim() || 'Unknown',
    sentiment,
    sentiment_score: sentimentScore,
    summary: (row.summary || '').trim() || text,
  };
}

export async function loadCommentsCsv(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch CSV: ${response.statusText}`);
  }
  const csvText = await response.text();

  return new Promise((resolve, reject) => {
    Papa.parse(csvText, {
      header: true,
      skipEmptyLines: true,
      transformHeader: header => header.trim(),
      complete: (results) => {
        if (results.errors.length) {
          console.error("Parsing errors:", results.errors);
          return reject(new Error("Failed to parse CSV file."));
        }

        if (!results.data || results.data.length === 0) {
            console.warn("CSV file loaded, but no data was parsed. Check CSV headers.");
            return resolve([]);
        }

        const cleanedData = results.data
          .map((row, index) => normalizeRow(row, index, url))
          .filter(Boolean);

        resolve(cleanedData);
      },
      error: (err) => {
        console.error("Papa Parse error:", err);
        reject(err);
      },
    });
  });
}

export async function loadCommentsCsvWithFallback(urls) {
  let lastError = null;

  for (const url of urls) {
    try {
      const data = await loadCommentsCsv(url);
      if (data.length > 0) {
        return data;
      }
      lastError = new Error(`No rows found in ${url}`);
    } catch (err) {
      lastError = err;
    }
  }

  throw lastError || new Error('No CSV data could be loaded from fallback sources.');
}

export async function loadLiveComments(source) {
  const response = await fetch(
    `${API_BASE_URL}/api/live-comments?source=${encodeURIComponent(source)}&_ts=${Date.now()}`,
    { cache: 'no-store' }
  );
  if (!response.ok) {
    throw new Error(`Live API failed: ${response.status} ${response.statusText}`);
  }

  const payload = await response.json();
  const comments = Array.isArray(payload.comments) ? payload.comments : [];
  const cleaned = comments
    .map((row, index) => normalizeRow(row, index, `live-${source}`))
    .filter(Boolean);

  return {
    comments: cleaned,
    lastUpdated: payload.last_updated || null,
    inProgress: Boolean(payload.in_progress),
    lastError: payload.last_error || null,
    sourceName: payload.source_name || source,
    geminiEnabled: Boolean(payload.gemini_enabled),
  };
}

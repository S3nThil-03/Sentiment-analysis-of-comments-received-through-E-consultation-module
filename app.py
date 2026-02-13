from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import threading
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from flask_cors import CORS
from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

try:
    import google.generativeai as genai
except Exception:
    genai = None

warnings.filterwarnings("ignore", category=FutureWarning)
DetectorFactory.seed = 0

app = Flask(__name__)
CORS(app)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DASHBOARD_OUTPUT_DIR = PROJECT_ROOT / "dashboard" / "public" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DASHBOARD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REFRESH_INTERVAL_SECONDS = int(os.getenv("REFRESH_INTERVAL_SECONDS", "5"))
MAX_PAGES_PER_SCRAPE = int(os.getenv("MAX_PAGES_PER_SCRAPE", "50"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SITE_CONFIG = {
    "site1": {
        "name": "Mann Ki Baat (English)",
        "url": "https://www.mygov.in/group-issue/inviting-ideas-mann-ki-baat-prime-minister-narendra-modi-28th-september-2025/",
        "csv": "comments_processed_site1.csv",
        "raw_csv": "comments_raw_site1.csv",
    },
    "site2": {
        "name": "Akshar Hindi (Hindi)",
        "url": "https://www.mygov.in/group-issue/inviting-comments-draft-indian-language-standard-akshar-hindi-language/",
        "csv": "comments_processed_site2.csv",
        "raw_csv": "comments_raw_site2.csv",
    },
}

LANGUAGE_CODE_MAP = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "mr": "Marathi",
    "gu": "Gujarati",
    "bn": "Bengali",
    "pa": "Punjabi",
    "or": "Odia",
    "ur": "Urdu",
}

SCRIPT_PATTERNS = [
    (re.compile(r"[\u0900-\u097F]"), "Hindi"),
    (re.compile(r"[\u0980-\u09FF]"), "Bengali"),
    (re.compile(r"[\u0A00-\u0A7F]"), "Punjabi"),
    (re.compile(r"[\u0A80-\u0AFF]"), "Gujarati"),
    (re.compile(r"[\u0B00-\u0B7F]"), "Odia"),
    (re.compile(r"[\u0B80-\u0BFF]"), "Tamil"),
    (re.compile(r"[\u0C00-\u0C7F]"), "Telugu"),
    (re.compile(r"[\u0C80-\u0CFF]"), "Kannada"),
    (re.compile(r"[\u0D00-\u0D7F]"), "Malayalam"),
    (re.compile(r"[\u0600-\u06FF]"), "Urdu"),
]

POSITIVE_WORDS = {
    "good",
    "great",
    "excellent",
    "awesome",
    "amazing",
    "helpful",
    "best",
    "love",
    "support",
    "thank",
    "thanks",
    "semma",
    "vera",
    "level",
    "verithanam",
    "super",
    "nice",
    "improve",
    "improved",
    "useful",
}

NEGATIVE_WORDS = {
    "bad",
    "worst",
    "poor",
    "waste",
    "useless",
    "issue",
    "problem",
    "bug",
    "hate",
    "slow",
    "broken",
    "mokkai",
    "not",
    "spam",
    "fake",
    "difficult",
    "error",
    "dislike",
    "delay",
}

PLACEHOLDER_AUTHORS = {
    "",
    "unknown",
    "default icon for user",
    "home",
    "user",
}

JUNK_PATTERNS = [
    re.compile(r"^like\s*\(\d+\)\s*dislike\s*\(\d+\)", re.IGNORECASE),
    re.compile(r"facebook\s+twitter", re.IGNORECASE),
    re.compile(r"^report\s+spam", re.IGNORECASE),
]

DEFAULT_SENTIMENT_SCORE = {
    "positive": 0.62,
    "negative": 0.62,
    "neutral": 0.50,
    "unknown": 0.00,
}

CSV_FIELDS = [
    "author",
    "timestamp",
    "text",
    "lang",
    "sentiment",
    "sentiment_score",
    "summary",
]

_gemini_model = None
_gemini_model_lock = threading.Lock()
_gemini_enabled = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) and genai is not None
_gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

_analysis_cache: Dict[str, Dict] = {}
_analysis_cache_lock = threading.Lock()

_state_lock = threading.Lock()
_site_states: Dict[str, Dict] = {
    source_id: {
        "source_name": conf["name"],
        "comments": [],
        "last_updated": None,
        "in_progress": False,
        "last_error": None,
    }
    for source_id, conf in SITE_CONFIG.items()
}


def csv_path(source_id: str) -> Path:
    return OUTPUT_DIR / SITE_CONFIG[source_id]["csv"]


def raw_csv_path(source_id: str) -> Path:
    return OUTPUT_DIR / SITE_CONFIG[source_id]["raw_csv"]


def dashboard_csv_path(source_id: str) -> Path:
    return DASHBOARD_OUTPUT_DIR / SITE_CONFIG[source_id]["csv"]


def dashboard_raw_csv_path(source_id: str) -> Path:
    return DASHBOARD_OUTPUT_DIR / SITE_CONFIG[source_id]["raw_csv"]


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def normalize_sentiment(raw: str) -> str:
    label = normalize_whitespace(raw).lower()
    if label in {"positive", "negative", "neutral", "unknown"}:
        return label
    aliases = {
        "pos": "positive",
        "neg": "negative",
        "neu": "neutral",
        "label_0": "negative",
        "label_1": "neutral",
        "label_2": "positive",
    }
    if label in aliases:
        return aliases[label]
    if "pos" in label:
        return "positive"
    if "neg" in label:
        return "negative"
    if "neu" in label:
        return "neutral"
    return "unknown"


def is_placeholder_author(author: str) -> bool:
    cleaned = normalize_whitespace(author).lower()
    return cleaned in PLACEHOLDER_AUTHORS


def is_junk_or_boilerplate(text: str) -> bool:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return True
    if len(cleaned) < 3:
        return True
    for pattern in JUNK_PATTERNS:
        if pattern.search(cleaned):
            return True
    return False


def fix_mojibake(text: str) -> str:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return ""
    if "Ã" in cleaned or "Â" in cleaned or "â" in cleaned:
        try:
            repaired = cleaned.encode("latin1").decode("utf-8")
            return normalize_whitespace(repaired)
        except Exception:
            return cleaned
    return cleaned


def detect_language_from_script(text: str) -> str:
    for pattern, language in SCRIPT_PATTERNS:
        if pattern.search(text):
            return language
    if re.search(r"[A-Za-z]", text):
        return "English"
    return "Unknown"


def normalize_language_name(raw: str) -> str:
    value = normalize_whitespace(raw)
    if not value:
        return "Unknown"
    lowered = value.lower()
    if lowered in LANGUAGE_CODE_MAP:
        return LANGUAGE_CODE_MAP[lowered]
    titled = value.title()
    if titled in set(LANGUAGE_CODE_MAP.values()):
        return titled
    return value


def detect_language_name(text: str) -> str:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return "Unknown"

    script_guess = detect_language_from_script(cleaned)

    try:
        code = detect(cleaned)
        mapped = LANGUAGE_CODE_MAP.get(code.lower())
        if mapped:
            return mapped
    except LangDetectException:
        pass
    except Exception:
        pass

    return normalize_language_name(script_guess)


def short_summary(text: str, max_chars: int = 220) -> str:
    cleaned = normalize_whitespace(text)
    if len(cleaned) <= max_chars:
        return cleaned
    cut = cleaned[: max_chars - 3]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return f"{cut}..."


def get_gemini_model():
    global _gemini_model
    if not _gemini_enabled:
        return None

    if _gemini_model is not None:
        return _gemini_model

    with _gemini_model_lock:
        if _gemini_model is not None:
            return _gemini_model
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel(_gemini_model_name)
        return _gemini_model


def heuristic_sentiment(text: str) -> Dict:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return {
            "sentiment": "unknown",
            "sentiment_score": DEFAULT_SENTIMENT_SCORE["unknown"],
        }

    lowered = cleaned.lower()
    if len(lowered) <= 3:
        return {
            "sentiment": "unknown",
            "sentiment_score": DEFAULT_SENTIMENT_SCORE["unknown"],
        }

    words = re.findall(r"[a-zA-Z']+", lowered)
    pos = 0.0
    neg = 0.0

    for token in words:
        if token in POSITIVE_WORDS:
            pos += 1.0
        if token in NEGATIVE_WORDS:
            neg += 1.0

    pos += sum(lowered.count(x) for x in ["😀", "😄", "😊", "👍", "❤️", "❤", "🔥", "👏", "🙏"]) * 0.5
    neg += sum(lowered.count(x) for x in ["😡", "😞", "👎", "💔", "😢", "😭"]) * 0.5

    if re.search(r"\b(not|no|never)\s+(good|great|excellent|super|nice)\b", lowered):
        neg += 1.0
    if re.search(r"\b(not|no|never)\s+(bad|poor|waste|worst)\b", lowered):
        pos += 1.0

    delta = pos - neg

    if delta > 0.35:
        sentiment = "positive"
    elif delta < -0.35:
        sentiment = "negative"
    else:
        if re.search(r"[a-zA-Z\u0900-\u0D7F]", lowered):
            sentiment = "neutral"
        else:
            sentiment = "unknown"

    if sentiment in {"positive", "negative"}:
        score = min(0.99, 0.55 + min(abs(delta), 5.0) * 0.08)
    else:
        score = DEFAULT_SENTIMENT_SCORE[sentiment]

    return {
        "sentiment": sentiment,
        "sentiment_score": round(score, 4),
    }


def parse_gemini_json(raw_text: str) -> Optional[Dict]:
    if not raw_text:
        return None
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def analyze_with_gemini(text_input: str) -> Optional[Dict]:
    model = get_gemini_model()
    if model is None:
        return None

    prompt = f"""
You are an expert sentiment and language analyzer for Indian public comments.
Analyze the text and return ONLY JSON in this exact schema:
{{"sentiment":"POSITIVE|NEGATIVE|NEUTRAL|UNKNOWN","score":0.0-1.0,"language":"English/Hindi/Tamil/etc","summary":"one short summary"}}

Text: {text_input}
"""

    try:
        response = model.generate_content(prompt)
        parsed = parse_gemini_json(getattr(response, "text", ""))
        if not parsed:
            return None
        sentiment = normalize_sentiment(str(parsed.get("sentiment", "")))
        if sentiment == "unknown":
            return None
        score = safe_float(parsed.get("score", DEFAULT_SENTIMENT_SCORE[sentiment]), DEFAULT_SENTIMENT_SCORE[sentiment])
        language = normalize_language_name(str(parsed.get("language", "Unknown")))
        summary = short_summary(str(parsed.get("summary", text_input)))
        return {
            "sentiment": sentiment,
            "sentiment_score": max(0.0, min(1.0, score)),
            "lang": language,
            "summary": summary,
        }
    except Exception:
        return None


def analyze_comment(text: str) -> Dict:
    cleaned = fix_mojibake(text)
    if not cleaned:
        return {
            "sentiment": "unknown",
            "sentiment_score": DEFAULT_SENTIMENT_SCORE["unknown"],
            "lang": "Unknown",
            "summary": "",
        }

    cache_key = text_hash(cleaned)
    with _analysis_cache_lock:
        cached = _analysis_cache.get(cache_key)
    if cached:
        return cached

    local = heuristic_sentiment(cleaned)
    result = {
        "sentiment": local["sentiment"],
        "sentiment_score": local["sentiment_score"],
        "lang": detect_language_name(cleaned),
        "summary": short_summary(cleaned),
    }

    gemini = analyze_with_gemini(cleaned)
    if gemini:
        result = gemini

    with _analysis_cache_lock:
        _analysis_cache[cache_key] = result

    return result


def extract_comments_from_html(fragment_html: str) -> List[Dict]:
    soup = BeautifulSoup(fragment_html or "", "html.parser")
    rows: List[Dict] = []

    articles = soup.select("article.comment_row, article.comment")
    for article in articles:
        text_el = article.select_one("div.comment_body")
        if text_el is None:
            continue

        text = fix_mojibake(text_el.get_text(" ", strip=True))
        if is_junk_or_boilerplate(text):
            continue

        author_el = article.select_one("span.username, .username, .comment_user, .user-name")
        author = fix_mojibake(author_el.get_text(" ", strip=True) if author_el else "Unknown")
        if is_placeholder_author(author):
            author = "Unknown"

        ts_el = article.select_one("time, span.timeago, .submitted, .comment_date, .comment-time")
        timestamp = fix_mojibake(ts_el.get_text(" ", strip=True) if ts_el else "")

        rows.append({"author": author or "Unknown", "timestamp": timestamp, "text": text})

    if rows:
        return rows

    fallback_nodes = soup.select("div.comment_body")
    for node in fallback_nodes:
        text = fix_mojibake(node.get_text(" ", strip=True))
        if is_junk_or_boilerplate(text):
            continue
        author_node = node.find_previous("span", class_="username")
        author = fix_mojibake(author_node.get_text(" ", strip=True) if author_node else "Unknown")
        if is_placeholder_author(author):
            author = "Unknown"
        rows.append({"author": author or "Unknown", "timestamp": "", "text": text})

    return rows


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def extract_view_params(page_html: str) -> Dict[str, str]:
    match = re.search(r"jQuery\.extend\(Drupal\.settings,\s*(\{.*?\})\s*\);", page_html, re.DOTALL)
    if not match:
        raise RuntimeError("Could not find Drupal settings JSON in source page.")

    settings = json.loads(match.group(1))
    ajax_views = (settings.get("views") or {}).get("ajaxViews") or {}
    if not ajax_views:
        raise RuntimeError("Could not find ajax view configuration for comments.")

    selected = None
    for view_data in ajax_views.values():
        if "comment" in str(view_data.get("view_name", "")).lower():
            selected = view_data
            break
    if selected is None:
        selected = next(iter(ajax_views.values()))

    required_keys = [
        "view_name",
        "view_display_id",
        "view_args",
        "view_path",
        "view_base_path",
        "view_dom_id",
        "pager_element",
    ]
    params = {key: str(selected.get(key, "")) for key in required_keys}
    if not params["view_name"] or not params["view_dom_id"]:
        raise RuntimeError("Invalid ajax view configuration received.")
    return params


def fetch_ajax_page(source_url: str, view_params: Dict[str, str], page_token: str) -> str:
    params = dict(view_params)
    params["_drupal_ajax"] = "1"
    params["page"] = page_token

    headers = dict(REQUEST_HEADERS)
    headers["X-Requested-With"] = "XMLHttpRequest"
    headers["Referer"] = source_url

    ajax_url = urljoin(source_url, "/views/ajax/")
    response = requests.get(ajax_url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, list):
        return ""

    for item in payload:
        if item.get("command") == "insert" and isinstance(item.get("data"), str):
            return item["data"]

    return ""


def make_comment_key(author: str, text: str) -> str:
    return text_hash(f"{normalize_whitespace(author).lower()}|{normalize_whitespace(text).lower()}")


def scrape_comments_paginated(source_url: str) -> List[Dict]:
    page_html = fetch_html(source_url)
    view_params = extract_view_params(page_html)

    collected: List[Dict] = []
    seen_keys = set()
    empty_streak = 0

    for page_index in range(MAX_PAGES_PER_SCRAPE):
        tokens = ["0"] if page_index == 0 else [f"0,{page_index}", str(page_index)]
        page_rows: List[Dict] = []

        for token in tokens:
            fragment = fetch_ajax_page(source_url, view_params, token)
            extracted = extract_comments_from_html(fragment)
            if extracted:
                page_rows = extracted
                break

        if not page_rows:
            empty_streak += 1
            if page_index > 0 and empty_streak >= 2:
                break
            continue

        empty_streak = 0
        new_in_page = 0
        for row in page_rows:
            key = make_comment_key(row.get("author", ""), row.get("text", ""))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            collected.append(row)
            new_in_page += 1

        if page_index > 0 and new_in_page == 0:
            break

    return collected


def normalize_rows(rows: List[Dict]) -> List[Dict]:
    normalized: List[Dict] = []

    for row in rows:
        text = fix_mojibake(row.get("text", ""))
        if is_junk_or_boilerplate(text):
            continue

        author = fix_mojibake(row.get("author", "Unknown")) or "Unknown"
        if is_placeholder_author(author):
            author = "Unknown"

        timestamp = fix_mojibake(row.get("timestamp", ""))

        analysis = analyze_comment(text)

        normalized.append(
            {
                "author": author,
                "timestamp": timestamp,
                "text": text,
                "lang": normalize_language_name(analysis.get("lang", "Unknown")) or "Unknown",
                "sentiment": normalize_sentiment(analysis.get("sentiment", "unknown")),
                "sentiment_score": safe_float(analysis.get("sentiment_score", 0.0), 0.0),
                "summary": short_summary(analysis.get("summary", text)),
            }
        )

    return normalized


def save_rows_to_csv(rows: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "author": row.get("author", "Unknown"),
                    "timestamp": row.get("timestamp", ""),
                    "text": row.get("text", ""),
                    "lang": row.get("lang", "Unknown"),
                    "sentiment": normalize_sentiment(row.get("sentiment", "unknown")),
                    "sentiment_score": f"{safe_float(row.get('sentiment_score', 0.0), 0.0):.4f}",
                    "summary": row.get("summary", ""),
                }
            )


def load_rows_from_csv(path: Path) -> List[Dict]:
    if not path.exists():
        return []

    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            with path.open("r", newline="", encoding=encoding) as file:
                reader = csv.DictReader(file)
                rows: List[Dict] = []
                for row in reader:
                    rows.append(
                        {
                            "author": row.get("author", "Unknown"),
                            "timestamp": row.get("timestamp", ""),
                            "text": row.get("text", ""),
                            "lang": row.get("lang", "Unknown"),
                            "sentiment": row.get("sentiment", "unknown"),
                            "sentiment_score": row.get("sentiment_score", 0.0),
                            "summary": row.get("summary", row.get("text", "")),
                        }
                    )
                return rows
        except UnicodeDecodeError:
            continue
        except Exception:
            return []

    return []


def merge_with_existing(new_rows: List[Dict], existing_rows: List[Dict]) -> List[Dict]:
    merged: List[Dict] = []
    seen = set()

    for row in new_rows + existing_rows:
        key = make_comment_key(row.get("author", ""), row.get("text", ""))
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)

    return merged


def scrape_and_analyze_source(source_id: str) -> List[Dict]:
    config = SITE_CONFIG[source_id]
    scraped_rows = scrape_comments_paginated(config["url"])
    if not scraped_rows:
        raise RuntimeError("No comments extracted from source.")

    analyzed_rows = normalize_rows(scraped_rows)
    if not analyzed_rows:
        raise RuntimeError("No valid comments after analysis.")

    existing_rows = normalize_rows(load_rows_from_csv(csv_path(source_id)))
    merged_rows = merge_with_existing(analyzed_rows, existing_rows)

    save_rows_to_csv(merged_rows, csv_path(source_id))
    save_rows_to_csv(merged_rows, dashboard_csv_path(source_id))

    raw_like_rows = [
        {
            "author": row.get("author", "Unknown"),
            "timestamp": row.get("timestamp", ""),
            "text": row.get("text", ""),
            "lang": row.get("lang", "Unknown"),
            "sentiment": row.get("sentiment", "unknown"),
            "sentiment_score": row.get("sentiment_score", 0.0),
            "summary": row.get("summary", row.get("text", "")),
        }
        for row in merged_rows
    ]

    save_rows_to_csv(raw_like_rows, raw_csv_path(source_id))
    save_rows_to_csv(raw_like_rows, dashboard_raw_csv_path(source_id))

    return merged_rows


def refresh_site_state(source_id: str) -> None:
    with _state_lock:
        state = _site_states[source_id]
        if state["in_progress"]:
            return
        state["in_progress"] = True
        state["last_error"] = None

    try:
        merged_rows = scrape_and_analyze_source(source_id)
        with _state_lock:
            _site_states[source_id]["comments"] = merged_rows
            _site_states[source_id]["last_updated"] = datetime.now(timezone.utc).isoformat()
            _site_states[source_id]["last_error"] = None
    except Exception as exc:
        with _state_lock:
            _site_states[source_id]["last_error"] = str(exc)
    finally:
        with _state_lock:
            _site_states[source_id]["in_progress"] = False


def ensure_seed_data() -> None:
    for source_id in SITE_CONFIG:
        processed = normalize_rows(load_rows_from_csv(csv_path(source_id)))
        if not processed:
            processed = normalize_rows(load_rows_from_csv(dashboard_csv_path(source_id)))
        if not processed:
            processed = normalize_rows(load_rows_from_csv(raw_csv_path(source_id)))
        if not processed:
            processed = normalize_rows(load_rows_from_csv(dashboard_raw_csv_path(source_id)))

        with _state_lock:
            _site_states[source_id]["comments"] = processed
            _site_states[source_id]["last_updated"] = (
                datetime.now(timezone.utc).isoformat() if processed else None
            )


def should_refresh(last_updated: Optional[str]) -> bool:
    if not last_updated:
        return True
    try:
        updated_at = datetime.fromisoformat(last_updated)
    except Exception:
        return True

    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    age_seconds = (datetime.now(timezone.utc) - updated_at).total_seconds()
    return age_seconds >= REFRESH_INTERVAL_SECONDS


def trigger_refresh_if_needed(source_id: str, force: bool = False) -> bool:
    with _state_lock:
        state = _site_states[source_id]
        if state["in_progress"]:
            return False
        if not force and not should_refresh(state.get("last_updated")):
            return False

        thread = threading.Thread(target=refresh_site_state, args=(source_id,), daemon=True)
        thread.start()
        return True


def state_payload(source_id: str) -> Dict:
    with _state_lock:
        state = _site_states[source_id]
        return {
            "source_id": source_id,
            "source_name": state["source_name"],
            "comments": list(state["comments"]),
            "last_updated": state["last_updated"],
            "in_progress": state["in_progress"],
            "last_error": state["last_error"],
            "gemini_enabled": _gemini_enabled,
        }


@app.route("/api/live-comments", methods=["GET"])
def get_live_comments():
    source_id = request.args.get("source", "site1")
    if source_id not in SITE_CONFIG:
        return jsonify({"error": f"Unknown source: {source_id}"}), 400

    trigger_refresh_if_needed(source_id)
    return jsonify(state_payload(source_id))


@app.route("/api/refresh-now", methods=["GET", "POST"])
def refresh_now():
    source_id = request.args.get("source", "site1")
    if source_id not in SITE_CONFIG:
        return jsonify({"error": f"Unknown source: {source_id}"}), 400

    started = trigger_refresh_if_needed(source_id, force=True)
    return jsonify({"ok": True, "started": started, "source": source_id})


@app.route("/api/sources", methods=["GET"])
def get_sources():
    return jsonify(
        {
            "sources": [
                {"id": source_id, "name": conf["name"], "url": conf["url"]}
                for source_id, conf in SITE_CONFIG.items()
            ],
            "refresh_interval_seconds": REFRESH_INTERVAL_SECONDS,
            "max_pages_per_scrape": MAX_PAGES_PER_SCRAPE,
            "gemini_enabled": _gemini_enabled,
        }
    )


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "mygov-dashboard-backend"})


if __name__ == "__main__":
    ensure_seed_data()
    for source in SITE_CONFIG:
        trigger_refresh_if_needed(source, force=True)
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


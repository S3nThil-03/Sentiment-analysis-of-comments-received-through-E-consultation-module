import os
import re
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from langdetect import detect, DetectorFactory, LangDetectException
from transformers import pipeline, AutoModelForSeq2SeqLM, AutoTokenizer
import pycountry
from tqdm import tqdm

# Selenium for dynamic content
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# --- SETUP ---
DetectorFactory.seed = 0
os.makedirs("outputs", exist_ok=True)
CACHE_DIR = "models_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# --- AI MODELS ---
SENT_MODEL_ID = "cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual"
SUMM_MODEL_ID = "csebuetnlp/mT5_multilingual_XLSum"

# --- HELPER FUNCTIONS ---
def get_language_full_name(code: str) -> str:
    """Converts a 2-letter language code to its full name."""
    if not code or len(code) > 3:
        return "Unknown"
    try:
        lang = pycountry.languages.get(alpha_2=code)
        return lang.name if lang else code.upper()
    except Exception:
        return code.upper()

def is_junk_or_boilerplate(text: str) -> bool:
    """Filters out very short or irrelevant text."""
    if not text or len(text.split()) < 3:
        return True
    if re.fullmatch(r"Like\s*\(\d+\)\s*Dislike\s*\(\d+\).*", text, re.IGNORECASE):
        return True
    return False

# --- NLP PIPELINE SETUP ---
print("Loading ADVANCED multilingual sentiment model...")
sentiment_pipeline = pipeline("sentiment-analysis", model=SENT_MODEL_ID, cache_dir=CACHE_DIR)

print("Loading STATE-OF-THE-ART multilingual summarization model...")
try:
    summarization_tokenizer = AutoTokenizer.from_pretrained(SUMM_MODEL_ID, cache_dir=CACHE_DIR)
    summarization_model = AutoModelForSeq2SeqLM.from_pretrained(SUMM_MODEL_ID, cache_dir=CACHE_DIR)
    summarizer = pipeline("summarization", model=summarization_model, tokenizer=summarization_tokenizer)
    print("Summarization model loaded successfully.")
except Exception as e:
    print(f"Failed to load summarization model. Summarization will be skipped. Error: {e}")
    summarizer = None

# --- PROCESSING FUNCTION ---
def process_and_predict(comments):
    """Processes comments, performs sentiment analysis, summarization, and language detection."""
    rows = []
    for c in tqdm(comments, desc="Running state-of-the-art analysis"):
        text = c.get("text", "").strip()
        if not text: continue

        sentiment, score, lang_code = "neutral", 0.5, "unknown"

        if is_junk_or_boilerplate(text):
            lang_code = "N/A"
        else:
            try:
                lang_code = detect(text)
                prediction = sentiment_pipeline(text[:512])[0]
                sentiment = prediction['label'].lower()
                score = prediction['score']
            except LangDetectException:
                lang_code = "unknown"
            except Exception:
                sentiment, score = "neutral", 0.5

        lang_full_name = get_language_full_name(lang_code)

        summary = ""
        if summarizer and len(text.split()) > 25:
            try:
                summary_input = "summarize: " + text
                s = summarizer(summary_input, max_length=150, min_length=20, do_sample=False)
                summary = s[0].get('summary_text', text)
            except Exception:
                summary = text
        else:
            summary = text

        rows.append({
            "author": c.get("author", "Unknown"),
            "timestamp": "",
            "text": text,
            "lang": lang_full_name,
            "sentiment": sentiment,
            "sentiment_score": score,
            "summary": summary
        })
    return rows

# --- SCRAPING AND MAIN EXECUTION ---
def scrape_comments_selenium(url: str):
    """Scrapes comments from a MyGov URL using Selenium to handle JavaScript-rendered content."""
    print("Initializing Selenium WebDriver...")
    
    # Setup Chrome options
    chrome_options = ChromeOptions()
    chrome_options.add_argument('--headless')  # Run in headless mode (no GUI)
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    try:
        # Initialize driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"Navigating to URL: {url}")
        driver.get(url)
        
        # Wait for comments to load - try multiple selectors
        print("Waiting for comments to load...")
        try:
            # Wait for the views-row elements to be populated
            WebDriverWait(driver, 20).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, "div.views-row div.comment_body")) > 0
            )
        except:
            print("Warning: Comments took longer to load or may not be available.")
        
        # Additional wait to ensure all comments are rendered
        time.sleep(3)
        
        # Scroll to load more comments if lazy loading exists
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(5):  # Try scrolling 5 times
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        # Get the page source and parse with BeautifulSoup
        page_source = driver.page_source
        driver.quit()
        
    except Exception as e:
        print(f"Error with Selenium: {e}")
        try:
            driver.quit()
        except:
            pass
        return []
    
    # Parse the rendered HTML
    soup = BeautifulSoup(page_source, "html.parser")
    results = []
    processed_texts = set()
    
    # Find all comment blocks
    comment_blocks = soup.select("div.views-row")
    
    if not comment_blocks:
        print("Warning: Could not find any comment blocks.")
        return []
    
    print(f"Found {len(comment_blocks)} comment blocks. Processing...")
    # Debug: dump first few blocks to a file for inspection
    try:
        os.makedirs('outputs', exist_ok=True)
        with open(os.path.join('outputs', 'debug_comment_blocks.html'), 'w', encoding='utf-8') as dbg:
            dbg.write('<html><body>')
            for i, blk in enumerate(comment_blocks[:10]):
                dbg.write(f"<h2>Block {i}</h2>\n")
                dbg.write(blk.prettify())
                dbg.write('\n<hr/>\n')
            dbg.write('</body></html>')
    except Exception as e:
        print(f"Warning: failed to write debug file: {e}")
    
    for block in comment_blocks:
        try:
            # Extract author name
            # Try multiple selectors for author
            author = "Unknown"
            author_elem = block.select_one(
                "div.comment_user, div.comment-user, span.author, a.username, div.post-author, div.user, .comment-author"
            )
            if author_elem:
                author_text = author_elem.get_text(separator=" ", strip=True)
                author = author_text.split('\n')[0].strip() if author_text else "Unknown"
            
            # Extract comment text: try common selectors then fallback to block text
            text_selectors = (
                "div.comment_body, div.comment-body, div.field--name-field-comments, div.field-name-body, div.views-field-body, div.field-item, p, article"
            )
            text_elem = block.select_one(text_selectors)
            if text_elem:
                text_content = text_elem.get_text(separator=" ", strip=True)
            else:
                # Fallback: use the block's visible text but remove author text if present
                raw = block.get_text(separator=" ", strip=True)
                if author and author in raw:
                    text_content = raw.replace(author, "").strip()
                else:
                    text_content = raw
            
            # Clean up and validate
            if text_content:
                # Remove repeated whitespace and very long metadata lines
                text_content = re.sub(r"\s+", " ", text_content).strip()
            if text_content and text_content not in processed_texts and not is_junk_or_boilerplate(text_content):
                results.append({"author": author, "text": text_content})
                processed_texts.add(text_content)
        
        except Exception as e:
            print(f"Error processing comment block: {e}")
            continue
    
    print(f"Successfully extracted {len(results)} valid comments.")
    return results

def main(url=None):
    """Main function to orchestrate the scraping and analysis."""
    if url is None:
        raise ValueError("A URL must be provided.")
    
    print("-" * 50)
    print(f"Starting scrape for URL: {url}")
    
    # Use Selenium for dynamic content
    comments = scrape_comments_selenium(url)
    
    if not comments:
        print("No valid comments found to process.")
        return

    rows = process_and_predict(comments)
    if not rows:
        print("Processing did not yield any valid rows.")
        return
        
    df = pd.DataFrame(rows)
    
    # Temporarily save the processed file
    output_path = os.path.join("outputs", "comments_processed.csv")
    df.to_csv(output_path, index=False)
    
    print(f"Scraping and analysis complete. {len(df)} comments saved to {output_path}")
    print("-" * 50)

if __name__ == '__main__':
    print("This script is designed to be called from run_scraper.py")

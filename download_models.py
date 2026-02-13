import os
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoModelForSeq2SeqLM

# --- SETTINGS ---
# This is the folder where your models will be saved permanently.
CACHE_DIR = "models_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# The IDs of the models we need.
SENT_MODEL_ID = "cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual"
SUMM_MODEL_ID = "csebuetnlp/mT5_multilingual_XLSum"

# --- DOWNLOAD PROCESS ---
print("--- Starting Model Download Process ---")
print("This is a one-time setup and may take a while depending on your internet connection.")

try:
    print(f"📥 Downloading sentiment model: {SENT_MODEL_ID}...")
    # Download all necessary files for the sentiment model.
    AutoTokenizer.from_pretrained(SENT_MODEL_ID, cache_dir=CACHE_DIR)
    AutoModelForSequenceClassification.from_pretrained(SENT_MODEL_ID, cache_dir=CACHE_DIR)
    print("✅ Sentiment model downloaded successfully.")

    print(f"📥 Downloading summarization model: {SUMM_MODEL_ID}...")
    # Download all necessary files for the summarization model.
    AutoTokenizer.from_pretrained(SUMM_MODEL_ID, cache_dir=CACHE_DIR)
    AutoModelForSeq2SeqLM.from_pretrained(SUMM_MODEL_ID, cache_dir=CACHE_DIR)
    print("✅ Summarization model downloaded successfully.")

except Exception as e:
    print(f"\n❌ An error occurred during download: {e}")
    print("Please check your internet connection and try running this script again.")

else:
    print(f"\n🎉 All models have been downloaded and saved to the '{CACHE_DIR}' folder.")
    print("You can now run 'python run_scraper.py' to perform the analysis.")

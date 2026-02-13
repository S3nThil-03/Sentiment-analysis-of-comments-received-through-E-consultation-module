import requests
from bs4 import BeautifulSoup
import json

url = "https://www.mygov.in/group-issue/inviting-ideas-mann-ki-baat-prime-minister-narendra-modi-28th-september-2025/"

print("Fetching URL...")
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
print(f"Status Code: {r.status_code}")
print(f"Content Length: {len(r.text)} chars")

soup = BeautifulSoup(r.text, "html.parser")

# Check for various possible comment selectors
print("\n=== Looking for comment containers ===")
print(f"div.views-row: {len(soup.select('div.views-row'))}")
print(f"div.comment: {len(soup.select('div.comment'))}")
print(f"div.views-col: {len(soup.select('div.views-col'))}")
print(f"div[class*='comment']: {len(soup.select('div[class*=\"comment\"]'))}")
print(f"div[data-comment-id]: {len(soup.select('div[data-comment-id]'))}")
print(f"article: {len(soup.select('article'))}")
print(f"div.node: {len(soup.select('div.node'))}")
print(f"div.field: {len(soup.select('div.field'))}")

# Try to find divs with specific class patterns
all_divs_with_class = soup.find_all('div', class_=True)
print(f"\nTotal divs with class attribute: {len(all_divs_with_class)}")

# Get unique class names that might be relevant
class_names = {}
for div in all_divs_with_class[:500]:
    classes = div.get('class', [])
    for cls in classes:
        if 'view' in cls.lower() or 'comment' in cls.lower() or 'field' in cls.lower() or 'content' in cls.lower():
            class_names[cls] = class_names.get(cls, 0) + 1

print("\n=== Relevant class names found ===")
for cls, count in sorted(class_names.items(), key=lambda x: x[1], reverse=True)[:20]:
    print(f"{cls}: {count}")

# Print sample HTML structure
print("\n=== Sample HTML (first 3000 chars) ===")
print(r.text[:3000])

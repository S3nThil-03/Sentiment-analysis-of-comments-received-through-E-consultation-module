import requests
from bs4 import BeautifulSoup
import json

url = "https://www.mygov.in/group-issue/inviting-ideas-mann-ki-baat-prime-minister-narendra-modi-28th-september-2025/"

print("Fetching URL...")
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
soup = BeautifulSoup(r.text, "html.parser")

# Look for JavaScript that might contain the data
print("\n=== Looking for JSON data in HTML ===")
scripts = soup.find_all('script', type='application/json')
print(f"Found {len(scripts)} JSON scripts")

# Also look for regular scripts
all_scripts = soup.find_all('script')
print(f"Found {len(all_scripts)} total scripts\n")

# Look for data in script tags
for i, script in enumerate(all_scripts[:10]):
    content = script.string
    if content:
        if 'comment' in content.lower() or 'data' in content.lower():
            print(f"Script {i}: {content[:500]}")
            print("---")

# Look for API endpoints or data attributes
print("\n=== Looking for data in elements ===")
divs_with_data = soup.find_all('div', attrs={'data-comment-id': True})
print(f"divs with data-comment-id: {len(divs_with_data)}")

divs_with_data = soup.find_all(attrs={'ng-repeat': True})
print(f"Elements with ng-repeat: {len(divs_with_data)}")

# Check for Vue.js or React attributes
divs_with_vue = soup.find_all(attrs={'v-for': True})
print(f"Elements with v-for: {len(divs_with_vue)}")

divs_with_react = soup.find_all(attrs={'data-react-root': True})
print(f"Elements with data-react-root: {len(divs_with_react)}")

# Print full body to see structure better
print("\n=== Full views-row content ===")
comment_blocks = soup.select("div.views-row")
for i, block in enumerate(comment_blocks[:2]):
    print(f"\nBlock {i}:")
    print(block.prettify()[:1000])

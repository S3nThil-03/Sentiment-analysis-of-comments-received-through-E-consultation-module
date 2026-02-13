from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time

URL = "https://www.mygov.in/group-issue/inviting-ideas-mann-ki-baat-prime-minister-narendra-modi-28th-september-2025/"

opts = Options()
opts.add_argument('--headless')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')
opts.add_argument('user-agent=Mozilla/5.0')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=opts)
try:
    driver.get(URL)
    time.sleep(5)
    # scroll
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    page = driver.page_source
    with open('outputs/debug_site1.html','w',encoding='utf-8') as f:
        f.write(page)
    elems = driver.find_elements(By.CSS_SELECTOR, 'div.views-row')
    print('Found views-row count:', len(elems))
    for i, e in enumerate(elems[:5]):
        text = e.get_attribute('innerHTML')[:800]
        print(f'--- block {i} innerHTML (first 800 chars) ---')
        print(text)
finally:
    driver.quit()

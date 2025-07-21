from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    options = Options()
    options.binary_location = '/usr/bin/google-chrome'
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service('/usr/bin/chromedriver', port=9515)
    driver = webdriver.Chrome(service=service, options=options)
    driver.get('https://www.google.com')
    print(driver.title)
    driver.quit()
except Exception as e:
    logging.error(f"Error occurred: {str(e)}")

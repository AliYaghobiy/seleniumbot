#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import logging
import random
import platform
import subprocess
import re
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from urllib.parse import urljoin
import sys
import os

class ProductScraper:
    """
    ربات اسکرپینگ محصولات با استفاده از سلنیوم - نسخه بهینه‌شده
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        راه‌اندازی ربات با بارگذاری کانفیگ
        """
        self.config = self.load_config(config_path)
        self.driver = None
        self.scraped_products = []
        self.tab_handles = []  # اضافه شده برای نگهداری handle های تب‌ها 
        self.setup_logging()
        
    def setup_logging(self):
        """
        تنظیم سیستم لاگ
        """
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('scraper.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self, config_path: str) -> Dict:
        """
        بارگذاری فایل کانفیگ
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"✅ فایل کانفیگ با موفقیت بارگذاری شد: {config_path}")
            return config
        except FileNotFoundError:
            print(f"❌ فایل کانفیگ یافت نشد: {config_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ خطا در فرمت JSON فایل کانفیگ: {e}")
            sys.exit(1)
            
    def detect_chrome_binary(self):
        """
        تشخیص مسیر Chrome در سیستم‌های مختلف
        """
        chrome_paths = [
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable', 
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            '/snap/bin/chromium',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
            'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
        ]
        
        for path in chrome_paths:
            if os.path.exists(path):
                self.logger.info(f"✅ Chrome یافت شد در: {path}")
                return path
                
        try:
            result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip()
                self.logger.info(f"✅ Chrome یافت شد با which: {path}")
                return path
        except:
            pass
            
        try:
            result = subprocess.run(['which', 'chromium-browser'], capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip()
                self.logger.info(f"✅ Chromium یافت شد با which: {path}")
                return path
        except:
            pass
            
        return None

    def install_chrome_ubuntu(self):
        """
        راهنمای نصب Chrome در Ubuntu/Debian
        """
        print("📋 برای نصب Google Chrome در Ubuntu/Debian:")
        print("wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -")
        print("echo 'deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main' | sudo tee /etc/apt/sources.list.d/google-chrome.list")
        print("sudo apt-get update")
        print("sudo apt-get install google-chrome-stable")
        print("\n📋 یا برای نصب Chromium:")
        print("sudo apt-get install chromium-browser")

    def human_like_delay(self, min_seconds=0.5, max_seconds=1.5):
        """
        تاخیر تصادفی بهینه‌شده برای سرعت بیشتر
        """
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
        
    def human_like_scroll(self, pause_time=None):
        """
        اسکرول طبیعی مانند انسان برای اطمینان از لود کامل محصولات
        """
        if pause_time is None:
            pause_time = random.uniform(0.5, 1.5)
            
        current_scroll = self.driver.execute_script("return window.pageYOffset;")
        total_height = self.driver.execute_script("return document.body.scrollHeight;")
        
        scroll_steps = random.randint(3, 6)
        step_height = (total_height - current_scroll) / scroll_steps
        
        for i in range(scroll_steps):
            scroll_to = current_scroll + (step_height * (i + 1))
            self.driver.execute_script(f"window.scrollTo(0, {scroll_to});")
            WebDriverWait(self.driver, 5).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(random.uniform(0.3, 0.8))
            
        time.sleep(pause_time)
        
    def simulate_quick_mouse_movement(self, element):
        """
        شبیه‌سازی سریع حرکت موس
        """
        try:
            actions = ActionChains(self.driver)
            actions.move_to_element(element)
            actions.pause(random.uniform(0.1, 0.2))
            actions.perform()
        except Exception as e:
            self.logger.warning(f"⚠️ خطا در شبیه‌سازی حرکت موس: {e}")
            
    def load_random_user_agents(self, file_path: str = "random.txt") -> List[str]:
        """
        بارگذاری User-Agent های تصادفی از فایل
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                user_agents = [line.strip() for line in f.readlines() if line.strip()]
            if user_agents:
                self.logger.info(f"✅ {len(user_agents)} User-Agent از فایل {file_path} بارگذاری شد")
                return user_agents
            else:
                self.logger.warning(f"⚠️ فایل {file_path} خالی است")
                return []
        except FileNotFoundError:
            self.logger.warning(f"⚠️ فایل {file_path} یافت نشد")
            return []
        except Exception as e:
            self.logger.error(f"❌ خطا در بارگذاری User-Agent ها: {e}")
            return []

    def get_random_user_agent(self) -> str:
        """
        انتخاب تصادفی User-Agent
        """
        user_agents = self.load_random_user_agents()
        if user_agents:
            selected_ua = random.choice(user_agents)
            self.logger.info(f"🎲 User-Agent تصادفی انتخاب شد: {selected_ua[:50]}...")
            return selected_ua
        default_ua = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
        self.logger.info(f"🔄 استفاده از User-Agent پیش‌فرض")
        return default_ua

    def setup_driver(self):
        """
        راه‌اندازی مرورگر با تنظیمات بهینه
        """
        try:
            chrome_options = Options()
            system_name = platform.system().lower()
            self.logger.info(f"🖥️ سیستم‌عامل شناسایی شده: {system_name}")
            
            chrome_binary = self.detect_chrome_binary()
            if chrome_binary:
                chrome_options.binary_location = chrome_binary
            else:
                self.logger.error("❌ Google Chrome یا Chromium یافت نشد!")
                self.install_chrome_ubuntu()
                sys.exit(1)
            
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-images')
            chrome_options.add_argument('--disable-css-background-images')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--max_old_space_size=4096')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-renderer-backgrounding')

            
            random_user_agent = self.get_random_user_agent()
            chrome_options.add_argument(f'--user-agent={random_user_agent}')
            
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            chromedriver_path = '/usr/bin/chromedriver'
            if os.path.exists(chromedriver_path):
                self.logger.info(f"✅ استفاده از chromedriver سیستم: {chromedriver_path}")
                service = Service(chromedriver_path, port=9515)
            else:
                self.logger.error("❌ chromedriver یافت نشد")
                sys.exit(1)
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.implicitly_wait(5)
            self.driver.maximize_window()
            self.logger.info("✅ مرورگر کروم با موفقیت راه‌اندازی شد")
            
        except Exception as e:
            self.logger.error(f"❌ خطا در راه‌اندازی مرورگر: {e}")
            sys.exit(1)
   
    def scroll_page(self, scroll_count: int):
        """
        اسکرول طبیعی صفحه برای بارگذاری محصولات بیشتر
        """
        self.logger.info(f"🔄 شروع اسکرول طبیعی صفحه - تعداد: {scroll_count}")
        
        for i in range(scroll_count):
            self.logger.info(f"📜 اسکرول {i+1} از {scroll_count}")
            self.human_like_scroll()
            self.human_like_delay(1.5, 3.5)
            if random.random() < 0.3:
                self.driver.execute_script("window.scrollBy(0, -100);")
                time.sleep(random.uniform(0.5, 1.0))
        
        self.driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
        self.human_like_delay(2, 3)
        
    def extract_product_links(self) -> List[str]:
        """
        استخراج لینک‌های محصولات با انتظار لود کامل
        """
        self.logger.info("🔍 شروع استخراج لینک‌های محصولات...")
        
        try:
            self.driver.get(self.config['main_page_url'])
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            self.human_like_delay(2, 3)
            
            scroll_count = self.config.get('scroll_count', 0)
            if scroll_count > 0:
                self.scroll_page(scroll_count)
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, self.config['selectors']['product_links']))
            )
            
            product_selector = self.config['selectors']['product_links']
            product_elements = self.driver.find_elements(By.CSS_SELECTOR, product_selector)
            
            product_links = []
            for element in product_elements:
                try:
                    href = element.get_attribute('href')
                    if href:
                        full_url = urljoin(self.config['main_page_url'], href)
                        if full_url not in product_links:
                            product_links.append(full_url)
                except Exception:
                    continue
                
            self.logger.info(f"✅ تعداد {len(product_links)} لینک محصول استخراج شد")
            return product_links
            
        except Exception as e:
            self.logger.error(f"❌ خطا در استخراج لینک‌های محصولات: {e}")
            return []

    def detect_brand_from_category(self, category_text: str) -> Optional[str]:
        """
        تشخیص برند از متن دسته‌بندی
        """
        pattern = r'(.+?)\s*\((.+?)\)'
        match = re.match(pattern, category_text.strip())
        if match:
            brand_persian = match.group(1).strip()
            brand_english = match.group(2).strip()
            self.logger.info(f"🏷️ برند تشخیص داده شد: {brand_persian} ({brand_english})")
            return f"{brand_persian} ({brand_english})"
        return None

    def extract_specifications(self, product_url: str) -> Dict:
        """
        استخراج مشخصات کلیدی و کلی محصول
        """
        specifications = {
            'key_specs': [],
            'general_specs': []
        }
        
        try:
            key_specs_selector = self.config['selectors']['specifications']['key_specs_section']
            general_specs_selector = self.config['selectors']['specifications']['general_specs_section']
            spec_items_selector = self.config['selectors']['specifications']['spec_items']
            spec_title_selector = self.config['selectors']['specifications']['spec_title']
            spec_value_selector = self.config['selectors']['specifications']['spec_value']
            
            try:
                spec_elements = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, spec_items_selector))
                )
                for element in spec_elements:
                    try:
                        title = element.find_element(By.CSS_SELECTOR, spec_title_selector).text.strip()
                        value = element.find_element(By.CSS_SELECTOR, spec_value_selector).text.strip()
                        if title and value:
                            if key_specs_selector in element.get_attribute('class') or 'key' in element.get_attribute('class').lower():
                                specifications['key_specs'].append({
                                    'title': title,
                                    'body': value
                                })
                            else:
                                specifications['general_specs'].append({
                                    'title': title,
                                    'body': value
                                })
                    except Exception:
                        continue
            except TimeoutException:
                self.logger.warning("⚠️ هیچ مشخصه‌ای با سلکتورهای اصلی پیدا نشد")
                self.extract_specs_alternative_method(specifications)
                
        except Exception as e:
            self.logger.warning(f"⚠️ خطا در استخراج مشخصات: {e}")
        
        return specifications

    def extract_specs_alternative_method(self, specifications: Dict):
        """
        روش جایگزین برای استخراج مشخصات
        """
        try:
            all_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'مشخصات')]")
            for element in all_elements:
                try:
                    parent = element.find_element(By.XPATH, './..')
                    spec_items = parent.find_elements(By.XPATH, './/*')
                    for item in spec_items:
                        try:
                            text = item.text.strip()
                            if text and '\n' in text:
                                lines = text.split('\n')
                                if len(lines) >= 2:
                                    title = lines[0].strip()
                                    body = lines[1].strip()
                                    if title and body and len(title) < 100 and len(body) < 200:
                                        if any(keyword in title.lower() for keyword in ['حافظه', 'باتری', 'دوربین', 'سیم']):
                                            specifications['key_specs'].append({
                                                'title': title,
                                                'body': body
                                            })
                                        else:
                                            specifications['general_specs'].append({
                                                'title': title,
                                                'body': body
                                            })
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception as e:
            self.logger.warning(f"⚠️ خطا در روش جایگزین استخراج مشخصات: {e}")
            
    def extract_product_data(self, product_url: str) -> Optional[Dict]:
        """
        استخراج بهینه‌شده اطلاعات محصول
        """
        try:
            self.logger.info(f"📊 استخراج اطلاعات محصول: {product_url}")
            self.driver.get(product_url)
            self.human_like_delay(1.5, 2.5)
            self.driver.execute_script("window.scrollTo(0, 500);")
            self.human_like_delay(0.5, 1)
            
            product_data = {
                'url': product_url,
                'title': None,
                'categories': [],
                'brand': None,
                'specifications': {
                    'key_specs': [],
                    'general_specs': []
                }
            }
            
            try:
                title_element = WebDriverWait(self.driver, 6).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.config['selectors']['product_title']))
                )
                product_data['title'] = title_element.text.strip()
                self.logger.info(f"📝 عنوان محصول: {product_data['title']}")
            except TimeoutException:
                self.logger.warning(f"⚠️ عنوان محصول یافت نشد: {product_url}")
                
            categories_selectors = self.config['selectors']['categories']
            categories_found = []
            for i, selector in enumerate(categories_selectors):
                try:
                    category_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    category_text = category_element.text.strip()
                    if category_text:
                        categories_found.append({
                            'level': i + 1,
                            'name': category_text
                        })
                        self.logger.info(f"🏷️ دسته‌بندی {i+1}: {category_text}")
                except NoSuchElementException:
                    break
                except Exception as e:
                    self.logger.warning(f"⚠️ خطا در استخراج دسته‌بندی {i+1}: {e}")
            
            if categories_found:
                last_category = categories_found[-1]
                brand = self.detect_brand_from_category(last_category['name'])
                if brand:
                    product_data['brand'] = brand
                    product_data['categories'] = categories_found[:-1]
                    self.logger.info(f"🏷️ برند استخراج شد: {brand}")
                else:
                    product_data['categories'] = categories_found
            
            self.logger.info("🔍 شروع استخراج مشخصات...")
            specifications = self.extract_specifications(product_url)
            product_data['specifications'] = specifications
            self.logger.info(f"✅ تعداد مشخصات کلیدی: {len(specifications['key_specs'])}")
            self.logger.info(f"✅ تعداد مشخصات کلی: {len(specifications['general_specs'])}")
            
            self.human_like_delay(0.3, 0.8)
            return product_data
            
        except Exception as e:
            self.logger.error(f"❌ خطا در استخراج اطلاعات محصول {product_url}: {e}")
            return None
            
    def save_data(self):
        """
        ذخیره اطلاعات استخراج شده
        """
        output_config = self.config.get('output', {})
        filename = output_config.get('filename', 'scraped_products.json')
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.scraped_products, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"💾 اطلاعات در فایل {filename} ذخیره شد")
            
            total_products = len(self.scraped_products)
            successful_products = len([p for p in self.scraped_products if p.get('title')])
            products_with_brand = len([p for p in self.scraped_products if p.get('brand')])
            products_with_key_specs = len([p for p in self.scraped_products if p.get('specifications', {}).get('key_specs')])
            products_with_general_specs = len([p for p in self.scraped_products if p.get('specifications', {}).get('general_specs')])
            
            print(f"\n📈 آمار نهایی:")
            print(f"🔢 تعداد کل محصولات: {total_products}")
            print(f"✅ محصولات موفق: {successful_products}")
            print(f"🏷️ محصولات با برند: {products_with_brand}")
            print(f"🔧 محصولات با مشخصات کلیدی: {products_with_key_specs}")
            print(f"📋 محصولات با مشخصات کلی: {products_with_general_specs}")
            print(f"❌ محصولات ناموفق: {total_products - successful_products}")
            
        except Exception as e:
            self.logger.error(f"❌ خطا در ذخیره اطلاعات: {e}")
            
    def run(self):
        """
        اجرای اصلی ربات
        """
        try:
            print("🚀 شروع اجرای ربات اسکرپینگ بهینه‌شده...")
            self.setup_driver()
            product_links = self.extract_product_links()
            
            if not product_links:
                self.logger.error("❌ هیچ لینک محصولی یافت نشد")
                return
                
            total_products = len(product_links)
            for i, product_url in enumerate(product_links, 1):
                print(f"\n🔄 پردازش محصول {i} از {total_products}")
                product_data = self.extract_product_data(product_url)
                if product_data:
                    self.scraped_products.append(product_data)
                if i < total_products:
                    delay = random.uniform(1, 3)
                    self.logger.info(f"⏱️ انتظار {delay:.1f} ثانیه قبل از محصول بعدی...")
                    time.sleep(delay)
                    
            self.save_data()
            print("\n🎉 ربات با موفقیت کار خود را تمام کرد!")
            
        except KeyboardInterrupt:
            self.logger.info("⏹️ ربات توسط کاربر متوقف شد")
        except Exception as e:
            self.logger.error(f"❌ خطای کلی در اجرای ربات: {e}")
        finally:
            self.cleanup()
            
    def cleanup(self):
        """
        تمیز کردن منابع
        """
        if self.driver:
            self.driver.quit()
            self.logger.info("🔒 مرورگر بسته شد")

    def setup_multiple_tabs(self, num_tabs: int = 2):
        """
        راه‌اندازی چندین تب برای پردازش موازی
        """
        try:
            self.logger.info(f"🔄 راه‌اندازی {num_tabs} تب برای پردازش موازی...")
            
            # باز کردن تب‌های اضافی
            for i in range(num_tabs - 1):
                self.driver.execute_script("window.open('about:blank', '_blank');")
                self.human_like_delay(0.3, 0.5)
            
            # دریافت handle های تمام تب‌ها
            self.tab_handles = self.driver.window_handles
            self.logger.info(f"✅ {len(self.tab_handles)} تب آماده شد")
            
            return self.tab_handles
            
        except Exception as e:
            self.logger.error(f"❌ خطا در راه‌اندازی چندین تب: {e}")
            return [self.driver.current_window_handle]

    def extract_product_data_in_tab(self, product_url: str, tab_handle: str) -> Optional[Dict]:
        """
        استخراج اطلاعات محصول در تب مشخص
        """
        try:
            # تغییر به تب مشخص
            self.driver.switch_to.window(tab_handle)
            
            self.logger.info(f"📊 استخراج اطلاعات محصول در تب: {product_url}")
            self.driver.get(product_url)
            self.human_like_delay(1.5, 2.5)
            self.driver.execute_script("window.scrollTo(0, 500);")
            self.human_like_delay(0.5, 1)
            
            product_data = {
                'url': product_url,
                'title': None,
                'categories': [],
                'brand': None,
                'specifications': {
                    'key_specs': [],
                    'general_specs': []
                }
            }
            
            # استخراج عنوان محصول
            try:
                title_element = WebDriverWait(self.driver, 6).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.config['selectors']['product_title']))
                )
                product_data['title'] = title_element.text.strip()
                self.logger.info(f"📝 عنوان محصول: {product_data['title']}")
            except TimeoutException:
                self.logger.warning(f"⚠️ عنوان محصول یافت نشد: {product_url}")
                
            # استخراج دسته‌بندی‌ها
            categories_selectors = self.config['selectors']['categories']
            categories_found = []
            for i, selector in enumerate(categories_selectors):
                try:
                    category_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    category_text = category_element.text.strip()
                    if category_text:
                        categories_found.append({
                            'level': i + 1,
                            'name': category_text
                        })
                        self.logger.info(f"🏷️ دسته‌بندی {i+1}: {category_text}")
                except NoSuchElementException:
                    break
                except Exception as e:
                    self.logger.warning(f"⚠️ خطا در استخراج دسته‌بندی {i+1}: {e}")
            
            # تشخیص برند از دسته‌بندی
            if categories_found:
                last_category = categories_found[-1]
                brand = self.detect_brand_from_category(last_category['name'])
                if brand:
                    product_data['brand'] = brand
                    product_data['categories'] = categories_found[:-1]
                    self.logger.info(f"🏷️ برند استخراج شد: {brand}")
                else:
                    product_data['categories'] = categories_found
            
            # استخراج مشخصات
            self.logger.info("🔍 شروع استخراج مشخصات...")
            specifications = self.extract_specifications(product_url)
            product_data['specifications'] = specifications
            self.logger.info(f"✅ تعداد مشخصات کلیدی: {len(specifications['key_specs'])}")
            self.logger.info(f"✅ تعداد مشخصات کلی: {len(specifications['general_specs'])}")
            
            self.human_like_delay(0.3, 0.8)
            return product_data
            
        except Exception as e:
            self.logger.error(f"❌ خطا در استخراج اطلاعات محصول {product_url}: {e}")
            return None

    def process_single_product_thread(self, product_url: str, tab_handle: str, thread_id: int, results_queue: queue.Queue):
        """
        پردازش یک محصول در thread جداگانه
        """
        try:
            # تاخیر کوچک برای جلوگیری از تداخل و کاهش فشار connection pool
            time.sleep(thread_id * 0.5)
            
            # تغییر به تب مشخص
            self.driver.switch_to.window(tab_handle)
            
            self.logger.info(f"📊 Thread {thread_id}: شروع استخراج {product_url}")
            product_data = self.extract_product_data_in_tab(product_url, tab_handle)
            
            # قرار دادن نتیجه در صف
            results_queue.put({
                'thread_id': thread_id,
                'product_data': product_data,
                'success': product_data is not None
            })
            
            self.logger.info(f"✅ Thread {thread_id}: تکمیل شد")
            
        except Exception as e:
            self.logger.error(f"❌ Thread {thread_id} خطا: {e}")
            results_queue.put({
                'thread_id': thread_id,
                'product_data': None,
                'success': False
            })

    def process_products_parallel(self, product_links: List[str], num_tabs: int = 2):
        """
        پردازش واقعاً موازی محصولات با استفاده از threading
        """
        try:
            # راه‌اندازی تب‌های متعدد
            tab_handles = self.setup_multiple_tabs(num_tabs)
            total_products = len(product_links)
            processed_count = 0
            
            self.logger.info(f"🚀 شروع پردازش همزمان {total_products} محصول با {len(tab_handles)} تب")
            
            # پردازش محصولات به صورت batch های ۳ تایی همزمان
            for batch_start in range(0, total_products, num_tabs):
                batch_end = min(batch_start + num_tabs, total_products)
                current_batch = product_links[batch_start:batch_end]
                
                print(f"\n📦 شروع پردازش همزمان batch {batch_start//num_tabs + 1}: محصولات {batch_start + 1} تا {batch_end}")
                
                # ایجاد صف برای نتایج
                results_queue = queue.Queue()
                threads = []
                
                # شروع thread ها برای پردازش همزمان
                for i, product_url in enumerate(current_batch):
                    if i < len(tab_handles):
                        tab_handle = tab_handles[i]
                        processed_count += 1
                        
                        print(f"🔄 شروع همزمان محصول {processed_count} از {total_products} در تب {i+1}")
                        
                        # ایجاد و شروع thread
                        thread = threading.Thread(
                            target=self.process_single_product_thread,
                            args=(product_url, tab_handle, i+1, results_queue)
                        )
                        thread.daemon = True
                        thread.start()
                        threads.append(thread)
                
                # انتظار برای تکمیل همه thread ها
                for thread in threads:
                    thread.join()
                
                # جمع‌آوری نتایج از صف
                batch_results = []
                while not results_queue.empty():
                    result = results_queue.get()
                    if result['success'] and result['product_data']:
                        batch_results.append(result['product_data'])
                        self.scraped_products.append(result['product_data'])
                        self.logger.info(f"✅ Thread {result['thread_id']}: داده محصول ذخیره شد")
                
                print(f"🎉 batch تکمیل شد - {len(batch_results)} محصول موفق از {len(current_batch)}")
                
                # تاخیر بین batch ها برای جلوگیری از بلاک شدن
                if batch_end < total_products:
                    batch_delay = random.uniform(3, 5)
                    self.logger.info(f"⏱️ انتظار {batch_delay:.1f} ثانیه قبل از batch بعدی...")
                    time.sleep(batch_delay)
            
            # بازگشت به تب اصلی
            self.driver.switch_to.window(tab_handles[0])
            self.logger.info("✅ پردازش همزمان تمام محصولات تکمیل شد")
            
        except Exception as e:
            self.logger.error(f"❌ خطا در پردازش همزمان محصولات: {e}")

    def run_parallel(self):
        """
        اجرای اصلی ربات با پردازش موازی - نسخه بهبود یافته
        """
        try:
            print("🚀 شروع اجرای ربات اسکرپینگ موازی...")
            self.setup_driver()
            product_links = self.extract_product_links()
            
            if not product_links:
                self.logger.error("❌ هیچ لینک محصولی یافت نشد")
                return
                
            # نمایش تعداد کل محصولات
            total_products_count = len(product_links)
            print(f"\n📊 تعداد کل محصولات یافت شده: {total_products_count}")
            print(f"🎯 شروع فرآیند استخراج اطلاعات...")
            print("=" * 60)
            
            # راه‌اندازی تب‌های متعدد
            num_tabs = 2
            tab_handles = self.setup_multiple_tabs(num_tabs)
            processed_count = 0
            
            self.logger.info(f"🚀 شروع پردازش همزمان {total_products_count} محصول با {len(tab_handles)} تب")
            
            # پردازش محصولات به صورت batch های موازی
            for batch_start in range(0, total_products_count, num_tabs):
                batch_end = min(batch_start + num_tabs, total_products_count)
                current_batch = product_links[batch_start:batch_end]
                
                batch_number = batch_start // num_tabs + 1
                total_batches = (total_products_count + num_tabs - 1) // num_tabs
                
                print(f"\n📦 Batch {batch_number} از {total_batches}")
                print(f"🔄 پردازش همزمان محصولات {batch_start + 1} تا {batch_end} از {total_products_count}")
                
                # ایجاد صف برای نتایج
                results_queue = queue.Queue()
                threads = []
                
                # شروع thread ها برای پردازش همزمان
                for i, product_url in enumerate(current_batch):
                    if i < len(tab_handles):
                        tab_handle = tab_handles[i]
                        current_product_number = batch_start + i + 1
                        
                        print(f"   🔄 تب {i+1}: شروع استخراج محصول {current_product_number} از {total_products_count}")
                        
                            # ایجاد و شروع thread
                        thread = threading.Thread(
                                target=self.process_single_product_thread,
                                args=(product_url, tab_handle, current_product_number, results_queue)
                        )
                        thread.daemon = True
                        thread.start()
                        threads.append(thread)
                
                # انتظار برای تکمیل همه thread ها
                for thread in threads:
                    thread.join()
                
                # جمع‌آوری نتایج از صف
                batch_results = []
                successful_in_batch = 0
                
                while not results_queue.empty():
                    result = results_queue.get()
                    if result['success'] and result['product_data']:
                        batch_results.append(result['product_data'])
                        self.scraped_products.append(result['product_data'])
                        successful_in_batch += 1
                        processed_count += 1
                        print(f"   ✅ محصول {result['thread_id']} : استخراج موفق ({processed_count} از {total_products_count})")
                    else:
                        processed_count += 1
                        print(f"   ❌ محصول {result['thread_id']} : استخراج ناموفق ({processed_count} از {total_products_count})")
                
                # نمایش آمار batch
                failed_in_batch = len(current_batch) - successful_in_batch
                completion_percentage = (processed_count / total_products_count) * 100
                
                print(f"🎉 Batch {batch_number} تکمیل شد:")
                print(f"   ✅ موفق: {successful_in_batch}")
                print(f"   ❌ ناموفق: {failed_in_batch}")
                print(f"   📈 پیشرفت کلی: {completion_percentage:.1f}% ({processed_count}/{total_products_count})")
                
                # تاخیر بین batch ها
                if batch_end < total_products_count:
                    batch_delay = random.uniform(3, 5)
                    remaining_products = total_products_count - processed_count
                    print(f"⏱️ انتظار {batch_delay:.1f} ثانیه قبل از batch بعدی ({remaining_products} محصول باقی‌مانده)...")
                    time.sleep(batch_delay)
            
            # نمایش آمار نهایی
            successful_total = len([p for p in self.scraped_products if p.get('title')])
            failed_total = total_products_count - successful_total
            
            print(f"\n🏁 فرآیند استخراج تکمیل شد!")
            print(f"📊 آمار نهایی:")
            print(f"   🔢 تعداد کل محصولات: {total_products_count}")
            print(f"   ✅ استخراج موفق: {successful_total}")
            print(f"   ❌ استخراج ناموفق: {failed_total}")
            print(f"   📈 درصد موفقیت: {(successful_total/total_products_count)*100:.1f}%")
            
            # بازگشت به تب اصلی
            self.driver.switch_to.window(tab_handles[0])
            
            # ذخیره داده‌ها
            self.save_data()
            print("\n🎉 ربات موازی با موفقیت کار خود را تمام کرد!")
            
        except KeyboardInterrupt:
            self.logger.info("⏹️ ربات توسط کاربر متوقف شد")
            print(f"\n⏹️ ربات متوقف شد - تا این لحظه {len(self.scraped_products)} محصول استخراج شده بود")
        except Exception as e:
            self.logger.error(f"❌ خطای کلی در اجرای ربات موازی: {e}")
        finally:
            self.cleanup()


def main():
    """
    تابع اصلی برنامه
    """
    print("=" * 60)
    print("🚀 ربات اسکرپینگ محصولات بهینه‌شده")
    print("=" * 60)
    
    config_file = "config.json"
    if not os.path.exists(config_file):
        print(f"❌ فایل کانفیگ یافت نشد: {config_file}")
        print("لطفاً ابتدا فایل config.json را ایجاد کنید")
        return
        
    scraper = ProductScraper(config_file)
    scraper.run_parallel()

if __name__ == "__main__":
    main()
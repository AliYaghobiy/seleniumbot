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
from typing import List, Dict, Optional, Tuple
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
        راه‌اندازی ربات با بارگذاری کانفیگ و تنظیمات Resume
        """
        self.config = self.load_config(config_path)
        self.driver = None
        self.scraped_products = []
        self.tab_handles = []
        
        # تنظیمات Resume
        self.progress_file = "scraper_progress.json"
        self.processed_urls = set()
        self.failed_urls = set()
        
        self.setup_logging()

    def load_progress(self) -> Dict:
        """
        بارگذاری وضعیت قبلی کار
        """
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                
                self.processed_urls = set(progress_data.get('processed_urls', []))
                self.failed_urls = set(progress_data.get('failed_urls', []))
                
                # بارگذاری محصولات قبلی
                if progress_data.get('scraped_products'):
                    self.scraped_products = progress_data['scraped_products']
                
                self.logger.info(f"✅ وضعیت قبلی بارگذاری شد - پردازش شده: {len(self.processed_urls)}, ناموفق: {len(self.failed_urls)}")
                return progress_data
            else:
                self.logger.info("🆕 شروع جدید - فایل progress یافت نشد")
                return {}
                
        except Exception as e:
            self.logger.error(f"❌ خطا در بارگذاری progress: {e}")
            return {}
    
    def save_progress(self, all_product_links: List[str] = None):
        """
        ذخیره وضعیت فعلی کار
        """
        try:
            progress_data = {
                'processed_urls': list(self.processed_urls),
                'failed_urls': list(self.failed_urls),
                'scraped_products': self.scraped_products,
                'total_found_products': len(all_product_links) if all_product_links else 0,
                'timestamp': time.time()
            }
            
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"💾 وضعیت ذخیره شد - پردازش شده: {len(self.processed_urls)}")
            
        except Exception as e:
            self.logger.error(f"❌ خطا در ذخیره progress: {e}")
    
    def get_remaining_urls(self, all_product_links: List[str]) -> List[str]:
        """
        دریافت URLهای باقی‌مانده برای پردازش
        """
        remaining_urls = []
        for url in all_product_links:
            if url not in self.processed_urls and url not in self.failed_urls:
                remaining_urls.append(url)
        
        self.logger.info(f"📋 تعداد محصولات باقی‌مانده: {len(remaining_urls)} از {len(all_product_links)}")
        return remaining_urls
    
    def extract_product_data_with_progress(self, product_url: str) -> Optional[Dict]:
        """
        استخراج اطلاعات محصول با ذخیره خودکار progress
        """
        try:
            product_data = self.extract_product_data(product_url)
            
            if product_data and product_data.get('title'):
                self.processed_urls.add(product_url)
                self.logger.info(f"✅ محصول موفق: {product_url}")
                return product_data
            else:
                self.failed_urls.add(product_url)
                self.logger.warning(f"❌ محصول ناموفق: {product_url}")
                return None
                
        except Exception as e:
            self.failed_urls.add(product_url)
            self.logger.error(f"❌ خطا در استخراج {product_url}: {e}")
            return None
        finally:
            # ذخیره progress بعد از هر محصول
            self.save_progress()
    
    def cleanup_with_progress_save(self, all_product_links: List[str] = None):
        """
        تمیز کردن منابع با ذخیره نهایی progress
        """
        try:
            # ذخیره نهایی progress
            self.save_progress(all_product_links)
            
            # ذخیره نهایی محصولات
            self.save_data()
            
        except Exception as e:
            self.logger.error(f"❌ خطا در cleanup: {e}")
        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("🔒 مرورگر بسته شد")
    
    def show_resume_status(self, all_product_links: List[str]):
        """
        نمایش وضعیت Resume
        """
        total_products = len(all_product_links)
        processed_count = len(self.processed_urls)
        failed_count = len(self.failed_urls)
        remaining_count = total_products - processed_count - failed_count
        
        if processed_count > 0 or failed_count > 0:
            print(f"\n🔄 ادامه کار قبلی:")
            print(f"   📊 تعداد کل محصولات: {total_products}")
            print(f"   ✅ پردازش شده: {processed_count}")
            print(f"   ❌ ناموفق: {failed_count}")
            print(f"   🔄 باقی‌مانده: {remaining_count}")
            print(f"   📈 پیشرفت: {((processed_count + failed_count) / total_products) * 100:.1f}%")
        else:
            print(f"\n🆕 شروع جدید - {total_products} محصول برای پردازش")
    
    def process_single_product_thread_with_progress(self, product_url: str, tab_handle: str, thread_id: int, results_queue):
        """
        پردازش محصول در thread با progress
        """
        try:
            time.sleep(thread_id * 0.5)
            self.driver.switch_to.window(tab_handle)
            
            self.logger.info(f"📊 Thread {thread_id}: شروع استخراج {product_url}")
            product_data = self.extract_product_data_in_tab(product_url, tab_handle)
            
            # به‌روزرسانی وضعیت
            if product_data and product_data.get('title'):
                self.processed_urls.add(product_url)
                success = True
            else:
                self.failed_urls.add(product_url)
                success = False
            
            results_queue.put({
                'thread_id': thread_id,
                'product_data': product_data,
                'success': success,
                'url': product_url
            })
            
            self.logger.info(f"✅ Thread {thread_id}: تکمیل شد")
            
        except Exception as e:
            self.failed_urls.add(product_url)
            self.logger.error(f"❌ Thread {thread_id} خطا: {e}")
            results_queue.put({
                'thread_id': thread_id,
                'product_data': None,
                'success': False,
                'url': product_url
            })
    
    def run_parallel_with_resume(self):
        """
        اجرای موازی با قابلیت Resume
        """
        try:
            print("🚀 شروع اجرای ربات اسکرپینگ موازی با Resume...")
            
            # بارگذاری وضعیت قبلی
            self.load_progress()
            
            # راه‌اندازی driver
            self.setup_driver()
            
            # دریافت لینک محصولات
            all_product_links = self.extract_product_links()
            if not all_product_links:
                self.logger.error("❌ هیچ لینک محصولی یافت نشد")
                return
            
            # نمایش وضعیت Resume
            self.show_resume_status(all_product_links)
            
            # دریافت محصولات باقی‌مانده
            remaining_product_links = self.get_remaining_urls(all_product_links)
            
            if not remaining_product_links:
                print("🎉 همه محصولات قبلاً پردازش شده‌اند!")
                self.save_data()
                return
            
            # ادامه پردازش موازی
            num_tabs = 2
            tab_handles = self.setup_multiple_tabs(num_tabs)
            
            for batch_start in range(0, len(remaining_product_links), num_tabs):
                batch_end = min(batch_start + num_tabs, len(remaining_product_links))
                current_batch = remaining_product_links[batch_start:batch_end]
                
                print(f"\n📦 پردازش batch: محصولات {batch_start + 1} تا {batch_end} از {len(remaining_product_links)} باقی‌مانده")
                
                results_queue = queue.Queue()
                threads = []
                
                for i, product_url in enumerate(current_batch):
                    if i < len(tab_handles):
                        thread = threading.Thread(
                            target=self.process_single_product_thread_with_progress,
                            args=(product_url, tab_handles[i], i+1, results_queue)
                        )
                        thread.daemon = True
                        thread.start()
                        threads.append(thread)
                
                for thread in threads:
                    thread.join()
                
                # جمع‌آوری نتایج
                while not results_queue.empty():
                    result = results_queue.get()
                    if result['success'] and result['product_data']:
                        self.scraped_products.append(result['product_data'])
                
                # ذخیره progress بعد از هر batch
                self.save_progress(all_product_links)
                
                if batch_end < len(remaining_product_links):
                    time.sleep(random.uniform(3, 5))
            
            print("\n🎉 تمام محصولات با موفقیت پردازش شدند!")
            
        except KeyboardInterrupt:
            print(f"\n⏹️ ربات متوقف شد - وضعیت ذخیره شد")
            self.logger.info("⏹️ ربات توسط کاربر متوقف شد")
        except Exception as e:
            self.logger.error(f"❌ خطای کلی: {e}")
        finally:
            self.cleanup_with_progress_save(all_product_links if 'all_product_links' in locals() else None)

        
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
    scraper.run_parallel_with_resume()

if __name__ == "__main__":
    main()

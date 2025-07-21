#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import logging
import random
import platform
import subprocess
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urljoin, urlparse
import sys
import os

class ProductScraper:
    """
    ربات اسکرپینگ محصولات با استفاده از سلنیوم
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        راه‌اندازی ربات با بارگذاری کانفیگ
        """
        self.config = self.load_config(config_path)
        self.driver = None
        self.scraped_products = []
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
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',  # macOS
            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',    # Windows
            'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
        ]
        
        for path in chrome_paths:
            if os.path.exists(path):
                self.logger.info(f"✅ Chrome یافت شد در: {path}")
                return path
                
        # تلاش برای یافتن با which
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

    def human_like_delay(self, min_seconds=1, max_seconds=3):
        """
        تاخیر تصادفی برای شبیه‌سازی رفتار انسانی
        """
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
        
    def human_like_scroll(self, pause_time=None):
        """
        اسکرول طبیعی مانند انسان
        """
        if pause_time is None:
            pause_time = random.uniform(0.5, 1.5)
            
        # اسکرول تدریجی به جای یکباره
        current_scroll = self.driver.execute_script("return window.pageYOffset;")
        total_height = self.driver.execute_script("return document.body.scrollHeight;")
        
        # اسکرول به صورت تدریجی
        scroll_steps = random.randint(3, 6)
        step_height = (total_height - current_scroll) / scroll_steps
        
        for i in range(scroll_steps):
            scroll_to = current_scroll + (step_height * (i + 1))
            self.driver.execute_script(f"window.scrollTo(0, {scroll_to});")
            time.sleep(random.uniform(0.3, 0.8))
            
        time.sleep(pause_time)
        
    def simulate_mouse_movement(self, element):
        """
        شبیه‌سازی حرکت موس طبیعی
        """
        try:
            actions = ActionChains(self.driver)
            
            # حرکت تصادفی موس قبل از کلیک
            actions.move_by_offset(random.randint(-50, 50), random.randint(-30, 30))
            actions.pause(random.uniform(0.1, 0.3))
            
            # حرکت به سمت المان
            actions.move_to_element(element)
            actions.pause(random.uniform(0.2, 0.5))
            
            actions.perform()
        except Exception as e:
            self.logger.warning(f"⚠️ خطا در شبیه‌سازی حرکت موس: {e}")
            
    def setup_driver(self):
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
            
            # تنظیمات برای سرور
            #chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            # سایر تنظیمات
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # تنظیم پورت ثابت
            chromedriver_path = '/usr/bin/chromedriver'
            if os.path.exists(chromedriver_path):
                self.logger.info(f"✅ استفاده از chromedriver سیستم: {chromedriver_path}")
                service = Service(chromedriver_path, port=9515)
            else:
                self.logger.error("❌ chromedriver یافت نشد")
                sys.exit(1)
            
            # ایجاد webdriver
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # اسکریپت‌های ضد تشخیص
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.implicitly_wait(10)
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
            
            # اسکرول طبیعی
            self.human_like_scroll()
            
            # تاخیر تصادفی بین اسکرول‌ها
            self.human_like_delay(1.5, 3.5)
            
            # گاهی اوقات اسکرول کمی به بالا (رفتار طبیعی کاربر)
            if random.random() < 0.3:  # 30% احتمال
                self.driver.execute_script("window.scrollBy(0, -100);")
                time.sleep(random.uniform(0.5, 1.0))
            
        # بازگشت تدریجی به بالای صفحه
        self.driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
        self.human_like_delay(2, 3)
        
    def extract_product_links(self) -> List[str]:
        """
        استخراج لینک‌های محصولات از صفحه اصلی با رفتار طبیعی
        """
        self.logger.info("🔍 شروع استخراج لینک‌های محصولات...")
        
        try:
            # بارگذاری صفحه اصلی
            self.driver.get(self.config['main_page_url'])
            
            # تاخیر طبیعی برای بارگذاری صفحه
            self.human_like_delay(3, 5)
            
            # شبیه‌سازی خواندن صفحه توسط کاربر
            self.driver.execute_script("window.scrollTo(0, 200);")
            self.human_like_delay(1, 2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            self.human_like_delay(1, 1.5)
            
            # اسکرول برای بارگذاری تمام محصولات
            scroll_count = self.config.get('scroll_count', 0)
            if scroll_count > 0:
                self.scroll_page(scroll_count)
            
            # استخراج لینک‌های محصولات
            product_selector = self.config['selectors']['product_links']
            product_elements = self.driver.find_elements(By.CSS_SELECTOR, product_selector)
            
            product_links = []
            for i, element in enumerate(product_elements):
                try:
                    # شبیه‌سازی حرکت موس روی المان (گاهی اوقات)
                    if random.random() < 0.1:  # 10% احتمال
                        self.simulate_mouse_movement(element)
                        
                    href = element.get_attribute('href')
                    if href:
                        # تبدیل لینک نسبی به مطلق
                        full_url = urljoin(self.config['main_page_url'], href)
                        if full_url not in product_links:
                            product_links.append(full_url)
                            
                    # تاخیر کوچک بین استخراج هر لینک
                    if i % 10 == 0:  # هر 10 لینک
                        time.sleep(random.uniform(0.1, 0.3))
                        
                except Exception as e:
                    self.logger.warning(f"⚠️ خطا در استخراج لینک: {e}")
                    continue
                    
            self.logger.info(f"✅ تعداد {len(product_links)} لینک محصول استخراج شد")
            return product_links
            
        except Exception as e:
            self.logger.error(f"❌ خطا در استخراج لینک‌های محصولات: {e}")
            return []
            
    def extract_product_data(self, product_url: str) -> Optional[Dict]:
        """
        استخراج اطلاعات محصول از صفحه محصول با رفتار انسانی
        """
        try:
            self.logger.info(f"📊 استخراج اطلاعات محصول: {product_url}")
            
            # بارگذاری صفحه محصول
            self.driver.get(product_url)
            
            # تاخیر طبیعی برای بارگذاری صفحه
            self.human_like_delay(2, 4)
            
            # شبیه‌سازی خواندن صفحه محصول
            self.driver.execute_script("window.scrollTo(0, 300);")
            self.human_like_delay(1, 2)
            
            # گاهی اوقات اسکرول بیشتر برای دیدن جزئیات
            if random.random() < 0.4:  # 40% احتمال
                self.driver.execute_script("window.scrollTo(0, 600);")
                self.human_like_delay(1, 1.5)
                self.driver.execute_script("window.scrollTo(0, 100);")
                self.human_like_delay(0.5, 1)
            
            product_data = {
                'url': product_url,
                'title': None,
                'categories': []
            }
            
            # استخراج عنوان محصول
            try:
                title_element = WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.config['selectors']['product_title']))
                )
                
                # شبیه‌سازی نگاه به عنوان
                self.simulate_mouse_movement(title_element)
                time.sleep(random.uniform(0.3, 0.7))
                
                product_data['title'] = title_element.text.strip()
                self.logger.info(f"📝 عنوان محصول: {product_data['title']}")
            except TimeoutException:
                self.logger.warning(f"⚠️ عنوان محصول یافت نشد: {product_url}")
                
            # استخراج دسته‌بندی‌ها
            categories_selectors = self.config['selectors']['categories']
            for i, selector in enumerate(categories_selectors):
                try:
                    category_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    category_text = category_element.text.strip()
                    if category_text:
                        product_data['categories'].append({
                            'level': i + 1,
                            'name': category_text
                        })
                        self.logger.info(f"🏷️ دسته‌بندی {i+1}: {category_text}")
                        
                        # تاخیر کوچک بین استخراج دسته‌بندی‌ها
                        time.sleep(random.uniform(0.1, 0.3))
                        
                except NoSuchElementException:
                    # اگر دسته‌بندی وجود نداشت، ادامه می‌دهیم
                    break
                except Exception as e:
                    self.logger.warning(f"⚠️ خطا در استخراج دسته‌بندی {i+1}: {e}")
                    
            # تاخیر کوتاه قبل از رفتن به محصول بعدی
            self.human_like_delay(0.5, 1.5)
                    
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
            # ذخیره در فرمت JSON
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.scraped_products, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"💾 اطلاعات در فایل {filename} ذخیره شد")
            
            # نمایش آمار
            total_products = len(self.scraped_products)
            successful_products = len([p for p in self.scraped_products if p.get('title')])
            
            print(f"\n📈 آمار نهایی:")
            print(f"🔢 تعداد کل محصولات: {total_products}")
            print(f"✅ محصولات موفق: {successful_products}")
            print(f"❌ محصولات ناموفق: {total_products - successful_products}")
            
        except Exception as e:
            self.logger.error(f"❌ خطا در ذخیره اطلاعات: {e}")
            
    def run(self):
        """
        اجرای اصلی ربات
        """
        try:
            print("🤖 شروع اجرای ربات اسکرپینگ...")
            
            # راه‌اندازی مرورگر
            self.setup_driver()
            
            # استخراج لینک‌های محصولات
            product_links = self.extract_product_links()
            
            if not product_links:
                self.logger.error("❌ هیچ لینک محصولی یافت نشد")
                return
                
            # استخراج اطلاعات هر محصول
            total_products = len(product_links)
            for i, product_url in enumerate(product_links, 1):
                print(f"\n🔄 پردازش محصول {i} از {total_products}")
                
                product_data = self.extract_product_data(product_url)
                if product_data:
                    self.scraped_products.append(product_data)
                    
                # تاخیر تصادفی بین محصولات (رفتار طبیعی)
                if i < total_products:
                    delay = random.uniform(2, 6)  # تاخیر بین 2 تا 6 ثانیه
                    self.logger.info(f"⏱️ انتظار {delay:.1f} ثانیه قبل از محصول بعدی...")
                    time.sleep(delay)
                    
            # ذخیره اطلاعات
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

def main():
    """
    تابع اصلی برنامه
    """
    print("=" * 60)
    print("🤖 ربات اسکرپینگ محصولات با سلنیوم")
    print("=" * 60)
    
    # بررسی وجود فایل کانفیگ
    config_file = "config.json"
    if not os.path.exists(config_file):
        print(f"❌ فایل کانفیگ یافت نشد: {config_file}")
        print("لطفاً ابتدا فایل config.json را ایجاد کنید")
        return
        
    # اجرای ربات
    scraper = ProductScraper(config_file)
    scraper.run()

if __name__ == "__main__":
    main()

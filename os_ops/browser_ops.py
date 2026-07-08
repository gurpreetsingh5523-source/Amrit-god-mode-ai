"""Browser Operations — Selenium-based web automation with auto ChromeDriver detection."""
from typing import List, Optional
import time
from logger import setup_logger
logger = setup_logger("BrowserOps")

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False
    logger.warning("selenium not installed — BrowserOps disabled")


def _find_chromedriver() -> Optional[str]:
    """Auto-detect chromedriver binary path."""
    import shutil
    # Prefer chromedriver in PATH
    found = shutil.which("chromedriver")
    if found:
        return found
    # Common macOS locations
    for path in [
        "/usr/local/bin/chromedriver",
        "/opt/homebrew/bin/chromedriver",
        "/usr/bin/chromedriver",
    ]:
        import os
        if os.path.exists(path):
            return path
    return None  # selenium-manager will handle it (selenium >= 4.6)


class BrowserOps:
    """Browser automation: navigate, extract text, click, fill forms."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None

    def _options(self) -> "Options":
        opts = Options()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        return opts

    def open_browser(self) -> bool:
        """Open browser. Returns True on success."""
        if not SELENIUM_OK:
            logger.warning("Selenium not available")
            return False
        try:
            driver_path = _find_chromedriver()
            if driver_path:
                service = Service(driver_path)
                self.driver = webdriver.Chrome(service=service, options=self._options())
            else:
                # Let selenium-manager auto-download chromedriver
                self.driver = webdriver.Chrome(options=self._options())
            logger.info("Browser opened")
            return True
        except WebDriverException as e:
            logger.warning(f"Browser open failed: {e}")
            return False

    def navigate(self, url: str, wait: float = 1.0) -> bool:
        """Navigate to URL. Auto-opens browser if not open."""
        if not self.driver:
            if not self.open_browser():
                return False
        try:
            self.driver.get(url)
            time.sleep(wait)
            logger.info(f"Navigated to {url}")
            return True
        except Exception as e:
            logger.warning(f"Navigate failed: {e}")
            return False

    def get_page_text(self) -> str:
        """Extract visible text from current page."""
        if not self.driver:
            return ""
        try:
            from selenium.webdriver.common.by import By
            body = self.driver.find_element(By.TAG_NAME, "body")
            return body.text[:8000]
        except Exception:
            return self.driver.page_source[:8000] if self.driver else ""

    def get_page_source(self) -> str:
        return self.driver.page_source if self.driver else ""

    def get_title(self) -> str:
        return self.driver.title if self.driver else ""

    def get_current_url(self) -> str:
        return self.driver.current_url if self.driver else ""

    def find_element(self, by, value: str):
        return self.driver.find_element(by, value)

    def find_elements(self, by, value: str) -> list:
        return self.driver.find_elements(by, value)

    def click(self, by, value: str, timeout: int = 10) -> bool:
        try:
            el = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            el.click()
            return True
        except TimeoutException:
            return False

    def type_text(self, by, value: str, text: str) -> bool:
        try:
            el = self.find_element(by, value)
            el.clear()
            el.send_keys(text)
            return True
        except Exception:
            return False

    def get_text(self, by, value: str) -> str:
        try:
            return self.find_element(by, value).text
        except Exception:
            return ""

    def wait_for_element(self, by, value: str, timeout: int = 10) -> bool:
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return True
        except TimeoutException:
            return False

    def screenshot(self, path: str = "workspace/screenshot.png") -> bool:
        try:
            self.driver.save_screenshot(path)
            return True
        except Exception:
            return False

    def close_browser(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            logger.info("Browser closed")

    def __enter__(self):
        self.open_browser()
        return self

    def __exit__(self, *_):
        self.close_browser()

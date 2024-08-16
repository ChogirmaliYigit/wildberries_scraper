"""
web driver module
"""

import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_argument("--headless")  # Run in headless mode
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")  # Disable GPU acceleration


class WebDriver:
    """
    Scrapping with webdriver
    """

    def __init__(self, network: str) -> None:
        """
        Web driver initialization
        """
        self.network = network
        self.driver: webdriver.Chrome = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )

    def get_html_content(self) -> str:
        """
        Get HTML content from given network
        """
        self.driver.get(self.network)

        # helps to bypassing cloudflare
        time.sleep(5)
        html_content = self.driver.page_source
        self.driver.close()
        return html_content

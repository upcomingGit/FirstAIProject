import sys
import argparse
import time
import pandas as pd
from dotenv import load_dotenv
from pydantic import ValidationError
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SECTIONS = {
    "balance-sheet": "Balance Sheet",
    "profit-loss": "Profit & Loss",
    "cash-flow": "Cash Flow"
}

def setup_driver():
    """Initialize headless Chrome driver."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(service=Service(), options=options)

def expand_all_buttons(driver, section_id):
    """Click all collapsible buttons in a given section."""
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, section_id))
        )
        buttons = driver.find_elements(
            By.XPATH, f"//section[@id='{section_id}']//button[contains(@onclick, 'Company.showSchedule')]"
        )
        for button in buttons:
            driver.execute_script("arguments[0].click();", button)
            time.sleep(0.3)
    except Exception as e:
        print(f"[!] Could not expand {section_id}: {e}")

def extract_table(driver, section_id):
    """Extract table from a section and return as DataFrame."""
    soup = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.select_one(f"section#{section_id} table")
    if table:
        return pd.read_html(str(table))[0]
    else:
        print(f"[!] No table found in section: {section_id}")
        return pd.DataFrame()

def main():
    parser = argparse.ArgumentParser(description="Extract financial data from a Screener Link.")
    parser.add_argument("input_link", type=str, help="Path to the input PDF file")
    args = parser.parse_args()

    url = args.input_link 
    #"https://www.screener.in/company/OBEROIRLTY/consolidated/"
    driver = setup_driver()
    driver.get(url)

    results = {}

    for section_id, label in SECTIONS.items():
        print(f"\n{'=' * 40}\nScraping: {label}\n{'=' * 40}")
        expand_all_buttons(driver, section_id)
        df = extract_table(driver, section_id)
        results[label] = df
        if not df.empty:
            print(df.to_string())
        else:
            print("[!] No data extracted.")

        # Optional CSV Export:
        # df.to_csv(f"{label.replace(' ', '_').lower()}.csv", index=False)

    driver.quit()
    return results

if __name__ == "__main__":
    financial_data = main()

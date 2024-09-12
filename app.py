from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import csv
import re
import time
import threading
import os
import zipfile
import requests
import subprocess
import shutil

app = Flask(__name__)

results = []
result_count = 0
scraping_active = True

DOWNLOAD_FOLDER = 'downloads'  # Choose a directory where files will be stored temporarily

# ChromeDriver management functions
def get_chrome_version():
    """Get the version of the installed Chrome browser using the Windows registry."""
    try:
        # Query the Windows registry to get the installed Chrome version
        command = r'reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version'
        version_output = subprocess.check_output(command, shell=True).decode()
        
        # Extract the version number from the command output
        version_line = version_output.strip().split('\n')[-1]
        chrome_version = version_line.split()[-1]
        return chrome_version
    except Exception as e:
        print(f"Error getting Chrome version: {e}")
        return None

def get_chromedriver_version():
    """Get the version of the installed Chromedriver."""
    try:
        chromedriver_path = os.path.join(os.getcwd(), "Chromedriver", "chromedriver.exe")
        if not os.path.exists(chromedriver_path):
            raise FileNotFoundError("Chromedriver executable not found in the expected directory.")
        
        # Execute chromedriver.exe to get its version
        output = subprocess.check_output([chromedriver_path, '--version']).decode().strip()
        return output.split()[1]
    except Exception as e:
        print(f"Error getting Chromedriver version: {e}")
        return None

def download_chromedriver(chrome_version):
    """Download the compatible Chromedriver for the given Chrome version using the specified URL format."""
    if not chrome_version:
        print("Cannot determine Chrome version. Please ensure Chrome is installed correctly.")
        return

    # Construct the download URL using the Chrome version
    download_url = f"https://storage.googleapis.com/chrome-for-testing-public/{chrome_version}/win64/chromedriver-win64.zip"
    
    try:
        # Downloading the zip file
        print(f"Downloading Chromedriver from: {download_url}")
        r = requests.get(download_url, stream=True)
        
        if r.status_code == 200:
            zip_path = os.path.join(os.getcwd(), "chromedriver.zip")
            with open(zip_path, 'wb') as file:
                file.write(r.content)
            
            # Extracting the zip file contents
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall("Chromedriver")
            
            # Move files from 'chromedriver-win64' to 'Chromedriver' folder
            extracted_folder = os.path.join("Chromedriver", "chromedriver-win64")
            if os.path.exists(extracted_folder):
                for file_name in os.listdir(extracted_folder):
                    shutil.move(os.path.join(extracted_folder, file_name), "Chromedriver")
                os.rmdir(extracted_folder)  # Remove the empty folder
            
            # Clean up zip file
            os.remove(zip_path)
            print(f"Downloaded and extracted Chromedriver version: {chrome_version}")
        else:
            print("Failed to download Chromedriver. Please check the URL and Chrome version.")
    
    except Exception as e:
        print(f"Error during Chromedriver download: {e}")

def setup_chromedriver():
    """Ensure Chromedriver is set up correctly with matching Chrome version."""
    if not os.path.exists("Chromedriver"):
        os.makedirs("Chromedriver")
    
    chrome_version = get_chrome_version()
    driver_version = get_chromedriver_version()

    if chrome_version and driver_version and chrome_version.startswith(driver_version.split('.')[0]):
        print("ChromeDriver and Chrome versions are compatible.")
    else:
        print("Updating ChromeDriver to match the Chrome version.")
        download_chromedriver(chrome_version)

# Set up ChromeDriver at application start
setup_chromedriver()


@app.route('/')
def index():
    return render_template('index.html')

def scrape_google_maps(query, location):
    global result_count
    global scraping_active
    # chrome_service = Service(executable_path='chromedriver-win64/chromedriver.exe')
    # driver = webdriver.Chrome(service=chrome_service)

    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run Chrome in headless mode
    chrome_options.add_argument('--no-sandbox')  # Disable sandboxing for headless mode
    chrome_options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems in headless mode

    # Set up the Chrome driver
    chrome_service = Service(executable_path='chromedriver-win64/chromedriver.exe')
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

    url = f'https://www.google.com/maps/search/{query}+in+{location}'
    driver.get(url)
    time.sleep(3)

    result_count = 0
    counter = 0
    while True:
        current_result_count = len(driver.find_elements(By.CSS_SELECTOR, 'div.Nv2PK.THOPZb.CpccDe'))
        for _ in range(50):
            scrollable_element = driver.find_element(By.CLASS_NAME, "m6QErb.DxyBCb.kA9KIf.dS8AEf.ecceSd")
            ActionChains(driver).move_to_element(scrollable_element).send_keys(Keys.PAGE_DOWN).perform()
        time.sleep(1)
        updated_result_count = len(driver.find_elements(By.CSS_SELECTOR, 'div.Nv2PK.THOPZb.CpccDe'))
        if updated_result_count == current_result_count:
            break
        result_count = updated_result_count

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser', from_encoding='utf-8')
    results_soup = soup.find_all('div', class_='Nv2PK')

    for result in results_soup:
        counter += 1
        print(counter, "/", result_count)
        title = result.find('div', class_='qBF1Pd').text.strip()
        rating_span = result.find('span', class_='e4rVHe')
        rating = rating_span.text.strip() if rating_span else 'N/A'
        link_element = result.find('a', class_='hfpxzc')
        link = link_element['href'] if link_element else 'N/A'

        driver.execute_script(f'window.open("{link}","_blank");')
        time.sleep(2)  # Give it time to open the tab
        driver.switch_to.window(driver.window_handles[-1])
        print(f'Switched to tab: {driver.current_url}')

        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, '[aria-label*="Phone"], [aria-label*="Website"], [aria-label*="Address"]')))

        try:
            phone_element = driver.find_element(By.CSS_SELECTOR, '[aria-label*="Phone"]')
            phone = phone_element.text.strip()[2:]
        except NoSuchElementException:
            phone = 'N/A'

        try:
            address_element = driver.find_element(By.CSS_SELECTOR, '[aria-label*="Address"]')
            address = address_element.text.strip()[2:]
        except NoSuchElementException:
            address = 'N/A'

        try:
            website_element = driver.find_element(By.CSS_SELECTOR, '[aria-label*="Website"]')
            website = website_element.text.strip()[2:]
            email = 'N/A'
            if '.' not in website:
                website = 'N/A'
                page_text = driver.find_element(By.TAG_NAME, 'body').text
                emails = re.findall(r'\S+@\S+', page_text)
                email = emails[0] if emails else 'N/A'
            else:
                try:
                    driver.get(f'https://{website}')
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body')))
                    try:
                        email_element = driver.find_element(By.XPATH,'//a[starts-with(@href, "mailto:")]')
                        email = re.sub(r'^mailto:', '', email_element.get_attribute('href'))
                    except NoSuchElementException:
                        page_text = driver.find_element(By.TAG_NAME, 'body').text
                        emails = re.findall(r'\S+@\S+', page_text)
                        email = emails[0] if emails else 'N/A'
                except (TimeoutException, WebDriverException):
                    email = 'N/A'
        except NoSuchElementException:
            website = 'N/A'
            email = 'N/A'

        result_data = {
            'name': title,
            'rating': rating,
            'address': address,
            'phone': phone,
            'website': website,
            'email': email,
            'link': link
        }
        results.append(result_data)

        # Close the tab and switch back to the original tab
        driver.close()
        driver.switch_to.window(driver.window_handles[0])

    driver.quit()
    scraping_active = False

@app.route('/scrape', methods=['POST'])
def scrape():
    query = request.form['query']
    location = request.form['location']
    global results
    results = []

    scrape_thread = threading.Thread(target=scrape_google_maps, args=(query, location))
    scrape_thread.start()

    return jsonify({'status': 'Scraping started'}), 202

@app.route('/get_results', methods=['GET'])
def get_results():
    if scraping_active:
        return jsonify(results)
    else:
        return jsonify({'status': 'Scraping Ended'}), 200


if __name__ == '__main__':
    app.run(debug=True)
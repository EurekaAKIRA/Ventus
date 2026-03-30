
import pytest
from pytest_bdd import scenarios, given, when, then
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# Constants
BASE_URL = 'https://en.wikipedia.org/'

# Scenarios
scenarios('demo_taobao.feature')

# Fixtures
@pytest.fixture
def browser():
    driver = webdriver.Chrome()
    driver.implicitly_wait(10)
    yield driver
    driver.quit()

# Steps
@given('the user is on the homepage')
def the_user_is_on_the_homepage(browser: webdriver.Chrome):
    browser.get(BASE_URL)
@then('the page should display "Wikipedia"')
def the_page_should_display_wikipedia(browser: webdriver.Chrome):
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    expected_text = "Wikipedia"
    title_element = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.XPATH, "//title[contains(text(), 'Wikipedia')]"))
    )
    actual_title = title_element.get_attribute("textContent").strip()
    assert expected_text in actual_title

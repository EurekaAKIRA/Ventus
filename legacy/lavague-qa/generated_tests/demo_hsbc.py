
import pytest
from pytest_bdd import scenarios, given, when, then
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# Constants
BASE_URL = 'https://www.hsbc.fr/'

# Scenarios
scenarios('demo_hsbc.feature')

# Fixtures
@pytest.fixture
def browser():
    driver = webdriver.Chrome()
    driver.implicitly_wait(10)
    yield driver
    driver.quit()

# Steps
@given('the user is on the HSBC homepage')
def the_user_is_on_the_hsbc_homepage(browser: webdriver.Chrome):
    browser.get(BASE_URL)
@when('the user clicks on "Tout accepter" to accept cookies')
def the_user_clicks_on_tout_accepter_to_accept_cookies(browser: webdriver.Chrome):
    element = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div/div/div[3]/button'))
    )
    browser.execute_script('arguments[0].click();', element)

@when('the user clicks on "Global Banking and Markets"')
def the_user_clicks_on_global_banking_and_markets(browser: webdriver.Chrome):
    element = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable((By.XPATH, '/html/body/div[2]/div[2]/header[2]/div[2]/div/ul/li[2]/a'))
    )
    browser.execute_script('arguments[0].click();', element)

@when('the user clicks on "Je comprends, continuons"')
def the_user_clicks_on_je_comprends_continuons(browser: webdriver.Chrome):
    element = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div/div/div/a[2]'))
    )
    browser.execute_script('arguments[0].click();', element)

@when('the user navigates to the new tab opened')
def the_user_navigates_to_the_new_tab_opened(browser: webdriver.Chrome):
    browser.switch_tab(tab_id=1)
@when('the user clicks on "Accept all cookies"')
def the_user_clicks_on_accept_all_cookies(browser: webdriver.Chrome):
    element = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable((By.XPATH, '/html/body/div[2]/div/div/div[2]/button'))
    )
    browser.execute_script('arguments[0].click();', element)

@when('the user clicks on "About us"')
def the_user_clicks_on_about_us(browser: webdriver.Chrome):
    element = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable((By.XPATH, '/html/body/div/div/div/div/div/div/nav/div/ul/li[4]/a'))
    )
    browser.execute_script('arguments[0].click();', element)

@then('the user should be on the "About us" page of the "Global Banking and Markets" services of HSBC')
def the_user_should_be_on_the_about_us_page_of_the_global_banking_and_markets_services_of_hsbc(browser: webdriver.Chrome):
    
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    
    # Wait for the page to load and verify we're on the correct page
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.XPATH, "//meta[@property='og:title' and @content='About us']"))
    )
    
    # Verify the page title contains the expected text
    page_title = browser.title
    assert "About Global Banking and Markets" in page_title, f"Expected 'About Global Banking and Markets' in title, but got: {page_title}"
    assert "HSBC" in page_title, f"Expected 'HSBC' in title, but got: {page_title}"
    
    # Verify the URL contains the expected path
    current_url = browser.current_url
    assert "/en-gb/about-us" in current_url, f"Expected '/en-gb/about-us' in URL, but got: {current_url}"
    
    # Verify the active navigation menu item is "About us"
    active_menu_item = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.XPATH, "//li[contains(@class, 'HeaderComponent_active')]/a[text()='About us']"))
    )
    assert active_menu_item.is_displayed(), "Active 'About us' menu item is not displayed"

Feature: Wikipedia Landing

  Scenario: Open the Wikipedia homepage
    Given the user is on the homepage
    Then the page should display "Wikipedia"

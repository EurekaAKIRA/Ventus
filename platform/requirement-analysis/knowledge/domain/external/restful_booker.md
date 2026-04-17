# Restful Booker Domain Knowledge

## Domain Facts
- Restful Booker commonly uses `POST /auth` to obtain a token and carries it through a cookie.
- `POST /booking` creates a booking and returns `bookingid`, which can seed detail, update, patch, and delete flows.
- `GET /booking` and filtered booking queries are read-only and can be validated with structural assertions when business data is unstable.

## Scenario Hints
- A practical lifecycle chain is `POST /auth` -> `POST /booking` -> `GET /booking/{id}` -> `PUT/PATCH /booking/{id}` -> `DELETE /booking/{id}`.
- `GET /ping` is a health-style endpoint and often has a documented status expectation independent of booking CRUD.

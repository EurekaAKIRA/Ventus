# Restful Booker smoke test

Base URL: `https://restful-booker.herokuapp.com`

Cover auth and booking APIs. The document is intentionally brief and does not describe context variables.

APIs:

- `POST /auth`
- `GET /booking`
- `GET /booking/{id}`
- `POST /booking`
- `PUT /booking/{id}`
- `PATCH /booking/{id}`
- `DELETE /booking/{id}`

Use username/password to get a token. Create one booking, then read, update and delete booking data. Also list bookings.

Expected: each request should return a valid response and the booking flow should be usable.

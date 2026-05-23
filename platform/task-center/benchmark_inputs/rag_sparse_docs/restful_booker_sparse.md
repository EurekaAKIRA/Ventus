# Restful Booker sparse requirement

Target system: Restful Booker.

Base URL: `https://restful-booker.herokuapp.com`

Need API tests for auth, booking creation, booking query, booking update, booking partial update, booking delete, and a simple health check.

The document intentionally omits exact HTTP methods, paths, token propagation details, and booking id extraction rules.

Expected: generated scenarios should recover a usable booking lifecycle from available knowledge rather than treating each operation as an isolated vague action.

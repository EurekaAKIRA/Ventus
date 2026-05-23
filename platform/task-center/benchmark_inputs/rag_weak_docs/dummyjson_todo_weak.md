# DummyJSON todo API quick notes

Base URL: `https://dummyjson.com`

Need test login and todo APIs.

Interfaces:

- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/refresh`
- `GET /todos`
- `GET /todos/{id}`
- `GET /todos/user/{id}`
- `POST /todos/add`
- `PUT /todos/{id}`
- `PATCH /todos/{id}`
- `DELETE /todos/{id}`

Login uses username and password. Todo add/update/delete should succeed. List and detail should return JSON.

Run a few useful scenarios for read and write.

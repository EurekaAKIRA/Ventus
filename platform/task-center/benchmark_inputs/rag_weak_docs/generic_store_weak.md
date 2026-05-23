# Store API draft

Base URL: `https://api.example.local`

We have a product service. Please generate API tests for common product operations.

Endpoints:

- `GET /products`
- `GET /products/{id}`
- `POST /products`
- `PUT /products/{id}`
- `PATCH /products/{id}`
- `DELETE /products/{id}`

Create product uses JSON body with name, price and status. Update changes the price or status. Delete removes a product. Detail should show one product.

Expected: status codes are successful and response is JSON.

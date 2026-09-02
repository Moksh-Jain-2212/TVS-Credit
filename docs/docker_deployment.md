# Docker deployment

## Local demo deployment

Prerequisites: Docker Desktop must be installed and running.

1. Create the backend environment file from the template:

   ```powershell
   Copy-Item backend/.env.example backend/.env
   ```

2. Edit `backend/.env` and set a strong `JWT_SECRET`. For a local demo, keep
   `OTP_DELIVERY_MODE=MOCK_CONSOLE`, or configure SMTP if email OTP delivery is
   required. Never commit this file.

3. Start the application from the repository root:

   ```powershell
   docker compose up --build
   ```

4. Open `http://localhost:3000`. The API health endpoint is
   `http://localhost:8000/health`.

On its first start, the backend creates a deterministic, synthetic demo
fixture and a local demo admin. Raw PKDD, Home Credit, and PaySim files are not
copied to the image.

Stop containers with `docker compose down`. The named volumes intentionally
preserve the local SQLite database, generated fixture, and model artifacts.
To reset only the Docker demo data, run `docker compose down -v`.

## Deployment notes

`NEXT_PUBLIC_API_BASE_URL` is compiled into the frontend image. Before a cloud
build, set it to the public HTTPS URL of the backend, and set
`CORS_ALLOW_ORIGINS` to the public HTTPS URL of the frontend.

The Docker setup uses SQLite for a single-instance demo deployment. A
production deployment should use a managed database, secret manager, HTTPS
reverse proxy, managed email provider, and a persistent object/model store.

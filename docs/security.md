# Security

Implemented controls:

- Email normalization and password validation.
- PBKDF2 password hashing.
- Short-lived access tokens and rotating refresh tokens.
- Logout revokes refresh sessions server-side.
- OTP expiry, retry limits, resend cooldown, and SMTP delivery without returning OTPs in email mode.
- Basic in-memory abuse controls for register, login, OTP verify, and OTP resend.
- Configurable CORS origins.
- Security headers and request IDs on API responses.
- Standard error envelope while preserving FastAPI `detail` for compatibility.

Production notes:

- Use strong `JWT_SECRET` and backend-only SMTP/xAI credentials.
- Prefer secure HttpOnly cookies for browser token transport in production.
- Put persistent rate limiting behind Redis or another shared store.
- Use Alembic migrations against PostgreSQL for managed production deployments.
- Do not log passwords, OTPs, bearer tokens, refresh tokens, or raw financial payloads.


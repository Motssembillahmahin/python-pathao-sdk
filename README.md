## Quick Start

### Sandbox Testing

Pathao provides public sandbox credentials for testing:

```
# .env.sandbox
PATHAO_CLIENT_ID=7N1aMJQbWm
PATHAO_CLIENT_SECRET=wRcaibZkUdSNz2EI9ZyuXLlNrnAv0TdPUPXMnD39
PATHAO_USERNAME=test@pathao.com
PATHAO_PASSWORD=lovePathao
PATHAO_ENVIRONMENT=sandbox
```

### Production

```
# .env
PATHAO_CLIENT_ID=your_client_id
PATHAO_CLIENT_SECRET=your_client_secret
PATHAO_USERNAME=your_username
PATHAO_PASSWORD=your_password
PATHAO_ENVIRONMENT=production
```
```

### .env.example File
Create a template file users can copy:

```bash
# Pathao Logistics SDK Configuration
# Copy this file to .env and fill in your credentials

# Required: Your Pathao API credentials
PATHAO_CLIENT_ID=
PATHAO_CLIENT_SECRET=
PATHAO_USERNAME=
PATHAO_PASSWORD=

# Environment: sandbox or production
PATHAO_ENVIRONMENT=production

# Optional: Custom settings
# PATHAO_BASE_URL=https://api-hermes.pathao.com
# PATHAO_TIMEOUT=30.0
# PATHAO_MAX_RETRIES=3
# PATHAO_WEBHOOK_SECRET=
```

## Helper for Sandbox Testing

Provide a convenience method for sandbox testing in your **examples** or **tests**:

```python
# examples/sandbox_setup.py
from pathao_logistics.config import PathaoConfig
from pathao_logistics import PathaoClient


def create_sandbox_client() -> PathaoClient:
    """
    Create a client configured for Pathao sandbox environment.

    Note: These are Pathao's public test credentials.
    For production, use your own credentials from environment variables.
    """
    config = PathaoConfig(
        pathao_client_id="7N1aMJQbWm",
        pathao_client_secret="wRcaibZkUdSNz2EI9ZyuXLlNrnAv0TdPUPXMnD39",
        pathao_username="test@pathao.com",
        pathao_password="lovePathao",
        pathao_environment="sandbox"
    )
    return PathaoClient(config=config)


# Usage in examples/tests
if __name__ == "__main__":
    import asyncio

    async def test_sandbox():
        async with create_sandbox_client() as client:
            cities = await client.stores.get_cities()
            print(f"Available cities: {len(cities)}")

    asyncio.run(test_sandbox())
```

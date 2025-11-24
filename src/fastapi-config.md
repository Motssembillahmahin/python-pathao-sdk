# Configure FastAPI

```text
Integrate FastAPI with this sdk by adding this in your project
```

# user's config.py (in their application)
```python
from pydantic_settings import BaseSettings
from src.config import PathaoConfig

class AppConfig(BaseSettings):
    # Their app settings
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["*"]
    APP_VERSION: str = "1.0"

    # Nested Pathao config
    pathao: PathaoConfig = PathaoConfig()

    class Config:
        env_file = ".env"
```

# user's main.py

```python
from fastapi import FastAPI
from src.client import PathaoClient

settings = AppConfig()

app = FastAPI()

@app.on_event("startup")
async def startup():
    app.state.pathao_client = PathaoClient(config=settings.pathao)
```

# AI Cenovnici API

Backend implementation for the AI Cenovnici application.

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── health.py
│   └── core/
│       ├── __init__.py
│       ├── config.py
│       └── logging.py
├── tests/
│   ├── __init__.py
│   └── test_health.py
├── pyproject.toml
├── Dockerfile
├── .env.example
└── README.md
```

## Features

- FastAPI backend with automatic OpenAPI documentation
- Health check endpoint at `/api/v1/health`
- Root endpoint at `/`
- Swagger UI at `/docs`
- ReDoc at `/redoc`
- CORS support
- Configuration management with pydantic-settings
- Logging setup

## Getting Started

### Prerequisites

- Python 3.12+
- Docker (for containerized development)

### Installation

```bash
# Install dependencies
pip install -e .
```

### Running the Application

```bash
# Run with uvicorn
uvicorn app.main:app --reload

# Or run with the script
ai-cenovnici-api
```

## API Endpoints

- `GET /` - Root endpoint with service information
- `GET /api/v1/health` - Health check endpoint
- `GET /docs` - Swagger UI documentation
- `GET /redoc` - ReDoc documentation

## Testing

Run tests with:

```bash
pytest
```

## Docker

Build and run with Docker:

```bash
docker build -t ai-cenovnici-api .
docker run -p 8000:8000 ai-cenovnici-api
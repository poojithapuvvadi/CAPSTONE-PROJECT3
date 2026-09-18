# Docker Setup Guide for AI IT Support Assistant

This guide helps you deploy the AI IT Support Assistant using Docker.

## Prerequisites

- Docker installed ([Install Docker](https://docs.docker.com/get-docker/))
- Docker Compose installed ([Install Docker Compose](https://docs.docker.com/compose/install/))
- An API key from OpenAI or Anthropic

## Quick Start with Docker Compose

### 1. Prepare Configuration

```bash
cp .env.example .env
```

Edit `.env` and add your API key:
```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
USE_LLM_RESPONSES=true
```

### 2. Start the Container

```bash
docker-compose up --build
```

The first run will build the Docker image, which may take a few minutes.

### 3. Access the Application

Open your browser and go to: http://localhost:8501

### 4. View Logs

```bash
docker-compose logs -f
```

### 5. Stop the Container

```bash
docker-compose down
```

## Docker CLI Usage

### Build the Image

```bash
docker build -t ai-it-support-assistant:latest .
```

### Run the Container

**With OpenAI:**
```bash
docker run -p 8501:8501 \
  --env OPENAI_API_KEY=sk-your-key-here \
  --env LLM_PROVIDER=openai \
  --env USE_LLM_RESPONSES=true \
  --volume $(pwd)/data:/app/data \
  --name ai-support \
  ai-it-support-assistant:latest
```

**With Anthropic Claude:**
```bash
docker run -p 8501:8501 \
  --env ANTHROPIC_API_KEY=sk-ant-your-key-here \
  --env LLM_PROVIDER=anthropic \
  --env USE_LLM_RESPONSES=true \
  --volume $(pwd)/data:/app/data \
  --name ai-support \
  ai-it-support-assistant:latest
```

**Without LLM (Fallback Mode):**
```bash
docker run -p 8501:8501 \
  --volume $(pwd)/data:/app/data \
  --name ai-support \
  ai-it-support-assistant:latest
```

### Check Container Status

```bash
docker ps
```

### View Logs

```bash
docker logs ai-support
```

### Stop the Container

```bash
docker stop ai-support
```

### Remove the Container

```bash
docker rm ai-support
```

## Port Mapping

By default, the app runs on port 8501 inside the container. You can map it to a different port on your host:

```bash
docker run -p 9000:8501 ai-it-support-assistant:latest
```

Then access at: http://localhost:9000

## Data Persistence

The SQLite database is stored in the `data/` directory. This directory is mounted as a volume to persist data across container restarts:

```bash
docker run -v $(pwd)/data:/app/data ai-it-support-assistant:latest
```

## Environment Variables

| Variable | Required | Options | Default |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | If using OpenAI | sk-... | empty |
| `ANTHROPIC_API_KEY` | If using Anthropic | sk-ant-... | empty |
| `LLM_PROVIDER` | No | `openai`, `anthropic` | `openai` |
| `USE_LLM_RESPONSES` | No | `true`, `false` | `true` |

## Docker Compose Configuration

The `docker-compose.yml` includes:
- Service name: `ai-support-assistant`
- Port mapping: 8501:8501
- Volume mounting: `./data:/app/data`
- Health checks
- Environment variables from `.env`

Customize it as needed for your deployment.

## Troubleshooting

### Container won't start
1. Check logs: `docker logs ai-support`
2. Ensure port 8501 is not in use
3. Verify API key is correct

### Database permission errors
- Ensure the `data/` directory has proper permissions
- Try: `chmod -R 755 data/`

### API key not recognized
- Check that `.env` file is properly mounted
- Verify API key format (must start with `sk-` for OpenAI or `sk-ant-` for Anthropic)

### Streamlit not responding
- Wait 30-40 seconds after container starts (Streamlit initialization time)
- Check health: `curl http://localhost:8501/_stcore/health`

## Production Deployment

For production deployments, consider:
1. Using a `.env` file with secure API key management
2. Setting resource limits: `--memory=2g --cpus=2`
3. Using a production registry (Docker Hub, ECR, etc.)
4. Adding SSL/TLS termination with a reverse proxy (nginx)
5. Using Docker Compose or Kubernetes for orchestration

Example with resource limits:
```bash
docker run -p 8501:8501 \
  --memory=2g \
  --cpus=2 \
  -v $(pwd)/data:/app/data \
  ai-it-support-assistant:latest
```

## More Information

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Streamlit Deployment Guide](https://docs.streamlit.io/library/deploy)

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000

# LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL are supplied at run time (docker run -e / --env-file).
CMD ["uvicorn", "--factory", "meeting_actions.main:create_app", "--host", "0.0.0.0", "--port", "8000"]

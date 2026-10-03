FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY web ./web
COPY data ./data
ENV HACKKIT_WEB_DIR=/app/web
EXPOSE 8000
CMD ["uvicorn", "--factory", "hackkit.server:create_app", "--host", "0.0.0.0", "--port", "8000"]

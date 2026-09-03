FROM python:3-slim

WORKDIR /workspace
COPY pyproject.toml README.md ./
COPY app ./src/app
ENV PYTHONPATH=/workspace
ENV NO_PROXY=localhost,127.0.0.1
RUN unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy && pip install --no-cache-dir -e .
EXPOSE 8080
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8080"]

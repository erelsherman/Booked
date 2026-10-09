FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir ".[web]"
ENV BOOKED_STATE_DIR=/tmp/booked-state
# Render tells the app which port to use through PORT.
CMD ["sh", "-c", "uvicorn booked.web.app:create_app --factory --host 0.0.0.0 --port ${PORT:-10000}"]

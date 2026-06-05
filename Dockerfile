FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py main.py quiz_manager.py ./
COPY db ./db
COPY static ./static
RUN mkdir -p /app/data
ENV CHAT_DB=/app/data/chat.db

ENV HOST=0.0.0.0
ENV PORT=8765

EXPOSE 8765

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8765"]

FROM python:3.13.7-slim
WORKDIR /app
COPY src ./src
COPY configs ./configs
COPY web ./web
EXPOSE 8787
CMD ["python3", "src/api/server.py", "--host", "0.0.0.0"]

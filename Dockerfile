FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -m app
COPY --chown=app:app . .
RUN mkdir -p /app/data && chown app:app /app/data
USER app
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0"]

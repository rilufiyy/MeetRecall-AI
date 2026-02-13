FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3005

CMD ["streamlit", "run", "app.py", "--server.port=3005", "--server.address=0.0.0.0"]
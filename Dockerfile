FROM python:3.11-slim

WORKDIR /app

# Install minimal build deps for scientific libs if needed
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY streamlit_app.py ./
COPY app_lib ./app_lib
COPY pages ./pages

# The database will be mounted into /app/data at runtime
RUN mkdir -p /app/data

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]


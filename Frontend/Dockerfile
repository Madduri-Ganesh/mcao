FROM python:3.9-slim

WORKDIR /home/app

# Install system dependencies for lxml
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY app.py InvokeLambda.py log_setup.py ./

CMD ["streamlit", "run", "app.py"]

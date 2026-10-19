# Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
# In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

FROM mcr.microsoft.com/playwright/python:v1.56.0-noble
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY walmart_scraper ./walmart_scraper
COPY config ./config
ENV WS_STORAGE=azure WS_STATE_DIR=/mnt/state PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "walmart_scraper"]
CMD ["run"]

FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libxrender1 libxext6 libexpat1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir rdkit==2026.3.6
WORKDIR /lab
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 REGEN_ROOT=/lab REGEN_DATA=/lab/data
CMD ["python", "/lab/workbench/tools/regen_desk.py", "serve", "--host", "0.0.0.0"]

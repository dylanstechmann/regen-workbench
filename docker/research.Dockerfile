FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive MAMBA_ROOT_PREFIX=/opt/conda
ENV PATH=/opt/conda/bin:${PATH}
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl bzip2 libxrender1 libxext6 libexpat1 autodock-vina \
    && rm -rf /var/lib/apt/lists/*
RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
      | tar -xvj -C /usr/local/bin --strip-components=1 bin/micromamba \
    && micromamba create -y -p /opt/conda -c conda-forge python=3.11 pip numpy openpyxl \
    && micromamba clean -a -y
RUN pip install --no-cache-dir rdkit==2026.3.6
WORKDIR /lab
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 REGEN_ROOT=/lab REGEN_DATA=/lab/data
RUN python -c "import rdkit; print('RDKit', rdkit.__version__)" && vina --version
CMD ["python", "/lab/workbench/tools/regen_desk.py", "serve", "--host", "0.0.0.0"]

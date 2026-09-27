# Regen Workbench
# CUDA runtime + micromamba scientific stack + agent CLI.
# Heavy folding weights are NOT baked in; they download into /lab/cache on first use.

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    MAMBA_ROOT_PREFIX=/opt/conda \
    PATH=/opt/conda/bin:/home/regen/.local/bin:${PATH} \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl wget git git-lfs build-essential \
        pkg-config cmake \
        libgl1 libglib2.0-0 libxrender1 libsm6 libxext6 \
        libegl1 libopengl0 \
        bzip2 unzip zip jq less vim tmux htop tree \
        ca-certificates gnupg \
        default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# micromamba
RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
        | tar -xvj -C /usr/local/bin --strip-components=1 bin/micromamba \
    && micromamba create -y -p /opt/conda -c conda-forge -c bioconda \
        python=3.11 \
        pip \
        jupyterlab \
        notebook \
        ipywidgets \
        numpy pandas scipy scikit-learn matplotlib seaborn \
        biopython \
        rdkit \
        openbabel \
        pymol-open-source \
        mdanalysis \
        biotite \
        pyyaml \
        rich \
        typer \
        httpx \
        requests \
        tqdm \
        networkx \
        py3dmol \
        logomaker \
        scanpy \
        anndata \
        leidenalg \
        python-igraph \
        nextflow \
        mafft \
        muscle \
        clustalo \
        hmmer \
        blast \
        mmseqs2 \
        foldseek \
        bedtools \
        samtools \
        minimap2 \
        fastqc \
        multiqc \
        seqkit \
        csvtk \
        parallel \
        autodock-vina \
        openmm \
    && micromamba clean -a -y

# pip-only scientific / agent helpers (kept small; GPU models optional)
RUN pip install --no-cache-dir \
        "fair-esm" \
        biopython \
        pubchempy \
        chembl-webresource-client \
        mygene \
        bioservices \
        gseapy \
        pyfaidx \
        parasail \
        gemmi \
        pdb2pqr \
        meeko \
    || pip install --no-cache-dir \
        fair-esm pubchempy chembl-webresource-client mygene \
        bioservices pyfaidx gemmi

# Optional: Boltz CLI if the package is on PyPI in this environment.
# Failure here must not break the workbench.
RUN pip install --no-cache-dir boltz && echo "boltz installed" || echo "boltz pip install skipped"

# Non-root user matching typical laptop UIDs; compose can still run as root if needed.
RUN useradd -m -u 1000 -s /bin/bash regen \
    && mkdir -p /lab /opt/regen \
    && chown -R regen:regen /lab /home/regen

WORKDIR /lab
COPY tools /opt/regen/tools
COPY config /opt/regen/config
RUN chmod +x /opt/regen/tools/*.py /opt/regen/tools/*.sh 2>/dev/null || true \
    && ln -sf /opt/regen/tools/regen /usr/local/bin/regen \
    && ln -sf /opt/regen/tools/regen.py /usr/local/bin/regen.py \
    && ln -sf /opt/regen/tools/regen_mcp.py /usr/local/bin/regen-mcp

# Health: python stack imports
RUN python - <<'PY'
import Bio, rdkit, numpy, pandas
from rdkit import Chem
print("ok", Chem.MolFromSmiles("CCO").GetNumAtoms())
PY

CMD ["bash"]

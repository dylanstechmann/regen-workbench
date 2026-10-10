FROM mambaorg/micromamba:2.9.0-debian13@sha256:ed1bc6280b1eadf303610c00befaf9ba52dbacbc988ae4d7d9765801465f129e
COPY --chown=$MAMBA_USER:$MAMBA_USER ipspdl_rnaseq_environment.yml /tmp/ipspdl_rnaseq_environment.yml
RUN micromamba install --yes --name base --file /tmp/ipspdl_rnaseq_environment.yml && micromamba clean --all --yes

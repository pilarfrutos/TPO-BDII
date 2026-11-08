FROM docker:28.0.4-cli@sha256:2bccc79fc5fed23d876bf244fa5fbe78c54bf6b6145a9483604306fd797237d5 AS docker-cli

FROM python:3.12.12-bookworm@sha256:c0abd0758831ad99b7a29e0c1a875da9c4abb9a2e3f21e2eeb585dbcadfb6cd0 AS development
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt && python -m pip check
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspaces/FarmaRed
CMD ["sleep", "infinity"]

# Misma imagen Python/dependencias para probar en una red y volúmenes aislados.
FROM development AS validation
WORKDIR /opt/farmared
COPY scripts/ scripts/
COPY data/original/ data/original/
COPY tests/t03/verify.py tests/t03/verify.py
CMD ["python", "tests/t03/verify.py"]

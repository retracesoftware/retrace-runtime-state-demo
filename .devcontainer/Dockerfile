FROM --platform=linux/amd64 python:3.12.13-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY .devcontainer/requirements.txt /tmp/retrace-demo-requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/retrace-demo-requirements.txt \
    && python -m pip check

WORKDIR /app
CMD ["sleep", "infinity"]

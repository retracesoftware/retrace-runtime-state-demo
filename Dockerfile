FROM --platform=linux/amd64 python:3.12.13-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b

ARG RETRACE_VERSION=0.2.30

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPYCACHEPREFIX=/tmp/retrace-pycache
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV RETRACE_AI_MAX_TOOL_CALLS=70
ENV RETRACE_AI_TIME_BUDGET=240
ENV RETRACE_AI_MAX_OUTPUT_TOKENS=8192
ENV RETRACE_AI_CORRECTION_ATTEMPTS=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt \
    && python -m pip install "retracesoftware==${RETRACE_VERSION}" \
    && python -m pip show retracesoftware \
    && python -m pip show retracesoftware-dap

COPY app/ /app/app/
COPY tests/ /app/tests/
COPY scripts/ /app/scripts/

RUN chmod +x /app/scripts/*.sh

CMD ["/app/scripts/run_demo.sh"]

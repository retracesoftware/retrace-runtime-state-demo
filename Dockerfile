FROM python:3.12-slim-bookworm

ARG RETRACE_VERSION=0.2.25

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV RETRACE_AI_MAX_TOOL_CALLS=70
ENV RETRACE_AI_TIME_BUDGET=240
ENV RETRACE_AI_MAX_OUTPUT_TOKENS=2600

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

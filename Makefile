.PHONY: preflight setup build run report example-report replay shell clean test stress require-live-ai-key live-ai-harness debugger-build debugger-verify debugger-verify-example debugger-clean

LIVE_AI_RUNS ?= 1

preflight:
	./scripts/preflight_host.sh

build: preflight
	docker compose build

setup: preflight
	docker compose pull incident-api
	docker compose build
	docker compose up -d incident-api

run: setup
	docker compose run --rm demo /app/scripts/run_demo.sh
	./scripts/open_report.sh reports/runtime-bug-report.md

report:
	./scripts/open_report.sh reports/runtime-bug-report.md

example-report:
	./scripts/open_report.sh example-reports/runtime-bug-report.md

replay:
	docker compose run --rm --no-deps demo /app/scripts/replay_trace.sh

shell:
	docker compose run --rm demo bash

clean:
	docker compose down -v --remove-orphans
	rm -rf recordings/* reports/* runtime-state/*

test:
	python3 -m unittest discover -s tests -p 'test_report_tools.py' -v

stress:
	@echo "The quota-consuming stress target is disabled by default."
	@echo "Run 'make live-ai-harness LIVE_AI_RUNS=1' for an explicit bounded check."
	@false

require-live-ai-key:
	@test -n "$(RETRACE_API_KEY)" || (echo "RETRACE_API_KEY is required for the live harness." >&2; exit 2)

live-ai-harness: require-live-ai-key setup
	ALLOW_FREE_RETRACE_AI=0 docker compose run --rm \
		-e RETRACE_RUN_LIVE_AI_HARNESS=1 \
		-e RETRACE_AI_CORRECTION_ATTEMPTS=0 \
		demo /app/scripts/stress_demo.sh "$(LIVE_AI_RUNS)"

debugger-build:
	docker compose -p retrace-runtime-state-debugger -f .devcontainer/docker-compose.yml build

debugger-verify: debugger-build
	docker compose -p retrace-runtime-state-debugger -f .devcontainer/docker-compose.yml run --rm demo python /app/scripts/verify_debugger.py --recording /app/recordings/runtime-incident.retrace

debugger-verify-example: debugger-build
	docker compose -p retrace-runtime-state-debugger -f .devcontainer/docker-compose.yml run --rm demo python /app/scripts/verify_debugger.py --all

debugger-clean:
	docker compose -p retrace-runtime-state-debugger -f .devcontainer/docker-compose.yml down -v --remove-orphans

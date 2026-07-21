.PHONY: preflight setup build run report example-report replay shell clean stress debugger-build debugger-verify debugger-verify-example debugger-clean

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

stress:
	docker compose run --rm demo /app/scripts/stress_demo.sh 5

debugger-build:
	docker compose -p retrace-runtime-state-debugger -f .devcontainer/docker-compose.yml build

debugger-verify: debugger-build
	docker compose -p retrace-runtime-state-debugger -f .devcontainer/docker-compose.yml run --rm demo python /app/scripts/verify_debugger.py --recording /app/recordings/runtime-incident.retrace

debugger-verify-example: debugger-build
	docker compose -p retrace-runtime-state-debugger -f .devcontainer/docker-compose.yml run --rm demo python /app/scripts/verify_debugger.py --all

debugger-clean:
	docker compose -p retrace-runtime-state-debugger -f .devcontainer/docker-compose.yml down -v --remove-orphans

.PHONY: preflight prepare convention build demo report example-report replay shell clean stress debugger-build debugger-verify debugger-clean

preflight:
	./scripts/preflight_host.sh

build: preflight
	docker compose build

prepare: preflight
	docker compose pull incident-api
	docker compose build
	docker compose up -d incident-api

demo: preflight
	docker compose run --build --rm demo /app/scripts/run_demo.sh

convention: demo
	./scripts/open_report.sh reports/runtime-incident.presentation.md

report:
	./scripts/open_report.sh reports/runtime-incident.presentation.md

example-report:
	./scripts/open_report.sh example-reports/runtime-incident.presentation.md

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
	docker compose -p retrace-runtime-state-debugger -f .devcontainer/docker-compose.yml run --rm demo python /app/scripts/verify_debugger.py --all

debugger-clean:
	docker compose -p retrace-runtime-state-debugger -f .devcontainer/docker-compose.yml down -v --remove-orphans

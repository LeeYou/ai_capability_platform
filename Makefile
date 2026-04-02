SHELL := /bin/bash

.PHONY: init-host-root shared-assets backend-test frontend-check docker-build compose-config

init-host-root:
	bash scripts/docker/init_host_root.sh

shared-assets:
	python -m unittest discover -s apps/shared/tests -v

backend-test:
	cd apps/ai-train/backend && PYTHONPATH=. python -m unittest discover -s tests -v
	cd apps/ai-test/backend && PYTHONPATH=. python -m unittest discover -s tests -v
	cd apps/ai-license-mgr/backend && PYTHONPATH=. python -m unittest discover -s tests -v
	cd apps/ai-builder/backend && PYTHONPATH=. python -m unittest discover -s tests -v
	cd apps/ai-prod/backend && PYTHONPATH=. python -m unittest discover -s tests -v
	cd apps/ai-sdk/backend && PYTHONPATH=. python -m unittest discover -s tests -v

frontend-check:
	cd apps/ai-train/frontend && npm ci && npm run build && npm run lint
	cd apps/ai-test/frontend && npm ci && npm run build && npm run lint
	cd apps/ai-license-mgr/frontend && npm ci && npm run build && npm run lint
	cd apps/ai-builder/frontend && npm ci && npm run build && npm run lint
	cd apps/ai-prod/frontend && npm ci && npm run build && npm run lint

docker-build:
	docker build -f Dockerfile.base.cuda118 -t ai-capability-platform/base:cuda118 .
	docker build --build-arg AI_CAP_BASE_IMAGE=ai-capability-platform/base:cuda118 -f apps/ai-train/Dockerfile .
	docker build --build-arg AI_CAP_BASE_IMAGE=ai-capability-platform/base:cuda118 -f apps/ai-test/Dockerfile .
	docker build --build-arg AI_CAP_BASE_IMAGE=ai-capability-platform/base:cuda118 -f apps/ai-license-mgr/Dockerfile .
	docker build --build-arg AI_CAP_BASE_IMAGE=ai-capability-platform/base:cuda118 -f apps/ai-builder/Dockerfile .
	docker build --build-arg AI_CAP_BASE_IMAGE=ai-capability-platform/base:cuda118 -f apps/ai-prod/Dockerfile .
	docker build --build-arg AI_CAP_BASE_IMAGE=ai-capability-platform/base:cuda118 -f apps/ai-sdk/Dockerfile .

compose-config:
	docker compose config >/dev/null

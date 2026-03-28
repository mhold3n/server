.PHONY: bootstrap verify train-sft train-clm eval package-runtime serve-local run-agent test lint

bootstrap:
	bash scripts/bootstrap.sh

verify:
	python scripts/verify_env.py

train-sft:
	python scripts/train_sft.py

train-clm:
	python scripts/train_clm.py

eval:
	python scripts/evaluate.py

package-runtime:
	python scripts/package_runtime.py

serve-local:
	python scripts/serve_local.py

run-agent:
	python scripts/run_agent.py

test:
	pytest tests/

lint:
	ruff check src/ scripts/ tests/

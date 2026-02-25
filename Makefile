.PHONY: help clean format setup test zip

PYTHON_VERSION ?= $(shell cat .python-version | cut -d '.' -f 1,2)
PACKAGE_DIR ?= .venv/lib/python$(PYTHON_VERSION)/site-packages
DEPLOYMENT_ZIP ?= deployment.zip

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

setup:	## Setup
	uv sync

format:	## Format code
	uv run ruff format --preview
	uv run pyright

$(DEPLOYMENT_ZIP): $(PACKAGE_DIR) lambda_function.py format
	rm -f $(DEPLOYMENT_ZIP)
	cd $(PACKAGE_DIR) && zip -r ../../../../$(DEPLOYMENT_ZIP) * -x "*/__pycache__/*" -x "./__pycache__/*"
	zip $(DEPLOYMENT_ZIP) lambda_function.py

test:
	uv run pytest -v

zip: deployment.zip	## Build deployment zip file

aws-deploy: zip ## Deploy on AWS
	@aws lambda update-function-code --no-cli-pager --function-name clean_torbox --zip-file fileb://deployment.zip

aws-logs: ## Get AWS logs
	@aws logs tail /aws/lambda/clean_torbox --since 10m

aws-run: ## Run on AWS
	@aws lambda invoke --function-name clean_torbox -

clean: ## Clean-up
	rm -f $(DEPLOYMENT_ZIP)

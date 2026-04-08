.PHONY: help clean format setup test zip

PYTHON_VERSION ?= $(shell cat .python-version | cut -d '.' -f 1,2)
DEPLOYMENT_ZIP ?= deployment.zip
DIST_DIR := dist

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

setup:	## Setup
	uv sync --extra test --extra dev

format:	## Format code
	uv run ruff format --preview
	uv run pyright

$(DIST_DIR):
	mkdir -p $(DIST_DIR)

$(DEPLOYMENT_ZIP): $(DIST_DIR) lambda_function.py format
	rm -f $(DEPLOYMENT_ZIP)
	# Install production dependencies only by installing the current package without extras
	uv pip install --target $(DIST_DIR) .
	# Copy the lambda function itself
	cp lambda_function.py $(DIST_DIR)/
	# Zip
	cd $(DIST_DIR) && zip -r ../$(DEPLOYMENT_ZIP) . -x "*/__pycache__/*" -x "./__pycache__/*"

test:	## Run tests
	uv run pytest -v

coverage:	## Run tests with coverage
	uv run pytest --cov=lambda_function --cov-report=term-missing tests/

zip: $(DEPLOYMENT_ZIP)	## Build deployment zip file

aws-deploy: zip ## Deploy on AWS
	@aws lambda update-function-code --no-cli-pager --function-name clean_torbox --zip-file fileb://deployment.zip

aws-logs: ## Get AWS logs
	@aws logs tail /aws/lambda/clean_torbox --since 10m

aws-run: ## Run on AWS
	@aws lambda invoke --function-name clean_torbox -

clean: ## Clean-up
	rm -rf $(DEPLOYMENT_ZIP) $(DIST_DIR)

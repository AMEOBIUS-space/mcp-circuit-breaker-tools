.PHONY: test run manifest
run:
	python -m src.server --stdio
manifest:
	python -m src.server --manifest
test:
	python -m pytest tests/ -v

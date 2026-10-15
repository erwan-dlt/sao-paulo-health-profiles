PYTHON ?= python

.PHONY: fetch run verify test
fetch:
	$(PYTHON) run.py fetch
run:
	$(PYTHON) run.py run
verify:
	$(PYTHON) run.py verify
test:
	$(PYTHON) -m unittest discover -s tests -v

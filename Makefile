.PHONY: install run test

install:
	python -m pip install -e .

run:
	python main.py

test:
	python -m unittest discover -s tests -v

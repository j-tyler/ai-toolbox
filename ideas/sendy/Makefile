.PHONY: sendy test coverage
sendy:
	./tools/ensure-sendy

test:
	go test -race ./...
	python3 tests/interface.py

coverage:
	./tests/coverage.sh

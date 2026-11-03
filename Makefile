GOOSE ?= .toolchain/goose/build/goose
BENCH_ITERATIONS ?= 100000

.PHONY: setup format check test bench
setup:
	./scripts/setup-goose.sh
format:
	$(GOOSE) format logger.goose examples tests bench
check:
	$(GOOSE) format --check logger.goose examples tests bench
	$(GOOSE) check tests/logger.goose
	$(GOOSE) check examples/hello.goose
	$(GOOSE) check bench/bench.goose
test:
	$(GOOSE) run tests/logger.goose
	mkdir -p .build
	$(GOOSE) build tests/logger.goose -o .build/logger
	./.build/logger
	$(GOOSE) build tests/logger.goose --debug --no-bce -o .build/logger-debug
	./.build/logger-debug
	$(GOOSE) run examples/hello.goose
	python3 tests/ownership.py $(GOOSE)
bench:
	mkdir -p .build
	$(GOOSE) build bench/bench.goose --cc gcc -O2 -o .build/bench
	./.build/bench $(BENCH_ITERATIONS)

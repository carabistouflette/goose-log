GOOSE ?= .toolchain/goose/build/goose
BENCH_ITERATIONS ?= 100000

# Goose keys generated C by source path, so concurrent goals can overwrite it.
.NOTPARALLEL:

.PHONY: setup format check test test-sanitize test-guarded bench
setup:
	./scripts/setup-goose.sh
format:
	$(GOOSE) format logger.goose examples tests bench
check:
	$(GOOSE) format --check logger.goose examples tests bench
	$(GOOSE) check tests/logger.goose
	$(GOOSE) check tests/overloads.goose
	$(GOOSE) check tests/differential.goose
	$(GOOSE) check tests/guarded.goose
	$(GOOSE) check examples/hello.goose
	$(GOOSE) check bench/bench.goose
test:
	$(GOOSE) run tests/logger.goose
	$(GOOSE) run tests/overloads.goose
	mkdir -p .build
	$(GOOSE) build tests/logger.goose -o .build/logger
	./.build/logger
	$(GOOSE) build tests/logger.goose --debug --no-bce -o .build/logger-debug
	./.build/logger-debug
	$(GOOSE) run examples/hello.goose
	python3 tests/ownership.py $(GOOSE)
	$(GOOSE) build tests/differential.goose -o .build/differential
	$(GOOSE) build tests/differential.goose --debug --no-bce -o .build/differential-debug
	python3 tests/differential.py .build/differential .build/differential-debug
test-sanitize:
	mkdir -p .build
	$(GOOSE) build tests/differential.goose --debug --no-bce --standalone --cc ./scripts/sanitizer-cc.sh -o .build/differential-sanitized
	$(GOOSE) build tests/differential.goose -O2 --standalone --cc ./scripts/sanitizer-cc.sh -o .build/differential-sanitized-release
	python3 tests/differential.py .build/differential-sanitized .build/differential-sanitized-release
test-guarded:
	mkdir -p .build
	$(GOOSE) build tests/guarded.goose -O2 -o .build/guarded
	$(GOOSE) build tests/guarded.goose --debug --no-bce -o .build/guarded-debug
	python3 tests/guarded.py .build/guarded .build/guarded-debug
bench:
	mkdir -p .build
	$(GOOSE) build bench/bench.goose --cc gcc -O2 -o .build/bench
	./.build/bench $(BENCH_ITERATIONS)

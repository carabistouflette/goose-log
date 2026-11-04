GOOSE ?= .toolchain/goose/build/goose
BENCH_ITERATIONS ?= 100000

# Goose keys generated C by source path, so concurrent goals can overwrite it.
.NOTPARALLEL:

.PHONY: setup format check check-core test test-core test-sanitize test-guarded test-cli test-cli-sanitize bench bench-compare bench-alloc
setup:
	./scripts/setup-goose.sh
format:
	$(GOOSE) format logger.goose examples tests bench
check: check-core
	$(GOOSE) format --check logger.goose examples tests bench
	$(GOOSE) check bench/alloc/probe.goose
	$(GOOSE) check bench/cli/driver.goose
	$(GOOSE) check examples/cli/consumer.goose
	$(GOOSE) check tests/cli_sink.goose
	$(GOOSE) check tests/cli_state.goose
check-core:
	$(GOOSE) format --check logger.goose tests/logger.goose tests/features.goose tests/record_oracle.goose tests/overloads.goose tests/differential.goose tests/guarded.goose examples/hello.goose examples/file.goose bench/bench.goose bench/hotpath/driver.goose
	$(GOOSE) check logger.goose
	$(GOOSE) check tests/logger.goose
	$(GOOSE) check tests/features.goose
	$(GOOSE) check tests/record_oracle.goose
	$(GOOSE) check tests/overloads.goose
	$(GOOSE) check tests/differential.goose
	$(GOOSE) check tests/guarded.goose
	$(GOOSE) check examples/hello.goose
	$(GOOSE) check examples/file.goose
	$(GOOSE) check bench/bench.goose
	$(GOOSE) check bench/hotpath/driver.goose
test: test-core
	$(MAKE) test-cli
test-core:
	$(GOOSE) run tests/logger.goose
	$(GOOSE) run tests/features.goose
	$(GOOSE) run tests/overloads.goose
	mkdir -p .build
	$(GOOSE) build tests/logger.goose -o .build/logger
	./.build/logger
	$(GOOSE) build tests/logger.goose --debug --no-bce -o .build/logger-debug
	./.build/logger-debug
	$(GOOSE) build tests/features.goose -o .build/features
	./.build/features
	$(GOOSE) build tests/features.goose --debug --no-bce -o .build/features-debug
	./.build/features-debug
	$(GOOSE) run examples/hello.goose
	$(GOOSE) build examples/file.goose -o .build/file-example
	python3 tests/file_example.py .build/file-example
	python3 tests/ownership.py $(GOOSE)
	python3 tests/setup.py
	$(GOOSE) build tests/differential.goose -o .build/differential
	$(GOOSE) build tests/differential.goose --debug --no-bce -o .build/differential-debug
	python3 tests/differential.py .build/differential .build/differential-debug
	$(GOOSE) build tests/record_oracle.goose -o .build/record-oracle
	$(GOOSE) build tests/record_oracle.goose --debug --no-bce -o .build/record-oracle-debug
	python3 tests/records.py .build/record-oracle .build/record-oracle-debug
test-cli:
	mkdir -p .build
	$(GOOSE) build examples/cli/consumer.goose -o .build/cli-consumer
	$(GOOSE) build tests/cli_sink.goose -o .build/cli-sink
	$(GOOSE) build tests/cli_state.goose -o .build/cli-state
	python3 tests/cli_consumer.py .build/cli-consumer .build/cli-sink .build/cli-state
test-cli-sanitize:
	mkdir -p .build
	$(GOOSE) build examples/cli/consumer.goose --debug --no-bce --standalone --cc ./scripts/sanitizer-cc.sh -o .build/cli-consumer-sanitized
	$(GOOSE) build tests/cli_sink.goose --debug --no-bce --standalone --cc ./scripts/sanitizer-cc.sh -o .build/cli-sink-sanitized
	$(GOOSE) build tests/cli_state.goose --debug --no-bce --standalone --cc ./scripts/sanitizer-cc.sh -o .build/cli-state-sanitized
	python3 tests/cli_consumer.py .build/cli-consumer-sanitized .build/cli-sink-sanitized .build/cli-state-sanitized
test-sanitize:
	mkdir -p .build
	$(GOOSE) build tests/differential.goose --debug --no-bce --standalone --cc ./scripts/sanitizer-cc.sh -o .build/differential-sanitized
	$(GOOSE) build tests/differential.goose -O2 --standalone --cc ./scripts/sanitizer-cc.sh -o .build/differential-sanitized-release
	python3 tests/differential.py .build/differential-sanitized .build/differential-sanitized-release
	$(GOOSE) build tests/features.goose --debug --no-bce --standalone --cc ./scripts/sanitizer-cc.sh -o .build/features-sanitized
	./.build/features-sanitized
	$(GOOSE) build tests/record_oracle.goose -O2 --standalone --cc ./scripts/sanitizer-cc.sh -o .build/record-oracle-sanitized
	python3 tests/records.py .build/record-oracle-sanitized
test-guarded:
	mkdir -p .build
	$(GOOSE) build tests/guarded.goose -O2 -o .build/guarded
	$(GOOSE) build tests/guarded.goose --debug --no-bce -o .build/guarded-debug
	python3 tests/guarded.py .build/guarded .build/guarded-debug
bench:
	mkdir -p .build
	$(GOOSE) build bench/bench.goose --cc gcc -O2 -o .build/bench
	./.build/bench $(BENCH_ITERATIONS)
bench-compare:
	python3 bench/compare/run.py --goose $(GOOSE) --iterations $(BENCH_ITERATIONS)
bench-alloc:
	python3 bench/alloc/run.py --goose $(GOOSE)

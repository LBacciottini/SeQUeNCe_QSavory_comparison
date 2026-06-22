# Validate Agreement

## Run the fast Python suite

```bash
cd python
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
```

## Run the full Python suite with SeQUeNCe

```bash
cd python
PYTHONPATH=src conda run -n sequenceEnv python -m unittest discover -s tests -p 'test_*.py'
```

## Run the Julia suite

```bash
JULIA_PKG_SERVER_REGISTRY_PREFERENCE=eager \
julia --project=julia/SeQUeNCeQSavoryComparison -e 'using Pkg; Pkg.test()'
```

## Run optional elementary-link statistical validation

```bash
RUN_SLOW_SIM_TESTS=1 conda run -n sequenceEnv python -m unittest tests.test_sequence_elementary_slow
RUN_SLOW_SIM_TESTS=1 julia --project=julia/SeQUeNCeQSavoryComparison -e 'using Pkg; Pkg.test()'
```

The optional elementary-link tests accept:

- `ELEMENTARY_TEST_TRIALS`
- `ELEMENTARY_TEST_TIMEOUT_S`

Use these only when you need tighter statistical confidence or a longer timeout
for a low-rate configuration.

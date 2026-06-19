# Running

Run the Python unit tests:

```bash
cd python
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
```

Run the full Python suite, including the SeQUeNCe integration smoke test:

```bash
cd python
PYTHONPATH=src conda run -n sequenceEnv python -m unittest discover -s tests -p 'test_*.py'
```

Run SeQUeNCe:

```bash
conda run -n sequenceEnv python scripts/run_sequence.py --config shared/configs/default.toml --seed 1 --output outputs/sequence_seed1
```

Run QuantumSavory:

```bash
julia --project=julia/SeQUeNCeQSavoryComparison -e 'using Pkg; Pkg.develop(path=".agents/codebases/QuantumSavory.jl"); Pkg.instantiate()'
julia --project=julia/SeQUeNCeQSavoryComparison scripts/run_qsavory.jl --config shared/configs/default.toml --seed 1 --raw-state-model exact --output outputs/qsavory_exact_seed1
julia --project=julia/SeQUeNCeQSavoryComparison scripts/run_qsavory.jl --config shared/configs/default.toml --seed 1 --raw-state-model werner --output outputs/qsavory_werner_seed1
```

Run a small batch. Requesting `qsavory` runs both `qsavory_exact` and
`qsavory_werner`, so the comparison has three series: `sequence`,
`qsavory_exact`, and `qsavory_werner`.

```bash
python3 scripts/run_batch.py --config shared/configs/default.toml --seeds 1:3 --output outputs/batch
python3 scripts/plot_compare.py --input outputs/batch --output outputs/batch/comparison.csv
```

`plot_compare.py` also writes `completion_time_by_seed.png` and
`average_fidelity_by_seed.png` next to the comparison CSV by default.

Run optional elementary-link statistical validations:

```bash
RUN_SLOW_SIM_TESTS=1 conda run -n sequenceEnv python -m unittest tests.test_sequence_elementary_slow
RUN_SLOW_SIM_TESTS=1 julia --project=julia/SeQUeNCeQSavoryComparison -e 'using Pkg; Pkg.test()'
```

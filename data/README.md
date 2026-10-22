# data/

Generated synthetic data (JSON). Everything in this folder except this README is gitignored.
`scripts/bootstrap.sh` creates it; to recreate it by hand:

```
python3 scripts/generate_data.py          # tools, employees, contracts, budgets, accounts, usage, planted issues
.venv/bin/python scripts/load_data.py     # loads tools, employees, contracts and budgets into Postgres
.venv/bin/python scripts/make_contract_pdfs.py data/sample-contracts
```

The dates are relative to the day you generate the data (for example the contracts that hit their 90, 60 and 30 day notice marks today),
so the contract PDFs must be generated from the same data. `planted_issues.json` lists the problems hidden in the data;
`scripts/check_audit.py` compares them with what workflow A found.

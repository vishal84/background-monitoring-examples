# background-monitoring-examples

## Run the example

1) Install dependencies:

- Run `uv sync`

2) Configure environment variables:

- Open [.env.example](.env.example) and update the values for your setup.
- Rename the file to .env in the repository root.

3) Run the example:

- `uv run python app/monitoring_example.py`

### Notes

- The example loads environment variables from the repository root .env file.
- You can override the model with `GEMINI_MODEL` in your .env (defaults to `gemini-2.5-flash`).

# Capabilities Probe

Utility for checking which Lemonade endpoints and host commands are available on the current installation.

Probe output is machine-specific and may include installed model names, process command lines, Lemonade paths, memory totals, OS details, and service logs. Generated results are ignored by git.

## Usage

```bash
cd capabilities
pip install -r requirements.txt

python probe.py

# With an admin key, to test protected /internal/* endpoints:
python probe.py --admin-key YOUR_ADMIN_KEY

# Or:
export LEMONADE_ADMIN_API_KEY=YOUR_KEY
python probe.py

# Custom Lemonade URL:
python probe.py --lemonade-url http://192.168.1.100:13305
```

## Output

- `results/*.json` — raw endpoint responses
- `results/probe_summary.json` — full summary
- `CAPABILITIES.md` — generated Markdown report

These files are local artifacts and are intentionally ignored by git.

For a sanitized example, see [`CAPABILITIES.example.md`](CAPABILITIES.example.md).

## When to Re-run

- after upgrading Lemonade
- after configuring or removing `LEMONADE_ADMIN_API_KEY`
- after changing server configuration
- on a new installation

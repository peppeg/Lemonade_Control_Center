# Capabilities Probe

Script per testare quali endpoint e comandi sono disponibili
sull'installazione Lemonade corrente.

## Uso

```bash
# Setup
cd capabilities
pip install -r requirements.txt  # oppure: pip install httpx websockets

# Probe base
python probe.py

# Con admin key (per testare /internal/* endpoints)
python probe.py --admin-key YOUR_ADMIN_KEY
# oppure:
export LEMONADE_ADMIN_API_KEY=YOUR_KEY
python probe.py

# URL custom
python probe.py --lemonade-url http://192.168.1.100:13305
```

## Output

- `results/*.json` — response reali di ogni endpoint
- `results/probe_summary.json` — riepilogo completo
- `CAPABILITIES.md` — documento leggibile con tabelle

## Quando rieseguire

- Dopo un aggiornamento di Lemonade
- Dopo aver configurato/rimosso LEMONADE_ADMIN_API_KEY
- Dopo aver cambiato la configurazione del server
- Su una nuova installazione

# misp_dockerized_testing
Test MISP instances using a dockerized infrastructure

# Usage

```bash
poetry install

./setup_nginx.py
./start_nginx.py
./init_misps.py
# Get the list printed at the end, add it in your /etc/hosts file
nosetests-3.4 testlive_sync.py
```

# Notes

`./stop_*` stops thigns
`./refresh_misps.py` cleans up the MISPs instances

# misp_dockerized_testing
Test MISP instances using a dockerized infrastructure

# What does what

* `start_dockers.py`: Configure and launch the `docker-compose.yml` files
* `start_dockers.py`: Guess.
* `refresh_dockers.py`: Run the refresh script on all the MISP instances
* `run_tests.sh`: Run the test suite (if that fails, you want to run `refresh_dockers.py`)

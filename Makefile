run:
	python3 -m app.main

start:
	bash start.sh

init:
	python3 scripts/init_db.py
	mkdir -p uploads temp_storage

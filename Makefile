run-server:
	ALLOW_ORIGINS=* ALLOW_METHODS=* ALLOW_HEADERS=* fastapi run --workers 4 api-server.py

run-redis:
	docker run -d -p 6379:6379 --name face-swap-redis redis 

run-workers:
	celery -A roop.swap_worker worker --loglevel=info
#!/bin/sh
# Entrypoint wrapper — всегда запускает uvicorn c PORT из env,
# независимо от того что Railway отдаёт как CMD/startCommand.
# Railway service-level startCommand пишет "--port $PORT" в exec-form
# (shell expansion не работает) — мы игнорируем их $@ и формируем
# команду сами.
set -e
PORT="${PORT:-8000}"
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT}"

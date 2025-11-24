default:
  just --list

run *args:
  uvicorn src.main:app --reload {{args}}

mm *args:
  alembic revision --autogenerate -m "{{args}}"

migrate:
  alembic upgrade head

downgrade *args:
  alembic downgrade {{args}}

ruff *args:
  ruff check {{args}} src

lint:
  ruff format src
  just ruff --fix

# docker
up:
  docker-compose up -d

kill *args:
  docker-compose kill {{args}}

build:
  docker-compose build

ps:
  docker-compose ps

pre-commit:
  git add .
  pre-commit run --all-files

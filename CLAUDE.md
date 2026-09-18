# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Rate Limiter service.

## Stack

- Python 3.x
- FastAPI
- Redis (via Docker)
- pytest

## Commands

- Run the app: `uvicorn src.main:app --reload`
- Run tests: `pytest`
- Run a single test file: `pytest tests/path/to/test_file.py`
- Run a single test: `pytest tests/path/to/test_file.py::test_name`

## Conventions

- Type hints on all functions
- Tests live in `tests/`, mirroring the `src/` structure

## Workflow

- Never commit directly to `main`. Branch per feature.
- Keep changes small enough to review in one sitting.
- Explain the reasoning behind non-obvious decisions in commit messages.

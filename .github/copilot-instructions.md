# Project Guidelines

## Code Style
Python with type hints using `typing` module. Uses SQLAlchemy 2.0 declarative style with `so.mapped_column` for model definitions, as seen in [app/models.py](app/models.py). Comments and UI strings in Russian. Imports organized with standard library first, then third-party, then local modules.

## Architecture
Flask web application with SQLAlchemy ORM for data persistence, using SQLite by default. User authentication via Flask-Login with password hashing. Multi-step route creation workflow: info form, stops form, prices matrix, with JSON storage for complex data. Templates extend [templates/base.html](templates/base.html) with Jinja2. App factory pattern in [app/__init__.py](app/__init__.py) for testability. Exports route data to CP866-encoded format via [app/utils.py](app/utils.py).

## Build and Test
Install dependencies with `poetry install`. Run tests with `pytest`. Lint with `ruff check`. Database migrations with `flask db upgrade` after `flask db migrate`. App runs via `flask run` or `python transportapp.py`.

## Project Conventions
Forms use WTForms with custom validators, e.g., regex for transport codes in [app/forms.py](app/forms.py#L45). Global constants defined in [app/constants.py](app/constants.py) injected via context processor. JSON fields for flexible data like `stops` and `price_matrix` in Route model. User profiles editable with form pre-population using `obj=current_user`.

## Integration Points
Flask extensions: SQLAlchemy for ORM, Flask-Migrate for schema changes, Flask-Login for sessions, Flask-WTF for CSRF protection. No external APIs; data export to file buffers.

## Security
User authentication required for all routes except login/register, enforced with `@login_required`. Passwords hashed with Werkzeug. CSRF enabled on forms via Flask-WTF. User profile access restricted to self via username check in [app/routes.py](app/routes.py#L75).
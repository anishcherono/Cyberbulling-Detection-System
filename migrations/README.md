# Database migrations

The application runs pending MySQL migrations during startup, before creating the
default administrator. Applied versions are recorded in `schema_migrations`.
Migrations are serialized with a MySQL advisory lock so simultaneous app workers
do not apply the same version at once.

To change the schema, add a new module under `migrations/versions/` with an
`upgrade()` function, then append its increasing version number, description,
and function to `MIGRATIONS` in `migrations/__init__.py`. Do not edit a migration
that may already have been applied; add another migration instead.

If an upgrade fails, startup reports the underlying database error and the
version is not recorded as applied. MySQL schema changes may partially persist
because DDL is not generally transactional, so make each migration safe to
rerun before deploying it.

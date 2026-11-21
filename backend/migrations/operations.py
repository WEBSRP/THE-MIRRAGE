"""Operations for the immutable initial revisions; future changes get new revisions."""
from alembic import op
import sqlalchemy as sa

from backend.migrations.schema_20261120 import REVISION_TABLES, schema_at


def create_revision(revision):
    for table in schema_at(revision).sorted_tables:
        if table.name in REVISION_TABLES[revision]:
            table.create(op.get_bind(), checkfirst=False)


def drop_empty_revision(revision):
    if op.get_context().as_sql:
        raise RuntimeError("Offline downgrade is disabled: table contents must be checked")
    metadata = schema_at(revision)
    tables = [table for table in reversed(metadata.sorted_tables) if table.name in REVISION_TABLES[revision]]
    if op.get_bind().dialect.name == "postgresql":
        quote = op.get_bind().dialect.identifier_preparer.quote
        op.get_bind().execute(sa.text("LOCK TABLE " + ", ".join(quote(table.name) for table in tables)
                                      + " IN ACCESS EXCLUSIVE MODE"))
    elif tables:
        # Start/hold SQLite's writer transaction before testing emptiness. A
        # concurrent insert must not slip between the check and a DROP TABLE.
        column = next(iter(tables[0].columns))
        op.get_bind().execute(tables[0].update().where(sa.false()).values({column.name: column}))
    # Check every target before any destructive statement. In particular, never
    # discard revocation tombstones, reservations, solves or quotas on rollback.
    if any(op.get_bind().execute(sa.select(sa.literal(1)).select_from(table).limit(1)).first()
           for table in tables):
        raise RuntimeError("Downgrade would discard data; retain the schema or restore a verified backup")
    for table in tables:
        table.drop(op.get_bind(), checkfirst=False)
    if op.get_bind().dialect.name == "postgresql":
        for table in tables:
            for column in table.columns:
                if isinstance(column.type, sa.Enum):
                    column.type.drop(op.get_bind(), checkfirst=True)

from alembic import context

from app.database import make_engine
from app.models import metadata

engine = make_engine(context.config.attributes.get("database_url"))
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=metadata, transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()

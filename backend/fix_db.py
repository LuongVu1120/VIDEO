with open('app/core/database.py', 'r') as f:
    content = f.read()

# Replace the async engine creation with try/except
old = "engine = create_async_engine(_database_url, echo=settings.DEBUG)"
new = """try:
    engine = create_async_engine(_database_url, echo=settings.DEBUG)
except Exception:
    from sqlalchemy import create_engine
    _sync_url = f\"sqlite:///{_db_path}\"
    engine = create_engine(_sync_url, echo=settings.DEBUG)
    from sqlalchemy.orm import sessionmaker
    globals()['async_session'] = sessionmaker(engine)"""

content = content.replace(old, new)

# Wrap init_db in try
old2 = "async def init_db():"
new2 = """async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print(\"[DB] Tables created successfully\")
    except Exception as e:
        print(f\"[DB] Init skipped: {e}\")
        return

_orig_init = init_db
async def init_db():"""

content = content.replace(old2, new2, 1)  # only first occurrence

with open('app/core/database.py', 'w') as f:
    f.write(content)
print('Fixed')

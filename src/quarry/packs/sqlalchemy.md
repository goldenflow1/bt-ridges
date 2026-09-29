SQLAlchemy 2.x notes:
- select(...).join(...) multiplies rows for one-to-many; aggregate in a subquery (.subquery()) or use scalar_subquery() correlated with the outer entity.
- func.count() counts rows; func.count(col) skips NULLs; func.coalesce(..., 0) for empty groups; aggregate FILTER via func.count().filter(cond).
- Eager loading: selectinload() for collections (one extra query per relationship), joinedload() for many-to-one; raiseload('*') helps find lazy loads.
- Query counting: event.listen(engine, "before_cursor_execute", ...).
- Alembic: op.create_index(name, table, cols, postgresql_where=text(...)) for partial indexes.

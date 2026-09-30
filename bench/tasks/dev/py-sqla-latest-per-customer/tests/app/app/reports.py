from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    and_,
    func,
    select,
)

metadata = MetaData()
events = Table('events', metadata, Column('id', Integer, primary_key=True), Column('customer_id', Integer),
               Column('occurred_at', DateTime(timezone=True)), Column('status', String))


def latest_per_customer(conn, since, until):
    """Return (customer_id, event_id, occurred_at) for each latest event in [since, until)."""
    newest = select(events.c.customer_id, func.max(events.c.occurred_at).label('ts')).where(
        events.c.occurred_at >= since, events.c.occurred_at < until).group_by(events.c.customer_id).subquery()
    query = select(events.c.customer_id, events.c.id, events.c.occurred_at).join(
        newest, and_(events.c.customer_id == newest.c.customer_id, events.c.occurred_at == newest.c.ts))
    return list(conn.execute(query.order_by(events.c.customer_id)))

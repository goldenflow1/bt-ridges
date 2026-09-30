from sqlalchemy import select
from freight.models import scan


def timeline(connection, parcel_id):
    query = select(scan).where(scan.c.parcel_id == parcel_id).order_by(scan.c.recorded_at, scan.c.id)
    return [dict(row) for row in connection.execute(query).mappings()]

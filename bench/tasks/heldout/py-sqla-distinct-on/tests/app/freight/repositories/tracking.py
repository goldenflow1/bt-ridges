from sqlalchemy import and_, func, select

from freight.models import parcel, scan


def current_scans(connection, carrier_id):
    """Return one current scan for every parcel belonging to a carrier."""
    latest = (select(scan.c.parcel_id, scan.c.id.label("scan_id"), scan.c.recorded_at,
                     scan.c.depot, scan.c.condition)
              .join(parcel, parcel.c.id == scan.c.parcel_id)
              .where(parcel.c.carrier_id == carrier_id)
              .distinct(scan.c.parcel_id)
              .order_by(scan.c.parcel_id, scan.c.id.desc()))
    return [dict(row) for row in connection.execute(latest).mappings()]


def scan_volume(connection, carrier_id):
    """Existing operations summary; zero is meaningful."""
    query = select(func.count(scan.c.id)).select_from(scan.join(parcel)).where(
        and_(parcel.c.carrier_id == carrier_id, scan.c.condition != "cancelled"))
    return connection.scalar(query)

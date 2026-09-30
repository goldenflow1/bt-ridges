from freight.presentation import serialize_scan
from freight.service import carrier_dashboard


def dashboard(connection, carrier_id):
    report = carrier_dashboard(connection, carrier_id)
    return {**report, 'current': [serialize_scan(row) for row in report['current']]}

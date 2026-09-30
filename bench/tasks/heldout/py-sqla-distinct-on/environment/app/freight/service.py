from freight.repositories.tracking import current_scans, scan_volume


def carrier_dashboard(connection, carrier_id):
    return {'current': current_scans(connection, carrier_id), 'scan_volume': scan_volume(connection, carrier_id)}

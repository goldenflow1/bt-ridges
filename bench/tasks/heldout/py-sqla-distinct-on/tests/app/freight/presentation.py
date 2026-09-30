def serialize_scan(row):
    return {**row, 'recorded_at': row['recorded_at'].isoformat()}

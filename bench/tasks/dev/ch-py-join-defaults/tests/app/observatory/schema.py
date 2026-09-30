TABLES = ['events', 'devices']


def create_schema(client):
    client.command('CREATE TABLE IF NOT EXISTS events (tenant String, event_id UInt64, device String) ENGINE=MergeTree ORDER BY (tenant,event_id)')
    client.command('CREATE TABLE IF NOT EXISTS devices (tenant String, device String, device_id UInt64, label String, enabled UInt8) ENGINE=MergeTree ORDER BY (tenant,device)')

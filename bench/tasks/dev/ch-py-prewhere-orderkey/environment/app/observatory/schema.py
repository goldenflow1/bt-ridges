TABLES = ['events']


def create_schema(client):
    client.command("CREATE TABLE IF NOT EXISTS events (tenant_id UInt32, happened DateTime('UTC'), event_id UInt64, status LowCardinality(String), amount Int64) ENGINE=MergeTree ORDER BY (tenant_id,happened,event_id) SETTINGS index_granularity=1024")

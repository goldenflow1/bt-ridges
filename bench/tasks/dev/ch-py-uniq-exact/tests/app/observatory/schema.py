TABLES = ['visits']


def create_schema(client):
    client.command("CREATE TABLE IF NOT EXISTS visits (tenant String, visitor Nullable(UInt64), happened DateTime('UTC')) ENGINE=MergeTree ORDER BY (tenant, happened)")

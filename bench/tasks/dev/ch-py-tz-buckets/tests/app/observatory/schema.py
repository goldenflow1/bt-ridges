TABLES = ['events']


def create_schema(client):
    client.command("CREATE TABLE IF NOT EXISTS events (tenant String, happened DateTime64(3, 'UTC')) ENGINE=MergeTree ORDER BY (tenant,happened)")

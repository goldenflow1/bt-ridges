TABLES = ['meter_events']


def create_schema(client):
    client.command("""CREATE TABLE IF NOT EXISTS meter_events (
        utility String, meter_id String, observed_at DateTime64(6,'UTC'), version UInt32,
        state String, region String, reading Int64
    ) ENGINE=MergeTree ORDER BY (utility,meter_id,observed_at,version)""")

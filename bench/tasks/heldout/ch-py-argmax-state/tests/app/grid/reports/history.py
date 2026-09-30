def received_event_count(client, utility):
    return client.query('SELECT count() AS n FROM meter_events WHERE utility = {utility:String}',
                        {'utility':utility})[0]['n']

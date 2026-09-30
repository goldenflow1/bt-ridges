from grid.reports.current import online_query


def regional_panel(client, utility, region):
    return client.query(online_query(), {'utility':utility, 'region':region})

from grid.services.operations import connection_panel


def get_connections(client, utility, region):
    if not isinstance(utility,str) or not isinstance(region,str):
        raise TypeError('utility and region must be strings')
    return connection_panel(client,utility,region)

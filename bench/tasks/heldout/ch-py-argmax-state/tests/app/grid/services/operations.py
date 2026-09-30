from grid.reports.panel import regional_panel


def connection_panel(client, utility, region):
    return {'meters':regional_panel(client,utility,region)}

# Grid Dispatch

Regional operators use the connection panel to see which electricity meters are online in their region. The importer accepts late events and revision corrections, so ingestion order is not the current-state order. A meter may move region without changing its ID.

Requests enter `grid/api.py`, pass through the operations service and the reporting package, then reach ClickHouse. The reporting package also supplies a history summary used elsewhere. The HTTP transport and schema management live outside that package.

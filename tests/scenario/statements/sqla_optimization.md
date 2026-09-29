# Optimize the invoice list

Listing invoices issues one query for the customer of every invoice, so the
number of SQL statements grows with the number of invoices. Make the listing
use a bounded number of queries independent of how many invoices are shown.

Limit production changes to `billing/repository.py`, specifically
`InvoiceRepository.list_invoices()`. Keep its signature and the rest of the file
unchanged, including imports; use only names the file already imports.

Do not materialize invoices in Python before filtering. Do not change models
or tests.

```bash
pytest tests/test_invoices.py
```

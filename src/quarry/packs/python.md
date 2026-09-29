Python data-access notes:
- Run throw-away checks as scripts in the scratch directory that import the application (put the repository on sys.path and load its settings/config). Never add files to the repository for this.
- Count queries at the driver level (a cursor wrapper or the ORM's query-capture hook) rather than relying on database-side logging.

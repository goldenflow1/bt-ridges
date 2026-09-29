Django ORM notes:
- Correlated aggregates: Subquery(Model.objects.filter(fk=OuterRef("pk")).values("fk").annotate(c=Count("pk")).values("c")) with Coalesce(..., 0) avoids join fan-out; output_field must match (IntegerField for counts).
- annotate() over several multi-valued relations multiplies rows; use separate subqueries or Count(..., distinct=True) only when distinctness is the requirement.
- values() before annotate() groups by those values; order_by() fields also join the GROUP BY.
- Never hard-code compiler table aliases in RawSQL/extra(); outer references in RawSQL break when the queryset is filtered or joined.
- Integer arithmetic in expressions stays integer; use Cast(..., FloatField()/DecimalField()) or ExpressionWrapper with an explicit output_field before dividing, then Round.
- N+1: select_related for forward FK/one-to-one, prefetch_related for reverse/many-to-many; Prefetch(queryset=...) to filter.
- Tests: `python manage.py test <label> --keepdb --noinput` reuses the test database. Query counts: django.test.utils.CaptureQueriesContext(connection) or connection.execute_wrapper.
- Migrations: indexes via migrations.AddIndex/models.Index(fields=..., condition=Q(...), name=...); AddIndexConcurrently needs atomic = False.

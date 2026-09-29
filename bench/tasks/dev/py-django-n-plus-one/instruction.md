# Bound the recipe list queries

The recipe list endpoint `GET /api/recipes/` gets slower as pages fill up.
With query logging on, one request for a full page of 20 recipes issues
more than 80 SQL statements, and the count grows with every recipe on the
page. The recipe page `GET /api/recipes/<slug>/` shares the same summary
fields.

Work in `/app`. Find where the per-recipe queries come from and fix them.
Limit production changes to the existing modules `recipes/views.py`,
`recipes/serializers.py`, and `recipes/models.py`; do not add, remove, or
rename files.

After the change:

- a list request uses a fixed number of queries (at most six), whatever the
  number of recipes on the page, including filtered (`?tag=`) and later
  (`?page=`) pages;
- the JSON of both endpoints stays exactly the same: the same keys, the
  same values, the same ordering of results and of each recipe's `tags`
  (sorted by slug), and the same `rating` rounding as
  `Recipe.rating_summary()`;
- `ingredient_count` and `rating.count` stay exact for recipes that have
  several ingredients, several reviews, and several tags at once.

Keep the work in the ORM and PostgreSQL. Do not use raw SQL, `.extra()`,
caching, or Python-side re-querying per recipe. Do not change model fields,
indexes, constraints, or migrations, URLs, settings, the seed command, or
tests. Do not add database writes, process, filesystem, or network side
effects.

Run these checks before finishing:

```bash
python manage.py test recipes --keepdb --noinput
ruff check --no-cache recipes/
```

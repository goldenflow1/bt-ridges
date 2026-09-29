from datetime import UTC, datetime, timedelta
from itertools import count

from recipes.models import Author, Ingredient, Recipe, Review, Tag

_seq = count(1)
BASE_TIME = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)


def author(handle=None, name=None):
    n = next(_seq)
    handle = handle or f"cook-{n}"
    return Author.objects.create(handle=handle, name=name or handle.replace("-", " ").title())


def tag(slug, name=None):
    return Tag.objects.get_or_create(slug=slug, defaults={"name": name or slug.title()})[0]


def recipe(
    title,
    *,
    by=None,
    tags=(),
    ingredients=(),
    ratings=(),
    published=True,
    minutes_ago=0,
    servings=2,
):
    n = next(_seq)
    item = Recipe.objects.create(
        slug=f"{title.lower().replace(' ', '-')}-{n}",
        title=title,
        author=by or author(),
        servings=servings,
        published=published,
        created_at=BASE_TIME - timedelta(minutes=minutes_ago),
    )
    item.tags.set(tags)
    for position, name in enumerate(ingredients, start=1):
        Ingredient.objects.create(recipe=item, position=position, name=name, quantity="1")
    for i, rating in enumerate(ratings):
        Review.objects.create(
            recipe=item,
            reviewer=f"reader-{i}",
            rating=rating,
            body="",
            created_at=BASE_TIME + timedelta(hours=i),
        )
    return item

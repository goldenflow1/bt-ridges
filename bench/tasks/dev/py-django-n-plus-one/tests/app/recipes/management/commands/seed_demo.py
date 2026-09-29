from datetime import UTC, datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from recipes.models import Author, Ingredient, Recipe, Review, Tag

AUTHORS = [("ada-quinn", "Ada Quinn"), ("bo-lindqvist", "Bo Lindqvist"), ("chidi-eze", "Chidi Eze")]
TAGS = [
    ("vegetarian", "Vegetarian"),
    ("weeknight", "Quick weeknight"),
    ("soup", "Soups"),
    ("baking", "Baking"),
    ("spicy", "Spicy"),
]
RECIPES = [
    (
        "Leek and Potato Soup",
        0,
        ["vegetarian", "soup"],
        ["leeks", "potatoes", "stock", "butter"],
        [5],
    ),
    (
        "Weeknight Dal",
        2,
        ["vegetarian", "weeknight", "spicy"],
        ["red lentils", "onion", "garlic"],
        [],
    ),
    ("Rye Flatbread", 1, ["baking"], ["rye flour"], [4, 5]),
    ("Chilli Noodles", 2, ["weeknight", "spicy"], ["noodles"], [5, 3, 4]),
    ("Seeded Loaf", 1, ["baking", "vegetarian"], ["flour", "seeds", "yeast", "salt", "water"], []),
    ("Tomato Rasam", 2, ["soup", "spicy"], ["tomatoes", "tamarind", "pepper"], [4]),
]


class Command(BaseCommand):
    help = "Load the demo data set (idempotent: replaces existing rows)."

    @transaction.atomic
    def handle(self, *args, **options):
        Review.objects.all().delete()
        Ingredient.objects.all().delete()
        Recipe.objects.all().delete()
        Tag.objects.all().delete()
        Author.objects.all().delete()
        authors = [Author.objects.create(handle=h, name=n) for h, n in AUTHORS]
        tags = {slug: Tag.objects.create(slug=slug, name=name) for slug, name in TAGS}
        start = datetime(2026, 4, 20, 18, 0, tzinfo=UTC)
        for i, (title, who, tag_slugs, ingredients, ratings) in enumerate(RECIPES):
            recipe = Recipe.objects.create(
                slug=title.lower().replace(" ", "-"),
                title=title,
                author=authors[who],
                servings=2 + i % 3,
                published=True,
                created_at=start - timedelta(days=i),
            )
            recipe.tags.set([tags[s] for s in tag_slugs])
            for position, name in enumerate(ingredients, start=1):
                Ingredient.objects.create(recipe=recipe, position=position, name=name)
            for n, rating in enumerate(ratings):
                Review.objects.create(
                    recipe=recipe,
                    reviewer=f"reader-{n + 1}",
                    rating=rating,
                    created_at=recipe.created_at + timedelta(hours=n + 1),
                )
        Recipe.objects.create(
            slug="untested-idea",
            title="Untested Idea",
            author=authors[0],
            published=False,
            created_at=start,
        )
        self.stdout.write(f"seeded {Recipe.objects.count()} recipes")

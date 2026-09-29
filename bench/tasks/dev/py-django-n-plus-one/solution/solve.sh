#!/bin/bash
set -euo pipefail

cd /app
python - <<'PY'
from pathlib import Path


def patch(path, edits):
    target = Path(path)
    text = target.read_text()
    for anchor, replacement in edits:
        if text.count(anchor) != 1:
            raise SystemExit(f"frozen anchor changed in {path}")
        text = text.replace(anchor, replacement, 1)
    target.write_text(text)


patch(
    "recipes/views.py",
    [
        (
            "from django.core.paginator import Paginator\n",
            "from django.core.paginator import Paginator\n"
            "from django.db.models import Avg, Count, Prefetch\n",
        ),
        ("from recipes.models import Recipe\n", "from recipes.models import Recipe, Tag\n"),
        (
            "PAGE_SIZE = 20\n\n\ndef recipe_list(request):\n"
            '    recipes = Recipe.objects.filter(published=True).order_by("-created_at", "id")\n',
            "PAGE_SIZE = 20\n\n\n"
            "def published_recipes():\n"
            '    """Published recipes with everything the serializers read, in O(1) queries."""\n'
            "    return (\n"
            "        Recipe.objects.filter(published=True)\n"
            '        .select_related("author")\n'
            '        .prefetch_related(Prefetch("tags", queryset=Tag.objects.order_by("slug")))\n'
            "        .annotate(\n"
            '            ingredient_total=Count("ingredients", distinct=True),\n'
            '            review_total=Count("reviews", distinct=True),\n'
            '            review_average=Avg("reviews__rating"),\n'
            "        )\n"
            "    )\n\n\n"
            "def recipe_list(request):\n"
            '    recipes = published_recipes().order_by("-created_at", "id")\n',
        ),
        (
            "    recipe = get_object_or_404(Recipe, slug=slug, published=True)\n",
            "    recipe = get_object_or_404(published_recipes(), slug=slug)\n",
        ),
    ],
)

patch(
    "recipes/serializers.py",
    [
        (
            '"""Plain-dict serializers for the JSON API."""\n',
            '"""Plain-dict serializers for the JSON API."""\n\n'
            "from recipes.models import rating_payload\n",
        ),
        (
            '        "tags": [tag.slug for tag in recipe.tags.order_by("slug")],\n'
            '        "ingredient_count": recipe.ingredients.count(),\n'
            '        "rating": recipe.rating_summary(),\n',
            '        "tags": [tag.slug for tag in recipe.tags.all()],\n'
            '        "ingredient_count": recipe.ingredient_total,\n'
            '        "rating": rating_payload(recipe.review_average, recipe.review_total),\n',
        ),
    ],
)
PY

ruff check --no-cache recipes/

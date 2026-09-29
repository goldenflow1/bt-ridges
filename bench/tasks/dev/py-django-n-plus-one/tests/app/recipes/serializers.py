"""Plain-dict serializers for the JSON API."""


def serialize_author(author):
    return {"handle": author.handle, "name": author.name}


def serialize_recipe_summary(recipe):
    """Compact representation used by the recipe list."""
    return {
        "id": recipe.id,
        "slug": recipe.slug,
        "title": recipe.title,
        "author": serialize_author(recipe.author),
        "tags": [tag.slug for tag in recipe.tags.order_by("slug")],
        "ingredient_count": recipe.ingredients.count(),
        "rating": recipe.rating_summary(),
        "created_at": recipe.created_at.isoformat(),
    }


def serialize_recipe_detail(recipe):
    """Full representation used by the recipe page."""
    return {
        **serialize_recipe_summary(recipe),
        "servings": recipe.servings,
        "ingredients": [
            {"name": item.name, "quantity": item.quantity} for item in recipe.ingredients.all()
        ],
        "reviews": [
            {
                "reviewer": review.reviewer,
                "rating": review.rating,
                "body": review.body,
                "created_at": review.created_at.isoformat(),
            }
            for review in recipe.reviews.all()[:5]
        ],
    }

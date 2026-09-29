from django.db import models
from django.db.models import Avg, Count


def rating_payload(average, count):
    """Public representation of a recipe's ratings."""
    return {
        "average": round(float(average), 2) if average is not None else None,
        "count": count,
    }


class Author(models.Model):
    handle = models.SlugField(unique=True)
    name = models.CharField(max_length=120)

    def __str__(self):
        return self.handle


class Tag(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=60)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.slug


class Recipe(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.PROTECT, related_name="recipes")
    tags = models.ManyToManyField(Tag, related_name="recipes", blank=True)
    servings = models.PositiveSmallIntegerField(default=2)
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField()

    def __str__(self):
        return self.slug

    def rating_summary(self):
        totals = self.reviews.aggregate(average=Avg("rating"), count=Count("id"))
        return rating_payload(totals["average"], totals["count"])


class Ingredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="ingredients")
    position = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=120)
    quantity = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "position"], name="ingredient_position_unique"
            )
        ]


class Review(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.CharField(max_length=80)
    rating = models.PositiveSmallIntegerField()
    body = models.TextField(blank=True)
    created_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5), name="review_rating_range"
            )
        ]

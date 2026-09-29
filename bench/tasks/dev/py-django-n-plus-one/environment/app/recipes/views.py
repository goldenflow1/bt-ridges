from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from recipes.models import Recipe
from recipes.serializers import serialize_recipe_detail, serialize_recipe_summary

PAGE_SIZE = 20


def recipe_list(request):
    recipes = Recipe.objects.filter(published=True).order_by("-created_at", "id")
    tag = request.GET.get("tag")
    if tag:
        recipes = recipes.filter(tags__slug=tag)
    page = Paginator(recipes, PAGE_SIZE).get_page(request.GET.get("page"))
    return JsonResponse(
        {
            "count": page.paginator.count,
            "page": page.number,
            "pages": page.paginator.num_pages,
            "results": [serialize_recipe_summary(recipe) for recipe in page],
        }
    )


def recipe_detail(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug, published=True)
    return JsonResponse(serialize_recipe_detail(recipe))

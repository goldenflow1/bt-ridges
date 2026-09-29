from django.urls import path

from recipes import views

urlpatterns = [
    path("recipes/", views.recipe_list, name="recipe-list"),
    path("recipes/<slug:slug>/", views.recipe_detail, name="recipe-detail"),
]

from django.test import TestCase

from recipes.tests import factories as f


class RecipeListTests(TestCase):
    def get(self, **params):
        response = self.client.get("/api/recipes/", params)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_list_payload(self):
        ada = f.author("ada-quinn", "Ada Quinn")
        soup = f.recipe(
            "Leek Soup",
            by=ada,
            tags=[f.tag("vegetarian"), f.tag("soup")],
            ingredients=["leeks", "potatoes", "stock"],
        )

        body = self.get()

        self.assertEqual(body["count"], 1)
        self.assertEqual(
            body["results"],
            [
                {
                    "id": soup.id,
                    "slug": soup.slug,
                    "title": "Leek Soup",
                    "author": {"handle": "ada-quinn", "name": "Ada Quinn"},
                    "tags": ["soup", "vegetarian"],
                    "ingredient_count": 3,
                    "rating": {"average": None, "count": 0},
                    "created_at": "2026-04-01T12:00:00+00:00",
                }
            ],
        )

    def test_rating_summary_in_list(self):
        f.recipe("Flatbread", ratings=[5, 4, 4])

        [row] = self.get()["results"]

        self.assertEqual(row["rating"], {"average": 4.33, "count": 3})
        self.assertEqual(row["ingredient_count"], 0)

    def test_newest_first_and_unpublished_hidden(self):
        older = f.recipe("Older", minutes_ago=30)
        newer = f.recipe("Newer", minutes_ago=5)
        f.recipe("Draft", published=False)

        body = self.get()

        self.assertEqual([r["id"] for r in body["results"]], [newer.id, older.id])

    def test_tag_filter(self):
        quick = f.tag("quick")
        fast = f.recipe("Toast", tags=[quick, f.tag("breakfast")])
        f.recipe("Stew", tags=[f.tag("slow")])

        body = self.get(tag="quick")

        self.assertEqual([r["id"] for r in body["results"]], [fast.id])
        self.assertEqual(body["results"][0]["tags"], ["breakfast", "quick"])

    def test_pagination(self):
        for i in range(23):
            f.recipe(f"Dish {i}", minutes_ago=i)

        first = self.get()
        second = self.get(page=2)

        self.assertEqual((first["count"], first["pages"], len(first["results"])), (23, 2, 20))
        self.assertEqual(len(second["results"]), 3)
        self.assertEqual(second["results"][-1]["title"], "Dish 22")

    def test_empty_list(self):
        self.assertEqual(self.get(), {"count": 0, "page": 1, "pages": 1, "results": []})


class RecipeDetailTests(TestCase):
    def test_detail_payload(self):
        dish = f.recipe(
            "Dal",
            tags=[f.tag("vegan")],
            ingredients=["lentils"],
            ratings=[3, 5],
            servings=4,
        )

        response = self.client.get(f"/api/recipes/{dish.slug}/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["servings"], 4)
        self.assertEqual([i["name"] for i in body["ingredients"]], ["lentils"])
        self.assertEqual(body["rating"], {"average": 4.0, "count": 2})
        self.assertEqual([r["rating"] for r in body["reviews"]], [5, 3])

    def test_unpublished_detail_is_404(self):
        draft = f.recipe("Secret", published=False)

        self.assertEqual(self.client.get(f"/api/recipes/{draft.slug}/").status_code, 404)

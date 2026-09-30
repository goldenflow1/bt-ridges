from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from recipes.models import Recipe
from recipes.tests import factories as f


class HiddenListingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.zucchini = f.tag("zucchini", "Awesome zucchini")
        cls.mint = f.tag("mint", "Minty")
        cls.apple = f.tag("apple", "Zesty apple")
        cls.batch = f.tag("batch", "Batch cooking")

    def fetch(self, path="/api/recipes/", **params):
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(path, params)
        self.assertEqual(response.status_code, 200)
        return len(captured), response.json()

    def rich_recipe(self, title, minutes_ago, ratings=(5, 4, 4, 2)):
        return f.recipe(
            title,
            by=f.author(),
            tags=[self.zucchini, self.mint, self.apple],
            ingredients=["onion", "garlic", "oil"],
            ratings=ratings,
            minutes_ago=minutes_ago,
        )

    def test_query_count_does_not_grow_with_rows(self):
        for i in range(2):
            self.rich_recipe(f"Small {i}", i)
        small, body = self.fetch()
        self.assertEqual(len(body["results"]), 2)
        for i in range(2, 20):
            self.rich_recipe(f"Small {i}", i)
        full, body = self.fetch()
        self.assertEqual(len(body["results"]), 20)

        self.assertEqual(small, full)
        self.assertLessEqual(full, 6)

    def test_payload_is_exact_with_many_relations(self):
        chef = f.author("mira-sol", "Mira Sol")
        stew = f.recipe(
            "Harvest Stew",
            by=chef,
            tags=[self.zucchini, self.apple, self.mint],
            ingredients=["squash", "apple", "mint", "stock", "salt"],
            ratings=[5, 4, 4, 2, 1, 3],
            minutes_ago=1,
        )
        salad = f.recipe(
            "Plain Salad",
            by=chef,
            tags=[],
            ingredients=["leaves", "vinegar"],
            ratings=[],
            minutes_ago=2,
        )

        _, body = self.fetch()

        self.assertEqual(
            body["results"],
            [
                {
                    "id": stew.id,
                    "slug": stew.slug,
                    "title": "Harvest Stew",
                    "author": {"handle": "mira-sol", "name": "Mira Sol"},
                    "tags": ["apple", "mint", "zucchini"],
                    "ingredient_count": 5,
                    "rating": {"average": 3.17, "count": 6},
                    "created_at": "2026-04-01T11:59:00+00:00",
                },
                {
                    "id": salad.id,
                    "slug": salad.slug,
                    "title": "Plain Salad",
                    "author": {"handle": "mira-sol", "name": "Mira Sol"},
                    "tags": [],
                    "ingredient_count": 2,
                    "rating": {"average": None, "count": 0},
                    "created_at": "2026-04-01T11:58:00+00:00",
                },
            ],
        )

    def test_rating_rounding_matches_model_and_detail(self):
        dish = self.rich_recipe("Even Split", 0, ratings=[4, 4, 4, 4, 4, 4, 4, 5])
        other = self.rich_recipe("Thirds", 1, ratings=[5, 5, 4])

        _, body = self.fetch()
        rows = {row["id"]: row for row in body["results"]}

        self.assertEqual(rows[dish.id]["rating"], {"average": 4.12, "count": 8})
        self.assertEqual(rows[other.id]["rating"], {"average": 4.67, "count": 3})
        for recipe in Recipe.objects.filter(id__in=[dish.id, other.id]):
            self.assertEqual(rows[recipe.id]["rating"], recipe.rating_summary())
            _, detail = self.fetch(f"/api/recipes/{recipe.slug}/")
            self.assertEqual(detail["rating"], rows[recipe.id]["rating"])
            self.assertEqual(detail["tags"], rows[recipe.id]["tags"])
            self.assertEqual(detail["ingredient_count"], 3)

    def test_filtered_later_pages_stay_bounded(self):
        for i in range(45):
            f.recipe(
                f"Batch {i}",
                tags=[self.batch, self.mint] if i % 3 else [self.batch],
                ingredients=["rice", "beans"],
                ratings=[3, 4],
                minutes_ago=i,
            )
        f.recipe("Other", tags=[self.apple], minutes_ago=100)

        queries_2, page_2 = self.fetch(tag="batch", page=2)
        queries_3, page_3 = self.fetch(tag="batch", page=3)

        self.assertEqual(page_2["count"], 45)
        titles_2 = [r["title"] for r in page_2["results"]]
        titles_3 = [r["title"] for r in page_3["results"]]
        self.assertEqual(titles_2, [f"Batch {i}" for i in range(20, 40)])
        self.assertEqual(titles_3, [f"Batch {i}" for i in range(40, 45)])
        self.assertEqual(page_2["results"][1]["tags"], ["batch"])
        self.assertEqual(page_2["results"][2]["tags"], ["batch", "mint"])
        self.assertEqual(page_2["results"][2]["ingredient_count"], 2)
        self.assertEqual(page_2["results"][2]["rating"], {"average": 3.5, "count": 2})
        self.assertLessEqual(queries_2, 6)
        self.assertEqual(queries_2, queries_3)

    def test_unpublished_recipes_do_not_leak(self):
        visible = self.rich_recipe("Visible", 0)
        f.recipe("Hidden draft", tags=[self.mint], published=False)

        _, body = self.fetch()
        _, by_tag = self.fetch(tag="mint")

        self.assertEqual([r["id"] for r in body["results"]], [visible.id])
        self.assertEqual([r["id"] for r in by_tag["results"]], [visible.id])
        self.assertEqual(body["count"], 1)

    def test_same_timestamp_recipes_page_in_id_order(self):
        tied = [
            f.recipe(
                f"Tie {i}", tags=[self.mint], ingredients=["salt"], ratings=[4], minutes_ago=7
            )
            for i in range(45)
        ]
        newest = f.recipe("Fresh", minutes_ago=1)

        ids = []
        for page in (1, 2, 3):
            _, body = self.fetch(page=page)
            ids += [r["id"] for r in body["results"]]

        self.assertEqual(ids, [newest.id] + [r.id for r in tied])

    def test_listing_counts_and_average_come_from_the_database(self):
        for i in range(3):
            self.rich_recipe(f"Pantry {i}", i, ratings=[5, 4, 2])

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get("/api/recipes/")
        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        self.assertEqual(row["ingredient_count"], 3)
        self.assertEqual(row["rating"], {"average": 3.67, "count": 3})

        statements = [q["sql"].upper() for q in captured.captured_queries]

        def aggregated(table, *functions):
            return any(
                table in sql and any(f"{fn}(" in sql for fn in functions) for sql in statements
            )

        self.assertTrue(
            aggregated("RECIPES_INGREDIENT", "COUNT"),
            "ingredient_count is not computed by the database",
        )
        self.assertTrue(
            aggregated("RECIPES_REVIEW", "COUNT"), "rating.count is not computed by the database"
        )
        self.assertTrue(
            aggregated("RECIPES_REVIEW", "AVG", "SUM"),
            "rating.average is not computed by the database",
        )

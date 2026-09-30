from django.db import models
from django.db.models import functions


class Member(models.Model):
    id = models.BigAutoField(primary_key=True)
    branch_id = models.IntegerField()
    email = models.CharField(max_length=254)
    display_name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    @classmethod
    def email_expression(cls):
        return functions.Lower('email')

    class Meta:
        db_table = 'library_member'
        indexes = []

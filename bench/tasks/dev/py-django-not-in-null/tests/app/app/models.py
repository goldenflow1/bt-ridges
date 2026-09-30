from django.db import models


class Customer(models.Model):
    tenant_id = models.IntegerField()
    name = models.TextField()

    class Meta:
        app_label = 'app'
        db_table = 'customers'
        managed = False


class Block(models.Model):
    customer_id = models.IntegerField(null=True)
    tenant_id = models.IntegerField()
    active = models.BooleanField()
    expires_at = models.DateTimeField(null=True)

    class Meta:
        app_label = 'app'
        db_table = 'blocks'
        managed = False

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(name='Member', fields=[
        ('id', models.BigAutoField(primary_key=True, serialize=False)),
        ('branch_id', models.IntegerField()),
        ('email', models.CharField(max_length=254)),
        ('display_name', models.CharField(max_length=100)),
        ('active', models.BooleanField(default=True)),
    ], options={'db_table':'library_member', 'indexes':[]})]

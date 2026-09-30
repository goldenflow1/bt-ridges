#!/bin/bash
set -euo pipefail
cd /app
python - <<'PYFIX'
from pathlib import Path
p=Path('library/models.py')
assert p.read_text()=="from django.db import models\nfrom django.db.models import functions\n\n\nclass Member(models.Model):\n    id = models.BigAutoField(primary_key=True)\n    branch_id = models.IntegerField()\n    email = models.CharField(max_length=254)\n    display_name = models.CharField(max_length=100)\n    active = models.BooleanField(default=True)\n\n    @classmethod\n    def email_expression(cls):\n        return functions.Lower('email')\n\n    class Meta:\n        db_table = 'library_member'\n        indexes = []\n", 'source anchor changed'
m=Path('library/schema_migrations/0002_email_lookup.py')
assert not m.exists(), 'new migration already exists'
p.write_text("from django.db import models\nfrom django.db.models import functions\n\n\nclass Member(models.Model):\n    id = models.BigAutoField(primary_key=True)\n    branch_id = models.IntegerField()\n    email = models.CharField(max_length=254)\n    display_name = models.CharField(max_length=100)\n    active = models.BooleanField(default=True)\n\n    @classmethod\n    def email_expression(cls):\n        return functions.Lower('email')\n\n    class Meta:\n        db_table = 'library_member'\n        indexes = [models.Index(functions.Lower('email'), name='library_member_lower_email')]\n")
m.write_text("from django.db import migrations, models\nfrom django.db.models.functions import Lower\n\n\nclass Migration(migrations.Migration):\n    dependencies = [('library', '0001_initial')]\n    operations = [migrations.AddIndex(model_name='member', index=models.Index(Lower('email'), name='library_member_lower_email'))]\n")
PYFIX

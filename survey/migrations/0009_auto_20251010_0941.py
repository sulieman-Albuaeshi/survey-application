# survey/migrations/0005_populate_uuids.py
from django.db import migrations
import uuid

def create_uuids(apps, schema_editor):
    Survey = apps.get_model('survey', 'Survey')
    
    # Iterate through *all* existing rows (since they all have the same duplicate UUID)
    for row in Survey.objects.all():
        # Overwrite the duplicate UUID with a new, unique one
        row.uuid = uuid.uuid4() 
        row.save(update_fields=['uuid']) 

class Migration(migrations.Migration):
    dependencies = [
        ('survey', '0004_survey_uuid'), 
    ]

    operations = [
        migrations.RunPython(create_uuids, reverse_code=migrations.RunPython.noop),
    ]
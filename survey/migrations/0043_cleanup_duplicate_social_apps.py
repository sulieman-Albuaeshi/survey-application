from django.db import migrations

def remove_duplicate_social_apps(apps, schema_editor):
    try:
        SocialApp = apps.get_model('socialaccount', 'SocialApp')
        Site = apps.get_model('sites', 'Site')
        
        # البحث عن كل التطبيقات التي تستخدم مزود google
        google_apps = SocialApp.objects.filter(provider='google').order_by('id')
        
        # إذا وجدنا أكثر من واحد
        if google_apps.count() > 1:
            # نحتفظ بالأخير (الذي تم إنشاؤه مؤخراً)
            valid_app = google_apps.last()
            print(f"Keeping SocialApp {valid_app.id} ({valid_app.name})")
            
            # نحذف الباقي
            duplicates = google_apps.exclude(id=valid_app.id)
            deleted_count = duplicates.count()
            duplicates.delete()
            print(f"Deleted {deleted_count} duplicate SocialApp(s)")
            
            # التأكد من ربط التطبيق المتبقي بالموقع الافتراضي
            if Site.objects.filter(id=1).exists():
                site = Site.objects.get(id=1)
                valid_app.sites.add(site)
                valid_app.save()

    except Exception as e:
        print(f"Error during cleanup: {e}")

class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0042_remove_likertquestion_scale_max'),
        ('socialaccount', '0001_initial'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(remove_duplicate_social_apps),
    ]

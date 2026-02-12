import os
from django.db import migrations

def force_fix_google_apps(apps, schema_editor):
    try:
        SocialApp = apps.get_model('socialaccount', 'SocialApp')
        Site = apps.get_model('sites', 'Site')
        
        # 1. حذف جميع تطبيقات جوجل الموجودة مسبقاً (لتنظيف التكرار وأي بيانات قديمة)
        deleted_count, _ = SocialApp.objects.filter(provider='google').delete()
        print(f"Deleted {deleted_count} existing Google SocialApp(s).")

        # 2. جلب المفاتيح من متغيرات البيئة (الآن الاسم صحيح في ريندر)
        client_id = os.environ.get('GOOGLE_CLIENT_ID')
        secret = os.environ.get('GOOGLE_CLIENT_SECRET')

        if client_id and secret:
            # 3. إنشاء تطبيق واحد جديد ونظيف
            new_app = SocialApp.objects.create(
                provider='google',
                name='Google',
                client_id=client_id,
                secret=secret,
                key=''
            )
            
            # 4. ربطه بالموقع الافتراضي
            if Site.objects.filter(id=1).exists():
                site = Site.objects.get(id=1)
                new_app.sites.add(site)
                new_app.save()
                print(f"Created new Google SocialApp linked to Site ID 1.")
            else:
                print("Warning: Site ID 1 not found. App created but not linked to site.")
        else:
            print("Skipping creation: GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET missing in environment.")

    except Exception as e:
        print(f"Error in force_fix_google_apps: {e}")

class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0043_cleanup_duplicate_social_apps'),
        ('socialaccount', '0001_initial'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(force_fix_google_apps),
    ]

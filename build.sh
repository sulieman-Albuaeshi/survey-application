#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# تجميع الملفات الثابتة (CSS/JS)
python manage.py collectstatic --no-input

# تطبيق الترحيلات لقاعدة البيانات
python manage.py migrate

python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'YourPassword123')
    print("Superuser created successfully!")
else:
    print("Superuser already exists.")
END
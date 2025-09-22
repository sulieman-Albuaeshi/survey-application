from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    pass


STATE_CHOICES = [
    ("draft", "Draft"),
    ("published", "Published"),
    ("archived", "Archived"),
]

# Create your models here.
class survey(models.Model):
    titel = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default="draft")
    is_puplished = models.BooleanField(default=False)
    created_by =  models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='surveys')
from django.db import models
from django.contrib.auth.models import AbstractUser

import uuid

class CustomUser(AbstractUser):
    pass


STATE_CHOICES = [
    ("draft", "Draft"),
    ("published", "Published"),
    ("archived", "Archived"),
]

# Create your models here.
class Survey(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True, null=True)
    title = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default="draft")
    created_by =  models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='surveys')
    questions = models.ManyToManyField('Question', blank=False)

    @property
    def status_badge_class(self):
        if self.state == 'published':
            return 'bg-primary text-black'
        elif self.state == 'draft':
            return 'bg-yellow-200 text-black'
        elif self.state == 'archived':
            return 'bg-red-200 text-black'
        return 'bg-gray-100 text-black'
    


class Question(models.Model):
    label = models.TextField()
    helper_text = models.TextField(null=True, blank=True)
    required = models.BooleanField(default=False)
    position = models.IntegerField()

    @classmethod
    def get_available_type_names(cls):
        """Returns a list of NAME static attributes from all direct subclasses."""
        names = []
        for subclass in cls.__subclasses__():
            if hasattr(subclass, 'NAME'):
                names.append(subclass.NAME)
        return names


class MultiChoiceQuestion(Question):
    options = models.JSONField()
    allow_multiple = models.BooleanField(default=True)
    randomize_options = models.BooleanField(default=False)
    show_as_dropdown = models.BooleanField(default=False)
    show_as_rank_Question = models.BooleanField(default=False)
    NAME = "Multi-Choice Question"

    def add_Option(self, option):
        if not self.options:
            self.options = []
        self.options.append(option)
        self.save()

    def remove_Option(self, option):
        if self.options and option in self.options:
            self.options.remove(option)
            self.save()

class LikertQuestion(Question):
    scale_min = models.IntegerField(default=1)
    scale_max = models.IntegerField(default=5)
    scale_labels = models.JSONField(null=True, blank=True)
    NAME = "Likert Question"    

    def set_Scale_Labels(self, labels):
        if len(labels) != (self.scale_max - self.scale_min + 1):
            raise ValueError("Number of labels must match the scale range.")
        self.scale_labels = labels
        self.save()
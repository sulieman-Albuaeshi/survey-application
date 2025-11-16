from django.db import models
from django.contrib.auth.models import AbstractUser
from polymorphic.models import PolymorphicModel

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
    question_count = models.IntegerField(default=0)
    shuffle_questions = models.BooleanField(default=False)
    anonymous_responses = models.BooleanField(default=False)

    @property
    def status_badge_class(self):
        if self.state == 'published':
            return 'bg-primary text-black'
        elif self.state == 'draft':
            return 'bg-yellow-200 text-black'
        elif self.state == 'archived':
            return 'bg-red-200 text-black'
        return 'bg-gray-100 text-black'
    
    @property
    def response_count(self):
        return self.responses.count()
    
    def get_response_stats(self):
        """Get statistics about responses for this survey"""
        return {
            'total_responses': self.response_count,
            'completion_rate': self.get_completion_rate(),
            'avg_response_time': self.get_avg_response_time(),
        }
    
    def get_completion_rate(self):
        """Calculate completion rate (placeholder)"""
        return 100 if self.response_count > 0 else 0
    
    def get_avg_response_time(self):
        """Calculate average response time (placeholder)"""
        return "N/A"
    


class Question(PolymorphicModel):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
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

    def get_answer_distribution(self):
        """Get distribution of answers for this question"""
        answers = Answer.objects.filter(question=self)
        distribution = {}
        
        for answer in answers:
            answer_data = answer.answer_data
            if isinstance(answer_data, list):
                for item in answer_data:
                    distribution[item] = distribution.get(item, 0) + 1
            else:
                distribution[answer_data] = distribution.get(answer_data, 0) + 1
        
        return distribution

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

    def get_average_rating(self):
        """Calculate average rating for this question"""
        answers = Answer.objects.filter(question=self)
        if not answers.exists():
            return 0
        
        total = sum(float(answer.answer_data) for answer in answers)
        return round(total / answers.count(), 2)
    
    def get_rating_distribution(self):
        """Get distribution of ratings"""
        answers = Answer.objects.filter(question=self)
        distribution = {}
        
        for i in range(self.scale_min, self.scale_max + 1):
            distribution[i] = 0
        
        for answer in answers:
            rating = int(float(answer.answer_data))
            distribution[rating] = distribution.get(rating, 0) + 1
        
        return distribution


class Response(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='responses')
    respondent = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Response to {self.survey.title} at {self.created_at}"


class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_data = models.JSONField(null=True, blank=True)
    
    def __str__(self):
        return f"Answer for {self.question.label[:30]}: {self.answer_data}"
import factory
from factory.django import DjangoModelFactory
from survey.models import SectionHeader, Survey, CustomUser
from survey.models import (
    CustomUser, 
    Survey, 
    MultiChoiceQuestion, 
    TextQuestion, 
    LikertQuestion,
    MatrixQuestion,
    RatingQuestion,
    RankQuestion, 
    Response,
    Answer
)


class UserFactory(DjangoModelFactory):
    class Meta:
        model = CustomUser
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.Faker("email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        password = extracted or 'password123'
        self.set_password(password)
        if create:
            self.save()


class SurveyFactory(DjangoModelFactory):
    class Meta:
        model = Survey

    title = factory.Faker("sentence", nb_words=4)
    description = factory.Faker("paragraph", nb_sentences=3)
    created_by = factory.SubFactory(UserFactory)
    state = factory.Iterator(["draft", "published", "archived"])

class QuestionFactory(DjangoModelFactory):
    """Base factory for shared question fields"""
    class Meta:
        model = MultiChoiceQuestion # Defaulting to one concrete type, usually overridden
        abstract = True

    survey = factory.SubFactory(SurveyFactory)
    label = factory.Faker("sentence", nb_words=6)
    required = factory.Faker("boolean")
    position = factory.Sequence(lambda n: n)


class MultiChoiceQuestionFactory(QuestionFactory):
    class Meta:
        model = MultiChoiceQuestion

    # Using LazyAttribute for JSON fields to avoid mutable defaults
    options = factory.LazyAttribute(lambda o: ["Red", "Green", "Blue", "Yellow"])
    allow_multiple = False

class TextQuestionFactory(QuestionFactory):
    class Meta:
        model = TextQuestion

    is_long_answer = factory.LazyAttribute(lambda o: [False, True])
    min_length = 10
    max_length = 500

class LikertQuestionFactory(QuestionFactory):
    class Meta:
        model = LikertQuestion
        
    options = factory.LazyAttribute(lambda o: ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"])
    scale_max = 5

class MatrixQuestionFactory(QuestionFactory):
    class Meta:
        model = MatrixQuestion
        
    rows = factory.LazyAttribute(lambda o: ["Row 1", "Row 2"])
    columns = factory.LazyAttribute(lambda o: ["Col 1", "Col 2", "Col 3"])

class RatingQuestionFactory(QuestionFactory):
    class Meta:
        model = RatingQuestion
    
    range_min = 1
    range_max = 5

class RankQuestionFactory(QuestionFactory):
    class Meta:
        model = RankQuestion
        
    options = factory.LazyAttribute(lambda o: ["Option A", "Option B", "Option C"])

class ResponseFactory(DjangoModelFactory):
    class Meta:
        model = Response

    survey = factory.SubFactory(SurveyFactory)
    # If you want anonymous responses, you can set this to None in the test
    respondent = factory.SubFactory(UserFactory) 
    completed = True

class AnswerFactory(DjangoModelFactory):
    class Meta:
        model = Answer

    response = factory.SubFactory(ResponseFactory)
    question = factory.SubFactory(MultiChoiceQuestionFactory)
    section = 1
    answer_data = "Red" 

    # Note: 'question' and 'answer_data' must be passed when calling
    # AnswerFactory.create(question=question_instance, answer_data="Red")

class SectionHeaderFactory(DjangoModelFactory):
    class Meta:
        model = SectionHeader

    survey = factory.SubFactory(SurveyFactory)
    label = factory.Faker("sentence", nb_words=3)
    position = factory.Sequence(lambda n: n)

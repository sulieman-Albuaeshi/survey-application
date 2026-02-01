import pytest
import random
from survey.models import LikertQuestion, MatrixQuestion, RatingQuestion, RankQuestion
from survey.tests.factories import (
    SurveyFactory, 
    ResponseFactory, 
    AnswerFactory, 
    LikertQuestionFactory,
    MatrixQuestionFactory,
    RatingQuestionFactory,
    RankQuestionFactory,
    MultiChoiceQuestionFactory
)

@pytest.mark.django_db
class TestComplexStatistics:
    def test_likert_statistics_complex(self):
        survey = SurveyFactory()
        question = LikertQuestionFactory(survey=survey)

        # Create responses with answers
        # Map integer indices to the actual option text because LikertQuestion expects
        # answer_data to match one of the string options options.
        indices = [2, 3, 4, 4, 5, 2, 3, 4, 4, 5, 2, 3, 4, 4, 5]
        options = question.options
        
        print(options)
        for idx in indices:
            print(idx)
            response = ResponseFactory(survey=survey)
            answer_text = options[idx - 1]
            AnswerFactory(response=response, question=question, answer_data=answer_text)
        
        stats = question.get_statistic()

        assert stats["mean"] == 3.6
        assert stats["median"] == 4
        assert stats["interpretation"] == "Agree"
        assert stats['t_test'] == 2.2014

    def test_rating_statistics_complex(self):
        survey = SurveyFactory()
        # A 5-star rating scale
        question = RatingQuestionFactory(survey=survey, range_min=1, range_max=5)
        
        # Data sequence: [2, 3, 4, 4, 5, 2, 3, 4, 4, 5, 2, 3, 4, 4, 5]
        scores = [2, 3, 4, 4, 5, 2, 3, 4, 4, 5, 2, 3, 4, 4, 5]
        
        for score in scores:
            AnswerFactory(
                response=ResponseFactory(survey=survey),
                question=question,
                answer_data=str(score)
            )
                
        stats = question.get_statistic()
        
        # Calculation: Sum(54) / Count(15) = 3.6
        assert stats["mean"] == 3.6
        
        # Sorted: [2,2,2, 3,3,3, 4,4,4,4,4,4, 5,5,5]
        # The 8th value (middle) is 4
        assert stats["median"] == 4
        assert stats["interpretation"] == "4"

    def test_matrix_statistics_complex(self):
        survey = SurveyFactory()
        rows = ["Customer Support", "Product Quality"]
        cols = ["Poor", "Fair", "Good", "Excellent"] # Indexes 0, 1, 2, 3
        # Weight mapping: Poor=1, Fair=2, Good=3, Excellent=4
        question = MatrixQuestionFactory(survey=survey, rows=rows, columns=cols)
        
        # Mixed Responses
        dataset = [
            {"Customer Support": "Excellent", "Product Quality": "Fair"}, # 4, 2
            {"Customer Support": "Good",      "Product Quality": "Poor"}, # 3, 1
            {"Customer Support": "Excellent", "Product Quality": "Fair"}, # 4, 2
        ]
        
        for payload in dataset:
            AnswerFactory(
                response=ResponseFactory(survey=survey),
                question=question,
                answer_data=payload
            )
                
        stats = question.get_row_statistics()
        
        # Customer Support scores: [4, 3, 4] 
        # Mean: 11 / 3 = 3.66...
        assert pytest.approx(stats["Customer Support"]["mean"], 0.01) == 3.67
        assert stats["Customer Support"]["median"] == 4.0
        
        # Product Quality scores: [2, 1, 2]
        # Mean: 5 / 3 = 1.66...
        assert pytest.approx(stats["Product Quality"]["mean"], 0.01) == 1.67
        assert stats["Product Quality"]["median"] == 2.0

    def test_rank_statistics_complex(self):
        survey = SurveyFactory()
        options = ["Speed", "UI Design", "Security"]
        question = RankQuestionFactory(survey=survey, options=options)
        
        # Data:
        # User 1: Speed=1, UI=2, Sec=3
        # User 2: Speed=2, UI=1, Sec=3
        # User 3: Speed=1, UI=3, Sec=2
        # User 4: Speed=1, UI=2, Sec=3
        payloads = [
            {"Speed": "1", "UI Design": "2", "Security": "3"},
            {"Speed": "2", "UI Design": "1", "Security": "3"},
            {"Speed": "1", "UI Design": "3", "Security": "2"},
            {"Speed": "1", "UI Design": "2", "Security": "3"},
        ]
        
        for p in payloads:
            AnswerFactory(response=ResponseFactory(survey=survey), question=question, answer_data=p)
        
        avg_ranks = question.get_average_ranks()
        
        # Speed: (1+2+1+1) / 4 = 5 / 4 = 1.25
        assert avg_ranks["Speed"] == 1.25
        
        # UI Design: (2+1+3+2) / 4 = 8 / 4 = 2.0
        assert avg_ranks["UI Design"] == 2.0
        
        # Security: (3+3+2+3) / 4 = 11 / 4 = 2.75
        assert avg_ranks["Security"] == 2.75

@pytest.mark.django_db
class TestMultiChoiceQuestionModel:
    def test_multi_choice_distribution(self):
        survey = SurveyFactory()
        question = MultiChoiceQuestionFactory(survey=survey, options=["Java", "Python", "Go"])
        
        # User 1: Java
        AnswerFactory(response=ResponseFactory(survey=survey), question=question, answer_data="Java")
        
        # User 2: Python
        AnswerFactory(response=ResponseFactory(survey=survey), question=question, answer_data="Python")
        
        # User 3: Java
        AnswerFactory(response=ResponseFactory(survey=survey), question=question, answer_data="Java")

        distribution = question.get_answer_distribution()
        
        # Results: Java=2, Python=1, Go=0 (or missing from dict)
        assert distribution["Java"] == 2
        assert distribution["Python"] == 1
        assert "Go" not in distribution or distribution["Go"] == 0

    def test_multi_choice_multiple_select(self):
        # Testing checking multiple boxes
        survey = SurveyFactory()
        question = MultiChoiceQuestionFactory(
            survey=survey, 
            options=["Morning", "Afternoon", "Evening"],
            allow_multiple=True
        )
        
        # User selects Moring AND Evening
        AnswerFactory(
            response=ResponseFactory(survey=survey), 
            question=question, 
            answer_data=["Morning", "Evening"]
        )

        distribution = question.get_answer_distribution()
        
        assert distribution["Morning"] == 1
        assert distribution["Evening"] == 1
        assert "Afternoon" not in distribution or distribution["Afternoon"] == 0
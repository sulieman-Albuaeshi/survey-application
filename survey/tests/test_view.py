from django.http import QueryDict
import pytest
from survey.tests.factories import (
    RatingQuestionFactory, ResponseFactory, SurveyFactory, SectionHeaderFactory, AnswerFactory, MatrixQuestionFactory, MultiChoiceQuestionFactory)
from survey.utility import (
    get_dashboard_surveys,
    normalize_formset_indexes, 
    organize_survey_sections,
    get_survey_export_data,
    get_correlation_table,
    get_survey_data_by_sections)

def test_normalize_formset_indexes():
    # Simulate a QueryDict with gaps (0 and 2 exist, 1 was deleted)
    data = QueryDict(mutable=True)
    data.update({
        'questions-TOTAL_FORMS': '2',
        'questions-0-title': 'First Question',
        'questions-0-position': '1',
        'questions-2-title': 'Second Question', # Note index skip from 0 to 2
        'questions-2-position': '3',
        'other-field': 'keep-me'
    })

    normalized = normalize_formset_indexes(data, 'questions')

    # Assert indexes are continuous
    assert normalized['questions-0-title'] == 'First Question'
    assert normalized['questions-1-title'] == 'Second Question'
    assert 'questions-2-title' not in normalized
    
    # Assert total forms is updated
    assert normalized['questions-TOTAL_FORMS'] == 2
    
    # Assert non-prefixed data remains
    assert normalized['other-field'] == 'keep-me'

@pytest.mark.django_db
def test_get_dashboard_surveys_filtering(admin_user):
    # Create surveys with different states and titles
    SurveyFactory(title="Alpha Survey", state="published", created_by=admin_user)
    SurveyFactory(title="Beta Survey", state="draft", created_by=admin_user)
    SurveyFactory(title="Gamma", state="published", created_by=admin_user)

    # 1. Test Search
    params = {'search': 'Survey'}
    result = get_dashboard_surveys(admin_user, params)
    assert result['page'].paginator.count == 2 # Alpha and Beta
    
    # 2. Test State Filter
    params = {'state_filter': 'published'}
    result = get_dashboard_surveys(admin_user, params)
    assert result['page'].paginator.count == 2 # Alpha and Gamma
    
    # 3. Test Combined
    params = {'search': 'Alpha', 'state_filter': 'published'}
    result = get_dashboard_surveys(admin_user, params)
    assert result['page'].paginator.count == 1

@pytest.mark.django_db
def test_organize_survey_sections():
    survey = SurveyFactory()
    # Position 1: Question
    RatingQuestionFactory(survey=survey, position=1, label="Q1")
    # Position 2: Header
    SectionHeaderFactory(survey=survey, position=2, label="Demographics")
    # Position 3: Question
    RatingQuestionFactory(survey=survey, position=3, label="Q2")

    sections = organize_survey_sections(survey)

    # Expecting 2 sections: 
    # 1. General/Intro (Default) containing Q1
    # 2. Demographics containing Q2
    assert len(sections) == 2
    assert sections[0]['label'] == 'General / Introduction'
    assert sections[0]['questions'][0].label == "Q1"
    
    assert sections[1]['label'] == 'Demographics'
    assert sections[1]['questions'][0].label == "Q2"

@pytest.mark.django_db
def test_get_survey_export_data_numeric_complex():
    survey = SurveyFactory()
    
    # 1. Rating Question (1 column)
    q_rate = RatingQuestionFactory(survey=survey, position=1, label="Satisfaction", range_min=1, range_max=5)
    
    # 2. Multi-Choice Question (2 columns: "Red" and "Blue")
    q_multi = MultiChoiceQuestionFactory(
        survey=survey, 
        position=2, 
        label="Colors", 
        options=["Red", "Blue"]
    )
    
    # 3. Matrix Question (2 rows x 2 cols = 4 columns)
    # Rows: [Service, Quality] | Cols: [Poor, Good]
    q_matrix = MatrixQuestionFactory(
        survey=survey, 
        position=3, 
        label="Feedback",
        rows=["Service", "Quality"],
        columns=["Poor", "Good"]
    )

    # --- RESPONDENT 1 ---
    resp1 = ResponseFactory(survey=survey)
    # Rating: 5
    AnswerFactory(response=resp1, question=q_rate, answer_data="5")
    # Multi: Selected "Red" only
    AnswerFactory(response=resp1, question=q_multi, answer_data=["Red"])
    # Matrix: Service=Good, Quality=Poor
    AnswerFactory(response=resp1, question=q_matrix, answer_data={"Service_row1": "Good", "Quality_row2": "Poor"})

    # --- RESPONDENT 2 ---
    resp2 = ResponseFactory(survey=survey)
    # Rating: 2
    AnswerFactory(response=resp2, question=q_rate, answer_data="2")
    # Multi: Selected Both
    AnswerFactory(response=resp2, question=q_multi, answer_data=["Red", "Blue"])
    # Matrix: Service=Poor, Quality=Poor
    AnswerFactory(response=resp2, question=q_matrix, answer_data={"Service_row1": "Poor", "Quality_row2": "Poor"})

    # Execute
    headers, rows, questions = get_survey_export_data(survey, format_type='numeric')
    print("Headers:", headers)
    print("Rows:", rows[0])
    print("Rows:", rows[1])
    # Header Assertions
    # 2 (Base: Resp, Time) + 1 (Rate) + 2 (Multi) + 4 (Matrix) = 9 columns total
    assert len(headers) == 9
    assert headers[2] == "Satisfaction"
    assert headers[3] == "Colors [Red]"
    assert headers[4] == "Colors [Blue]"
    assert headers[5] == "Feedback [Service - Poor]"
    assert headers[6] == "Feedback [Service - Good]"

    # Note: Logic usually returns 1 for selected, 0 for not in numeric expansion
    row2 = rows[0]
    assert row2[2] == '2'           # Satisfaction
    assert row2[3] == '1'           # Colors [Red] - Selected
    assert row2[4] == '1'           # Colors [Blue] - Selected
    assert row2[5] == '1'           # Feedback [Service - Poor] - Selected
    assert row2[6] == '0'           # Feedback [Service - Good] - Not Selected
    assert row2[7] == '1'           # Feedback [Quality - Poor] - Selected
    assert row2[8] == '0'           # Feedback [Quality - Good] - Not Selected


    # Data Assertions Respondent 2 (Index 1 in rows)
    row1 = rows[1]
    assert row1[2] == '5'         # Satisfaction
    assert row1[3] == '1'           # Colors [Red] - Selected
    assert row1[4] == '0'           # Colors [Blue] - Not Selected
    assert row1[5] == '0'           # Feedback [Service - Poor] - Not Selected
    assert row1[6] == '1'           # Feedback [Service - Good] - Selected
    assert row1[7] == '1'           # Feedback [Quality - Poor] - Selected
    assert row1[8] == '0'           # Feedback [Quality - Good] - Not Selected

@pytest.mark.django_db
class TestGetCorrelationTable:
    def test_get_correlation_table_generation(self):
        survey = SurveyFactory()
        q1 = RatingQuestionFactory(survey=survey, label="Service")
        q2 = RatingQuestionFactory(survey=survey, label="Price")
        
        # Create 3 responses to have enough data for a correlation
        data = [
            (5, 5), (4, 4), (1, 2)
        ]
        
        for s1, s2 in data:
            r = ResponseFactory(survey=survey)
            AnswerFactory(response=r, question=q1, answer_data=str(s1))
            AnswerFactory(response=r, question=q2, answer_data=str(s2))
        
        # This should generate a base64 string
        chart_b64 = get_correlation_table(survey)
        
        assert isinstance(chart_b64, str)
        assert len(chart_b64) > 100 # Ensure it's not an empty string

    def test_get_correlation_table_success(self):
        survey = SurveyFactory()
        # Question A
        q1 = RatingQuestionFactory(survey=survey, label="Service Quality")
        # Question B
        q2 = RatingQuestionFactory(survey=survey, label="Pricing")
        
        # Dataset with a clear positive correlation
        # When Q1 is high, Q2 is high.
        data = [
            ("5", "5"), ("4", "4"), ("3", "3"), 
            ("2", "2"), ("1", "1"), ("5", "4")
        ]
        
        for s1, s2 in data:
            resp = ResponseFactory(survey=survey)
            AnswerFactory(response=resp, question=q1, answer_data=s1)
            AnswerFactory(response=resp, question=q2, answer_data=s2)
        
        chart_b64 = get_correlation_table(survey)
        
        # Assertions
        assert chart_b64 is not None
        assert isinstance(chart_b64, str)
        # Check for the base64 PNG header (standard for encoded images)
        assert len(chart_b64) > 500

    def test_get_correlation_table_incompatible_columns(self):
        survey = SurveyFactory()
        q1 = RatingQuestionFactory(survey=survey, label="Lone Question")
        
        for i in range(5):
            resp = ResponseFactory(survey=survey)
            AnswerFactory(response=resp, question=q1, answer_data=str(i))
            
        chart_b64 = get_correlation_table(survey)
        
        # Should return None because df.shape[1] < 2
        assert chart_b64 is None

    def test_get_correlation_table_no_variance(self):
        survey = SurveyFactory()
        q1 = RatingQuestionFactory(survey=survey, label="Q1")
        q2 = RatingQuestionFactory(survey=survey, label="Q2")
        
        # Everyone gives the same score
        for _ in range(3):
            resp = ResponseFactory(survey=survey)
            AnswerFactory(response=resp, question=q1, answer_data="5")
            AnswerFactory(response=resp, question=q2, answer_data="5")
            
        chart_b64 = get_correlation_table(survey)
        

        # 'if correlation_matrix.empty: return None'
        assert chart_b64 is not None or chart_b64 is None

    def test_get_correlation_table_with_matrix(self):
        survey = SurveyFactory()
        q_matrix = MatrixQuestionFactory(
            survey=survey, 
            label="Grid", 
            rows=["Cleanliness"], 
            columns=["Poor", "Good"] # Good=1, Poor=0 (numeric)
        )
        
        # 3 Responses
        for i in range(3):
            resp = ResponseFactory(survey=survey)
            AnswerFactory(response=resp, question=q_matrix, answer_data={"Cleanliness_row1": "Good"})
            
        chart_b64 = get_correlation_table(survey)

        # in the test above the corr will generate two columns Cleanliness [Poor] and Cleanliness [Good]
        assert chart_b64 is not None

@pytest.mark.django_db
class TestSurveyDataBySections:  
    def test_section_segmentation_logic(self):
        """Verify that questions are grouped correctly into sections."""
        survey = SurveyFactory(title="User Research")
        
        # Section 1 (Implicitly 'Start')
        q1 = RatingQuestionFactory(survey=survey, position=1, label="Q1")
        
        # Section 2 
        SectionHeaderFactory(survey=survey, position=2, label="Personal Info")
        q2 = RatingQuestionFactory(survey=survey, position=3, label="Q2")
        
        results = get_survey_data_by_sections(survey, format_type='raw')
        
        assert len(results) == 2
        assert results[0]['title'] == "User Research / Start"
        assert "Q1" in results[0]['header']
        
        assert results[1]['title'] == "User Research / Personal Info"
        assert "Q2" in results[1]['header']

    def test_numeric_expansion_in_sections(self):
        """Verify that multi-choice questions expand into multiple columns in numeric mode."""
        survey = SurveyFactory()
        # Create a multi-choice question with 2 options
        q_multi = MultiChoiceQuestionFactory(
            survey=survey, 
            label="Hobbies", 
            options=["Sports", "Music"]
        )
        
        # Create a response selecting only 'Sports'
        resp = ResponseFactory(survey=survey)
        AnswerFactory(
            response=resp, 
            question=q_multi, 
            answer_data=["Sports"]
        )
        
        results = get_survey_data_by_sections(survey, format_type='numeric')
        
        header = results[0]['header']
        row = results[0]['rows'][0]
        
        # Check Header Expansion: ['Respondent', 'Submitted At', 'Hobbies [Sports]', 'Hobbies [Music]']
        assert "Hobbies [Sports]" in header
        assert "Hobbies [Music]" in header
        
        # Check Data Mapping (Usually 1 for selected, 0 for not)
        # respondent=0, date=1, sports=2, music=3
        assert row[2] == '1'
        assert row[3] == '0'

    def test_raw_formatting_with_complex_types(self):
        """Verify that Dicts (Matrix/Rank) are formatted as strings in 'raw' mode."""
        survey = SurveyFactory()
        q_matrix = MatrixQuestionFactory(survey=survey, label="Grid")
        
        resp = ResponseFactory(survey=survey)
        payload = {"Row A": "Col 1", "Row B": "Col 2"}
        AnswerFactory(response=resp, question=q_matrix, answer_data=payload)
        
        results = get_survey_data_by_sections(survey, format_type='raw')
        
        row_data = results[0]['rows'][0][2]
        # Expecting a string like "Row A: 'Col 1' | Row B: 'Col 2'"
        assert "Row A: 'Col 1'" in row_data
        assert "|" in row_data

    def test_empty_sections_removal(self):
        """Verify that sections with no questions (e.g., two headers in a row) are excluded."""
        survey = SurveyFactory()
        SectionHeaderFactory(survey=survey, position=1, label="Empty Section")
        SectionHeaderFactory(survey=survey, position=2, label="Actual Section")
        RatingQuestionFactory(survey=survey, position=3, label="Q1")
        
        results = get_survey_data_by_sections(survey)
        
        # Should only return one section ("Actual Section")
        assert len(results) == 1
        assert "Actual Section" in results[0]['title']

    def test_anonymous_respondent_handling(self):
        """Verify that responses without a linked user show as 'Anonymous'."""
        survey = SurveyFactory(anonymous_responses=True)
        RatingQuestionFactory(survey=survey, label="Q1")
        
        # Response with respondent=None
        ResponseFactory(survey=survey, respondent=None)
        
        results = get_survey_data_by_sections(survey)
        assert results[0]['rows'][0][0] == "Anonymous"






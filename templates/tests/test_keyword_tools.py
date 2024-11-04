import pytest
import os
from unittest.mock import patch, MagicMock
from apps.agents.tools.keyword_tools.keyword_tools import (
    KeywordsForSiteTool,
    KeywordSuggestionsTool,
    KeywordIdeasTool,
    KeywordTools
)

@pytest.fixture(autouse=True)
def set_test_environment():
    with patch.dict(os.environ, {
        'DATAFORSEO_EMAIL': 'test@example.com',
        'DATAFORSEO_PASSWORD': 'test_password'
    }):
        yield

@pytest.fixture
def mock_requests_post():
    with patch('requests.post') as mock_post:
        yield mock_post

def test_keywords_for_site_tool(mock_requests_post):
    # Arrange
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tasks": [
            {
                "result": [
                    {
                        "keyword": "test keyword",
                        "search_volume": 1000,
                        "competition": 0.5,
                        "low_top_of_page_bid": 0.5,
                        "high_top_of_page_bid": 1.0,
                        "cpc": 0.75,
                        "monthly_searches": [
                            {"search_volume": 900},
                            {"search_volume": 1100}
                        ],
                        "keyword_annotations": {
                            "concepts": [
                                {"name": "Test Concept"}
                            ]
                        }
                    }
                ]
            }
        ]
    }
    mock_requests_post.return_value = mock_response

    tool = KeywordsForSiteTool()

    # Act
    result = tool._run("example.com")

    # Assert
    assert len(result) == 1
    assert "Keyword: test keyword" in result[0]
    assert "Avg. Monthly Searches: 1000" in result[0]
    assert "Min: 900, Max: 1100" in result[0]
    assert "Competition: 0.5" in result[0]
    assert "Low Top Bid: $0.50, High Top Bid: $1.00" in result[0]
    assert "CPC: $0.75" in result[0]
    assert "Concepts: Test Concept" in result[0]
    mock_requests_post.assert_called_once()

def test_keyword_suggestions_tool(mock_requests_post):
    # Arrange
    mock_response = MagicMock()
    mock_response.json.return_value = {"mocked": "response"}
    mock_requests_post.return_value = mock_response

    tool = KeywordSuggestionsTool()

    # Act
    # result = tool._run("test keyword")

    # # Assert
    # assert result == {"mocked": "response"}
    # mock_requests_post.assert_called_once()

def test_keyword_ideas_tool(mock_requests_post):
    # Arrange
    mock_response = MagicMock()
    mock_response.json.return_value = {"mocked": "response"}
    mock_requests_post.return_value = mock_response

    tool = KeywordIdeasTool()

    # # Act
    # result = tool._run(["test keyword 1", "test keyword 2"])

    # # Assert
    # assert result == {"mocked": "response"}
    # mock_requests_post.assert_called_once()

def test_keyword_tools_static_methods():
    # Test tools() method
    tools = KeywordTools.tools()
    assert len(tools) == 3
    assert isinstance(tools[0], KeywordsForSiteTool)
    assert isinstance(tools[1], KeywordSuggestionsTool)
    assert isinstance(tools[2], KeywordIdeasTool)

    # Test _dataforseo_credentials() method
    login, password = KeywordTools._dataforseo_credentials()
    assert login == 'test@example.com'
    assert password == 'test_password'

@pytest.mark.parametrize("tool_class,expected_url", [
    (KeywordsForSiteTool, "https://sandbox.dataforseo.com/v3/keywords_data/google_ads/keywords_for_site/live"),
    (KeywordSuggestionsTool, "https://sandbox.dataforseo.com/v3/dataforseo_labs/google/keyword_suggestions/live"),
    (KeywordIdeasTool, "https://sandbox.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live"),
])
def test_sandbox_url(mock_requests_post, tool_class, expected_url):
    # Arrange
    mock_response = MagicMock()
    mock_response.json.return_value = {"mocked": "response"}
    mock_requests_post.return_value = mock_response

    tool = tool_class()

    # Act
    if tool_class == KeywordsForSiteTool:
        tool._run("example.com")
    elif tool_class == KeywordSuggestionsTool:
        tool._run("test keyword")
    else:  # KeywordIdeasTool
        tool._run(["test keyword 1", "test keyword 2"])

    # Assert
    mock_requests_post.assert_called_once()
    actual_url = mock_requests_post.call_args[0][0]
    assert actual_url == expected_url

def test_dataforseo_credentials():
    login, password = KeywordTools._dataforseo_credentials()
    assert login == 'test@example.com'
    assert password == 'test_password'

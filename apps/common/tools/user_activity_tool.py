from typing import Any, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from apps.seo_manager.models import UserActivity
import logging
from typing import Optional

logger = logging.getLogger(__name__)

"""
You can use the UserActivityTool by 
 1. importing 'from apps.common.tools.user_activity_tool import user_activity_tool' and 
 2. calling its run method with the required arguments: 'result = user_activity_tool.run(user=user, category=category, action=action, client=client, details=details)'
"""

class UserActivityToolSchema(BaseModel):
    """Schema for UserActivityTool parameters"""
    query: str = Field(
        description="The query to search for user activity",
        default=""
    )
    user_id: Optional[int] = Field(
        description="User ID to filter activity",
        default=None
    )
    start_date: Optional[str] = Field(
        description="Start date in YYYY-MM-DD format",
        default=None
    )
    end_date: Optional[str] = Field(
        description="End date in YYYY-MM-DD format", 
        default=None
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "Find recent logins",
                    "user_id": 1,
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31"
                }
            ]
        }
    }

class UserActivityTool(BaseTool):
    name: str = "User Activity Tool"
    description: str = "Search and analyze user activity data"
    args_schema: type[UserActivityToolSchema] = UserActivityToolSchema

    def _run(self, query: str, user_id: Optional[int] = None, 
             start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
        """Run the tool synchronously"""
        try:
            # Your existing _run implementation
            return f"Found activity for query: {query}"
        except Exception as e:
            return f"Error searching user activity: {str(e)}"

    async def _arun(self, query: str, user_id: Optional[int] = None,
                    start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
        """Run the tool asynchronously"""
        return self._run(query, user_id, start_date, end_date)

# Initialize the tool instance
user_activity_tool = UserActivityTool()
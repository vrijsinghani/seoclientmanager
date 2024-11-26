import logging
from django.utils import timezone
from apps.seo_manager.models import Client
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)

class ClientDataManager:
    def __init__(self):
        pass

    @database_sync_to_async
    def get_client_data(self, client_id):
        """Get and format client data"""
        try:
            client = Client.objects.get(id=client_id)
            current_date = timezone.now().date()
            
            return {
                'client_id': client.id,
                'current_date': current_date.isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting client data: {str(e)}", exc_info=True)
            return None 
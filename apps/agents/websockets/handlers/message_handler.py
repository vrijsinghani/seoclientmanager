import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, consumer):
        self.consumer = consumer

    def format_table(self, content):
        """Format content as an HTML table if it contains tabular data"""
        try:
            # Check if content has table-like format (e.g., "Date | Users")
            if '|' in content and '-|-' in content:
                lines = [line.strip() for line in content.strip().split('\n')]
                
                # Find the header line
                header_line = None
                separator_line = None
                data_lines = []
                
                for i, line in enumerate(lines):
                    if '|' in line:
                        if header_line is None:
                            header_line = line
                        elif separator_line is None and '-|-' in line:
                            separator_line = line
                        else:
                            data_lines.append(line)
                
                if not header_line or not separator_line:
                    return content
                    
                # Process headers
                headers = [h.strip() for h in header_line.split('|') if h.strip()]
                
                # Create HTML table
                html = ['<table class="table"><thead><tr>']
                html.extend([f'<th>{h}</th>' for h in headers])
                html.append('</tr></thead><tbody>')
                
                # Process data rows
                for line in data_lines:
                    if '|' in line:
                        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                        if cells:
                            html.append('<tr>')
                            html.extend([f'<td>{cell}</td>' for cell in cells])
                            html.append('</tr>')
                
                html.append('</tbody></table>')
                
                # Log the formatted HTML
                formatted = '\n'.join(html)
                logger.debug(f"Formatted table HTML: {formatted}")
                return formatted
                
            return content
            
        except Exception as e:
            logger.error(f"Error formatting table: {str(e)}")
            return content

    def format_tool_output(self, content):
        """Format tool output with proper styling"""
        if isinstance(content, dict):
            return f'<div class="json-output">{json.dumps(content, indent=2)}</div>'
        return content

    def format_tool_usage(self, content):
        """Format tool usage messages"""
        if content.startswith('Using tool:'):
            tool_info = content.split('\n')
            formatted = f'''
            <div class="tool-usage">
                <i class="fas fa-tools"></i>
                <div>
                    <strong>{tool_info[0]}</strong>
                    <div class="tool-output">{tool_info[1] if len(tool_info) > 1 else ''}</div>
                </div>
            </div>
            '''
            return formatted
        return content

    async def handle_message(self, message, is_agent=True, error=False, is_stream=False):
        """Format and send a message"""
        try:
            # Format the message content
            content = str(message)
            
            if is_agent:
                # Log before formatting
                logger.debug(f"Before formatting: {content[:200]}")
                
                # Apply different formatting based on content type
                content = self.format_table(content)
                content = self.format_tool_usage(content)
                content = self.format_tool_output(content)
                
                # Log after formatting
                logger.debug(f"After formatting: {content[:200]}")
            
            response_data = {
                'type': 'agent_message' if is_agent else 'user_message',
                'message': content,
                'is_agent': bool(is_agent),
                'error': bool(error),
                'is_stream': bool(is_stream),
                'timestamp': datetime.now().isoformat()
            }
            
            # Log final response data
            logger.debug(f"Sending response: {response_data}")
            
            await self.consumer.send_json(response_data)
            
        except Exception as e:
            logger.error(f"Error in message handler: {str(e)}", exc_info=True)
            await self.consumer.send_json({
                'type': 'error',
                'error': True,
                'message': 'Error processing message'
            })

    async def handle_keep_alive(self):
        """Handle keep-alive messages"""
        await self.consumer.send_json({
            'type': 'keep_alive_response',
            'timestamp': datetime.now().isoformat()
        }) 
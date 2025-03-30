import re
from typing import Optional

def escape_special_chars(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2"""
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in chars:
        text = text.replace(char, f'\\{char}')
    return text

def process_markdown(text: str) -> str:
    """
    Convert HTML to Telegram MarkdownV2 format
    """
    try:
        # Remove HTML tags and convert to Markdown
        text = text.replace('<p>', '')
        text = text.replace('</p>', '\n\n')
        text = text.replace('<br />', '\n')
        text = text.replace('<br>', '\n')
        
        # Convert basic formatting
        text = text.replace('<b>', '*').replace('</b>', '*')
        text = text.replace('<strong>', '*').replace('</strong>', '*')
        text = text.replace('<i>', '_').replace('</i>', '_')
        text = text.replace('<em>', '_').replace('</em>', '_')
        text = text.replace('<u>', '__').replace('</u>', '__')
        text = text.replace('<s>', '~').replace('</s>', '~')
        text = text.replace('<strike>', '~').replace('</strike>', '~')
        text = text.replace('<del>', '~').replace('</del>', '~')
        
        # Clean up multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Escape special characters
        text = escape_special_chars(text)
        
        return text.strip()
    except Exception as e:
        # If processing fails, return plain text
        return text.replace('<p>', '').replace('</p>', '\n').replace('<br>', '\n')
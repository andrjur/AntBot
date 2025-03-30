import re

def process_markdown_simple(text: str) -> str:
    """Process text for basic Telegram Markdown (v1) format"""
    try:
        # Remove HTML tags
        text = text.replace('<p>', '').replace('</p>', '\n')
        text = text.replace('<br />', '\n').replace('<br>', '\n')
        
        # Convert HTML to Markdown v1
        text = text.replace('<b>', '*').replace('</b>', '*')
        text = text.replace('<strong>', '*').replace('</strong>', '*')
        text = text.replace('<i>', '_').replace('</i>', '_')
        text = text.replace('<em>', '_').replace('</em>', '_')
        
        # Clean up multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Fix lists (simple dashes, no escaping needed)
        text = text.replace('—', '-')
        
        return text.strip()
    except Exception as e:
        return text

# Keep the old function but use the new one in handlers
def process_markdown(text: str) -> str:
    """Process text for Telegram MarkdownV2 format"""
    try:
        # First handle markdown elements
        markdown_pairs = [
            ('*', '※'), # Bold
            ('_', '¤'),  # Italic
            ('~', '±'),  # Strikethrough
            ('__', '§'), # Underline
        ]
        
        # Replace markdown with temporary symbols
        for md, temp in markdown_pairs:
            # Find pairs of markdown symbols and replace them
            pattern = f'\\{md}(.*?)\\{md}'
            matches = re.finditer(pattern, text)
            for match in reversed(list(matches)):
                text = text[:match.start()] + temp + match.group(1) + temp + text[match.end():]
        
        # Escape special characters
        special_chars = r'_*[]()~`>#+-=|{}.!'
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        
        # Restore markdown symbols
        for md, temp in markdown_pairs:
            text = text.replace(temp, md)
            
        # Fix lists (only at start of lines)
        text = re.sub(r'(?m)^[-—•]\s', '\\- ', text)
        text = re.sub(r'(?m)^(\d+)\.', r'\1\.', text)
        
        return text.strip()
    except Exception as e:
        # On error, return basic escaped text
        return text.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]')
import re
from multi_doc_chat.logging import GLOBAL_LOGGER as log

def clean_extracted_text(text: str) -> str:
    if not text:
        return ""
    
    original_length = len(text)

    # Fix hyphenated words broken across lines: ex:  "artifi-\ncial" -> "artificial
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)

    # Remove weird unicode artifacts
    text = text.replace('\u200b', '') # zero width space
    text = text.replace('\x0c','') # from feed/page break
    text = text.replace('\x00','') #Null bytes

    # Normalize whitespace (In Pdf whitespaces act as \n\n\n\n\n\n\n) it converts multiple space to single space.
    text = re.sub(r'[ \t]+', ' ', text)

    # Normalize newlines (Convert 3+ consecutive newlines into exactly 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Strip leading and trailing whitespace
    text = text.strip()

    cleaned_length = len(text)
    if original_length != cleaned_length:
        log.debug("Text Cleaned",
                  original_char = original_length,
                  clean_char = cleaned_length,
                  remove_char = original_length - cleaned_length)
    return text
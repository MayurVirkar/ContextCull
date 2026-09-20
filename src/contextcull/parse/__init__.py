"""TEP Block Parsers package."""

from contextcull.parse.code import is_code_input, parse_code_blocks
from contextcull.parse.email import is_email, parse_email_blocks
from contextcull.parse.logs import is_test_log, parse_test_log_blocks
from contextcull.parse.markdown import parse_markdown_blocks
from contextcull.parse.text import parse_plain_text_blocks

__all__ = [
    "is_code_input",
    "is_email",
    "is_test_log",
    "parse_code_blocks",
    "parse_email_blocks",
    "parse_markdown_blocks",
    "parse_plain_text_blocks",
    "parse_test_log_blocks",
]

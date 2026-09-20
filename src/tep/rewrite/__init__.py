"""TEP Rewrite package."""

from tep.rewrite.engine import RewriteEngine
from tep.rewrite.rules import ABBREVIATIONS, PHRASE_RULES, PhraseRule

__all__ = ["ABBREVIATIONS", "PHRASE_RULES", "PhraseRule", "RewriteEngine"]

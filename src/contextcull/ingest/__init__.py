"""TEP Ingestion package."""

from contextcull.ingest.decoder import IngestionResult, clean_char_to_byte_span, ingest_bytes

__all__ = ["IngestionResult", "clean_char_to_byte_span", "ingest_bytes"]

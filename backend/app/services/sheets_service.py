"""
SevaSetu — Sheets Service
Google Sheets integration to sync community need reports from NGO spreadsheets.

Architecture:
  - If GOOGLE_APPLICATION_CREDENTIALS is set → real Sheets API v4
  - If not set → graceful degradation with clear error messages

Usage:
  await sheets_service.register_sheet("1BxiMVs0...", org_id, db)
  result = await sheets_service.sync_sheet(org_id, column_mapping, db)
"""

import logging
from uuid import UUID
from typing import Dict, Any, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.db_models import Organization

logger = logging.getLogger(__name__)
settings = get_settings()


class SheetsService:
    """Google Sheets API v4 integration for periodic need data sync."""

    def __init__(self):
        self._service = None
        self._available = False

        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build

                credentials = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_APPLICATION_CREDENTIALS,
                    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
                )
                self._service = build("sheets", "v4", credentials=credentials)
                self._available = True
                logger.info("✅ Google Sheets API client initialized")
            except Exception as e:
                logger.warning(f"⚠️ Sheets API init failed: {e}")
        else:
            logger.info("ℹ️ No GOOGLE_APPLICATION_CREDENTIALS — Sheets sync disabled")

    @property
    def is_available(self) -> bool:
        return self._available

    async def register_sheet(
        self,
        sheet_id: str,
        org_id: UUID,
        db: AsyncSession,
    ) -> bool:
        """Link a Google Sheet to an organization for automatic sync."""
        result = await db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        org = result.scalar_one_or_none()
        if not org:
            return False

        org.sheet_id = sheet_id
        await db.commit()
        logger.info(f"📊 Linked sheet {sheet_id} to org {org.name}")
        return True

    async def sync_sheet(
        self,
        org_id: UUID,
        db: AsyncSession,
        column_mapping: Optional[Dict[str, str]] = None,
        sheet_range: str = "A2:Z",
    ) -> Dict[str, Any]:
        """
        Pull all rows from an organization's linked Google Sheet.
        Pass the mapped rows to the ingestion pipeline.

        column_mapping example:
          {"A": "title", "B": "description", "C": "location", "D": "need_type"}
        """
        if not self._available:
            return {
                "status": "error",
                "message": "Sheets API not configured. Set GOOGLE_APPLICATION_CREDENTIALS.",
            }

        # Get org and its linked sheet
        result = await db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        org = result.scalar_one_or_none()

        if not org or not org.sheet_id:
            return {
                "status": "error",
                "message": "Organization or linked sheet not found.",
            }

        try:
            import asyncio

            # Sheets API is synchronous — run in thread pool
            sheet_data = await asyncio.to_thread(
                self._fetch_sheet_data, org.sheet_id, sheet_range
            )

            if not sheet_data:
                return {
                    "status": "success",
                    "synced_rows": 0,
                    "message": "No new rows found in sheet.",
                }

            # Map columns to need fields
            default_mapping = {
                "A": "title",
                "B": "description",
                "C": "location",
                "D": "need_type",
                "E": "urgency",
                "F": "affected_count",
            }
            mapping = column_mapping or default_mapping
            mapped_rows = self._map_rows(sheet_data, mapping)

            # Ingest each row through the pipeline
            ingested = 0
            errors = 0

            for row in mapped_rows:
                try:
                    raw_text = (
                        f"{row.get('title', '')}. "
                        f"{row.get('description', '')}. "
                        f"Location: {row.get('location', 'unknown')}. "
                        f"Type: {row.get('need_type', 'general')}."
                    )

                    from app.routes.ingestion_routes import _ingest_text
                    await _ingest_text(
                        raw_text=raw_text,
                        source_channel="sheets",
                        db=db,
                    )
                    ingested += 1

                except Exception as e:
                    logger.warning(f"Sheet row ingestion failed: {e}")
                    errors += 1

            await db.commit()

            logger.info(
                f"📊 Sheet sync for org {org.name}: "
                f"{ingested} ingested, {errors} errors, "
                f"{len(sheet_data)} total rows"
            )

            return {
                "status": "success",
                "synced_rows": ingested,
                "errors": errors,
                "total_rows": len(sheet_data),
            }

        except Exception as e:
            logger.error(f"Sheet sync failed for org {org_id}: {e}")
            return {"status": "error", "message": str(e)}

    def _fetch_sheet_data(
        self, sheet_id: str, sheet_range: str
    ) -> List[List[str]]:
        """
        Synchronous call to Google Sheets API v4 to fetch cell values.
        Called via asyncio.to_thread().
        """
        try:
            result = (
                self._service.spreadsheets()
                .values()
                .get(spreadsheetId=sheet_id, range=sheet_range)
                .execute()
            )
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Sheets API fetch failed: {e}")
            return []

    def _map_rows(
        self,
        rows: List[List[str]],
        column_mapping: Dict[str, str],
    ) -> List[Dict[str, str]]:
        """
        Map spreadsheet columns (A, B, C...) to need field names.
        """
        col_to_idx = {col: ord(col.upper()) - ord("A") for col in column_mapping}
        mapped = []

        for row in rows:
            entry = {}
            for col, field_name in column_mapping.items():
                idx = col_to_idx.get(col, -1)
                if 0 <= idx < len(row):
                    entry[field_name] = row[idx].strip()
            if entry.get("title") or entry.get("description"):
                mapped.append(entry)

        return mapped


# Singleton
sheets_service = SheetsService()

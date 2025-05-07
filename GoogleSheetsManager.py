"""
Google Sheets Manager
Centralized service for all spreadsheet operations with:
- Connection management
- Batch processing
- Automatic retries
- Data validation
"""

import gspread
from google.oauth2.service_account import Credentials
from typing import Dict, List, Union, Optional
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential
import time
from pydantic import BaseModel, ValidationError

# Data Models
class SheetSchema(BaseModel):
    name: str
    headers: List[str]
    id_col: str = "id"

@dataclass
class BatchUpdate:
    range: str
    values: List[List[Union[str, int, float]]]

class GoogleSheetsManager:
    def __init__(self, credentials: Dict, spreadsheet_id: str):
        """
        Args:
            credentials: Google Service Account credentials dict
            spreadsheet_id: Target spreadsheet ID
        """
        self.credentials = credentials
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        self.spreadsheet = None
        self._sheet_cache = {}  # worksheet_name: worksheet
        self._schema_registry = {}  # sheet_name: SheetSchema
        self.connect()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def connect(self) -> None:
        """Establish authenticated connection"""
        try:
            creds = Credentials.from_service_account_info(
                self.credentials,
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            print(f"Connected to spreadsheet: {self.spreadsheet.title}")
        except Exception as e:
            print(f"Connection failed: {str(e)}")
            raise

    def register_schema(self, schema: SheetSchema) -> None:
        """Register data schema for a sheet"""
        self._schema_registry[schema.name] = schema

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    def get_worksheet(self, sheet_name: str) -> gspread.Worksheet:
        """Get worksheet with caching"""
        if sheet_name in self._sheet_cache:
            return self._sheet_cache[sheet_name]

        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            self._sheet_cache[sheet_name] = worksheet
            return worksheet
        except gspread.WorksheetNotFound:
            print(f"Sheet {sheet_name} not found, creating...")
            worksheet = self.spreadsheet.add_worksheet(
                title=sheet_name, 
                rows=1000, 
                cols=26
            )
            self._initialize_sheet_headers(worksheet, sheet_name)
            return worksheet

    def _initialize_sheet_headers(self, 
                               worksheet: gspread.Worksheet, 
                               sheet_name: str) -> None:
        """Set up headers if sheet is new"""
        if sheet_name in self._schema_registry:
            headers = self._schema_registry[sheet_name].headers
            worksheet.update([headers], range_name="A1")
            print(f"Initialized headers for {sheet_name}: {headers}")

    def validate_row(self, sheet_name: str, row: Dict) -> bool:
        """Validate data against registered schema"""
        if sheet_name not in self._schema_registry:
            return True  # No validation if no schema
        
        try:
            self._schema_registry[sheet_name].model_validate(row)
            return True
        except ValidationError as e:
            print(f"Validation failed for {sheet_name}: {str(e)}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(gspread.exceptions.APIError)
    )
    def append_rows(self, 
                  sheet_name: str, 
                  rows: List[Dict],
                  batch_size: int = 100) -> Dict:
        """
        Append multiple rows with validation
        
        Args:
            sheet_name: Target worksheet
            rows: List of dictionaries (keys must match headers)
            batch_size: Rows per API call
            
        Returns:
            {
                "success": int,
                "failed": int,
                "batches": int,
                "errors": List[str]
            }
        """
        worksheet = self.get_worksheet(sheet_name)
        schema = self._schema_registry.get(sheet_name)
        results = {"success": 0, "failed": 0, "batches": 0, "errors": []}
        
        # Convert dicts to lists in header order
        if schema:
            header_order = schema.headers
        else:
            header_order = list(rows[0].keys()) if rows else []
        
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            validated_values = []
            
            for row in batch:
                if self.validate_row(sheet_name, row):
                    validated_values.append([
                        str(row.get(col, "")) for col in header_order
                    ])
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Row {i} validation failed")
            
            if validated_values:
                worksheet.append_rows(validated_values)
                results["batches"] += 1
                time.sleep(1)  # Rate limiting
            
        return results

    def batch_update(self, 
                   sheet_name: str, 
                   updates: List[BatchUpdate]) -> Dict:
        """
        Perform multiple updates in one API call
        
        Args:
            sheet_name: Target worksheet
            updates: List of BatchUpdate objects
            
        Returns:
            {
                "updated_cells": int,
                "failed_ranges": List[str]
            }
        """
        worksheet = self.get_worksheet(sheet_name)
        body = {
            "valueInputOption": "USER_ENTERED",
            "data": [
                {
                    "range": update.range,
                    "values": update.values
                } for update in updates
            ]
        }
        
        try:
            response = worksheet.batch_update(body)
            return {
                "updated_cells": sum(
                    len(update.values) * len(update.values[0]) 
                    for update in updates
                ),
                "failed_ranges": []
            }
        except Exception as e:
            print(f"Batch update failed: {str(e)}")
            return {
                "updated_cells": 0,
                "failed_ranges": [update.range for update in updates]
            }

    def find_rows(self, 
                 sheet_name: str, 
                 conditions: Dict[str, str]) -> List[Dict]:
        """
        Find rows matching conditions (exact match)
        
        Args:
            sheet_name: Worksheet to search
            conditions: {"column": "value"} pairs
            
        Returns:
            List of matching rows as dictionaries
        """
        worksheet = self.get_worksheet(sheet_name)
        all_records = worksheet.get_all_records()
        
        matches = []
        for record in all_records:
            if all(
                str(record.get(k, "") == str(v) 
                for k, v in conditions.items()
            ):
                matches.append(record)
        
        return matches

    def update_or_create(self, 
                       sheet_name: str, 
                       rows: List[Dict],
                       id_column: str = "id") -> Dict:
        """
        Upsert operation - updates existing or appends new
        
        Args:
            sheet_name: Target worksheet
            rows: Data to upsert
            id_column: Column used to identify existing records
            
        Returns:
            {
                "updated": int,
                "created": int,
                "errors": int
            }
        """
        worksheet = self.get_worksheet(sheet_name)
        existing_ids = {
            str(row[id_column]): idx + 2  # +2 for header and 1-based index
            for idx, row in enumerate(worksheet.get_all_records())
            if id_column in row
        }
        
        results = {"updated": 0, "created": 0, "errors": 0}
        updates = []
        
        for row in rows:
            if not self.validate_row(sheet_name, row):
                results["errors"] += 1
                continue
                
            row_id = str(row.get(id_column))
            if row_id in existing_ids:
                # Update existing
                row_num = existing_ids[row_id]
                updates.append(BatchUpdate(
                    range=f"A{row_num}:{chr(64 + len(row))}{row_num}",
                    values=[[row.get(col, "") for col in row.keys()]]
                ))
                results["updated"] += 1
            else:
                # Append new
                self.append_rows(sheet_name, [row])
                results["created"] += 1
        
        if updates:
            self.batch_update(sheet_name, updates)
            
        return results

    def backup_sheet(self, sheet_name: str) -> List[List[str]]:
        """Get all data as raw values for backup"""
        worksheet = self.get_worksheet(sheet_name)
        return worksheet.get_all_values()
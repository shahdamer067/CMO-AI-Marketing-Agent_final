"""
============================================================
CMO.AI — Database Layer (MongoDB)
============================================================
Handles all MongoDB operations for the marketing agent.

Collections:
  - brand_profiles     → written by branding agent, READ here
  - marketing_strategies → written HERE, read by content agent

Usage:
    db = MarketingDB()
    brand = db.get_brand_profile(user_id="abc123")
    db.save_marketing_strategy(user_id="abc123", strategy=strategy_dict)
============================================================
"""

import os
from datetime import datetime
from typing import Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from dotenv import load_dotenv

load_dotenv()


class MarketingDB:
    """
    Database interface for the Marketing Strategy Agent.
    Connects to MongoDB and handles brand/strategy documents.
    """

    def __init__(self):
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
        db_name = os.getenv("MONGODB_DB_NAME", "cmo_ai")

        self.client = MongoClient(uri)
        self.db = self.client[db_name]

        # Collection references
        self.brand_col = self.db[os.getenv("BRAND_COLLECTION", "brand_profiles")]
        self.strategy_col = self.db[os.getenv("STRATEGY_COLLECTION", "marketing_strategies")]

        print(f"[DB] Connected to MongoDB → database: '{db_name}'")

    # ─────────────────────────────────────────
    # READ: Brand Profile (from branding agent)
    # ─────────────────────────────────────────

    def get_brand_profile(self, user_id: str) -> Optional[dict]:
        """
        Fetches the brand identity document created by the branding agent.

        Args:
            user_id: The unique user/session identifier

        Returns:
            dict with brand data, or None if not found
        """
        try:
            doc = self.brand_col.find_one(
                {"user_id": user_id},
                sort=[("created_at", -1)]  # Get the most recent profile
            )

            if not doc:
                print(f"[DB] No brand profile found for user_id: {user_id}")
                return None

            # Remove MongoDB internal _id before returning
            doc.pop("_id", None)
            print(f"[DB] Brand profile loaded for: {doc.get('brand_name', 'Unknown')}")
            return doc

        except (ConnectionFailure, OperationFailure) as e:
            print(f"[DB ERROR] Failed to fetch brand profile: {e}")
            return None

    # ─────────────────────────────────────────
    # WRITE: Marketing Strategy (for other agents)
    # ─────────────────────────────────────────

    def save_marketing_strategy(self, user_id: str, strategy: dict) -> bool:
        """
        Saves the generated marketing strategy to MongoDB.
        Other agents (content, image, video) will read from here.

        Args:
            user_id: The unique user/session identifier
            strategy: The full strategy dict from the agent

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            strategy["user_id"] = user_id
            strategy["saved_at"] = datetime.utcnow()

            # Upsert: update if exists, insert if new
            result = self.strategy_col.update_one(
                {"user_id": user_id},
                {"$set": strategy},
                upsert=True
            )

            if result.upserted_id or result.modified_count > 0:
                print(f"[DB] Marketing strategy saved for user_id: {user_id}")
                return True
            return False

        except (ConnectionFailure, OperationFailure) as e:
            print(f"[DB ERROR] Failed to save strategy: {e}")
            return False

    def get_marketing_strategy(self, user_id: str) -> Optional[dict]:
        """
        Fetches an existing marketing strategy (for updates or agent reads).

        Args:
            user_id: The unique user/session identifier

        Returns:
            dict with strategy data, or None if not found
        """
        try:
            doc = self.strategy_col.find_one({"user_id": user_id})
            if doc:
                doc.pop("_id", None)
            return doc
        except (ConnectionFailure, OperationFailure) as e:
            print(f"[DB ERROR] Failed to fetch strategy: {e}")
            return None

    def save_brand_profile(self, user_id: str, profile: dict) -> bool:
        """
        Saves a brand profile built from Mode 2 intake conversation.
        This means next time the user visits, Mode 1 will kick in automatically.

        Args:
            user_id: Unique user identifier
            profile: Brand profile dict built during intake

        Returns:
            True if saved successfully
        """
        try:
            profile["user_id"] = user_id
            profile["saved_at"] = datetime.utcnow()
            result = self.brand_col.update_one(
                {"user_id": user_id},
                {"$set": profile},
                upsert=True
            )
            if result.upserted_id or result.modified_count > 0:
                print(f"[DB] Brand profile (from intake) saved for user_id: {user_id}")
                return True
            return False
        except (ConnectionFailure, OperationFailure) as e:
            print(f"[DB ERROR] Failed to save brand profile: {e}")
            return False

    def close(self):
        """Always call this when done to close the MongoDB connection."""
        self.client.close()
        print("[DB] MongoDB connection closed.")
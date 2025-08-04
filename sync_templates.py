#!/usr/bin/env python3
"""Synchronize PROTOCOL_TEMPLATES & servers from config.settings into database.

Usage:
    python sync_templates.py

It calls init_db() to ensure tables exist and then init_default_data()
which upserts servers and config templates.  Handy after editing
config/settings.py without restarting full bot.
"""
import asyncio
from database.database import init_db, init_default_data

async def main():
    init_db()
    await init_default_data()
    print("✅ Database synchronized with config.settings.PROTOCOL_TEMPLATES and servers list.")

if __name__ == "__main__":
    asyncio.run(main()) 
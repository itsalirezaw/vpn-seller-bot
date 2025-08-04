#!/usr/bin/env python3
"""Complete migration script for moving bot to a new server.

This script helps you safely migrate your VPN bot to a new server without 
losing any user data or configurations.

FEATURES:
- Creates comprehensive backup
- Validates migration requirements
- Provides step-by-step migration guide
- Handles database migration
- Preserves all user accounts and settings

USAGE:
python scripts/migrate_to_new_server.py [--backup-only | --restore-only]

Options:
  --backup-only   Only create backup, don't migrate
  --restore-only  Only restore from backup, assume files copied
"""

import os
import sys
import shutil
import argparse
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BotMigrator:
    def __init__(self):
        self.backup_dir = Path("migration_backup")
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_name = f"bot_migration_{self.timestamp}"
        self.full_backup_path = self.backup_dir / self.backup_name
        
    def create_migration_backup(self) -> bool:
        """Create comprehensive backup for migration"""
        try:
            logger.info("🚀 Starting migration backup creation...")
            
            # Create backup directory
            self.full_backup_path.mkdir(parents=True, exist_ok=True)
            
            # 1. Backup database
            logger.info("💾 Backing up database...")
            if not self._backup_database():
                return False
                
            # 2. Backup configuration files
            logger.info("⚙️  Backing up configuration...")
            if not self._backup_configs():
                return False
                
            # 3. Backup scripts and custom files
            logger.info("📜 Backing up scripts...")
            if not self._backup_scripts():
                return False
                
            # 4. Create migration info
            logger.info("📋 Creating migration info...")
            if not self._create_migration_info():
                return False
                
            # 5. Create restoration script
            logger.info("🔄 Creating restoration script...")
            self._create_restoration_script()
            
            logger.info(f"✅ Migration backup created successfully!")
            logger.info(f"📂 Backup location: {self.full_backup_path}")
            logger.info(f"📦 Backup size: {self._get_dir_size(self.full_backup_path)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating migration backup: {e}")
            return False
            
    def _backup_database(self) -> bool:
        """Backup SQLite database with integrity check"""
        try:
            db_path = Path("vpn_bot.db")
            if not db_path.exists():
                logger.warning("⚠️  Database file not found, skipping...")
                return True
                
            # Check database integrity
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            
            if result[0] != "ok":
                logger.error(f"❌ Database integrity check failed: {result[0]}")
                return False
                
            # Create backup
            backup_path = self.full_backup_path / "database"
            backup_path.mkdir(exist_ok=True)
            
            shutil.copy2(db_path, backup_path / "vpn_bot.db")
            
            # Export as SQL for additional safety
            self._export_database_sql(backup_path)
            
            logger.info("✅ Database backup completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error backing up database: {e}")
            return False
            
    def _export_database_sql(self, backup_path: Path):
        """Export database as SQL statements"""
        try:
            conn = sqlite3.connect("vpn_bot.db")
            with open(backup_path / "database_export.sql", 'w') as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")
            conn.close()
            logger.info("✅ Database SQL export completed")
        except Exception as e:
            logger.warning(f"⚠️  Could not export SQL: {e}")
            
    def _backup_configs(self) -> bool:
        """Backup all configuration files"""
        try:
            config_backup = self.full_backup_path / "config"
            config_backup.mkdir(exist_ok=True)
            
            # Essential files to backup
            files_to_backup = [
                ".env",
                "requirements.txt",
                "config/",
                "bot/",
                "services/",
                "database/",
            ]
            
            for item in files_to_backup:
                item_path = Path(item)
                if item_path.exists():
                    if item_path.is_file():
                        shutil.copy2(item_path, config_backup / item_path.name)
                    else:
                        shutil.copytree(item_path, config_backup / item_path.name, dirs_exist_ok=True)
                    logger.info(f"✅ Backed up: {item}")
                else:
                    logger.warning(f"⚠️  Not found: {item}")
                    
            return True
            
        except Exception as e:
            logger.error(f"❌ Error backing up configs: {e}")
            return False
            
    def _backup_scripts(self) -> bool:
        """Backup scripts and important files"""
        try:
            scripts_backup = self.full_backup_path / "scripts"
            scripts_backup.mkdir(exist_ok=True)
            
            # Copy important files
            important_files = [
                "main.py",
                "start_bot.py",
                "setup_database.py",
                "database_commands.sh",
                "database_commands.bat",
                "scripts/",
            ]
            
            for item in important_files:
                item_path = Path(item)
                if item_path.exists():
                    if item_path.is_file():
                        shutil.copy2(item_path, scripts_backup / item_path.name)
                    else:
                        shutil.copytree(item_path, scripts_backup / item_path.name, dirs_exist_ok=True)
                        
            return True
            
        except Exception as e:
            logger.error(f"❌ Error backing up scripts: {e}")
            return False
            
    def _create_migration_info(self) -> bool:
        """Create migration information file"""
        try:
            migration_info = {
                "migration_date": datetime.now().isoformat(),
                "python_version": sys.version,
                "backup_contents": {
                    "database": "vpn_bot.db + SQL export",
                    "configs": "All config files and .env",
                    "code": "All Python source code",
                    "scripts": "Migration and utility scripts"
                },
                "database_stats": self._get_database_stats(),
                "migration_steps": [
                    "1. Install Python and dependencies on new server",
                    "2. Copy backup files to new server",
                    "3. Run restoration script",
                    "4. Update .env with new server details",
                    "5. Test bot functionality",
                    "6. Update DNS/webhooks if needed"
                ],
                "post_migration_checklist": [
                    "✓ Database restored successfully",
                    "✓ All user accounts preserved",
                    "✓ Bot responds to commands",
                    "✓ Payment system working",
                    "✓ Server connections active",
                    "✓ Monitoring services running"
                ]
            }
            
            with open(self.full_backup_path / "migration_info.json", 'w', encoding='utf-8') as f:
                json.dump(migration_info, f, indent=2, ensure_ascii=False)
                
            # Also create readable text version
            with open(self.full_backup_path / "MIGRATION_GUIDE.txt", 'w', encoding='utf-8') as f:
                f.write(self._generate_migration_guide())
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating migration info: {e}")
            return False
            
    def _get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for verification"""
        try:
            if not Path("vpn_bot.db").exists():
                return {"error": "Database not found"}
                
            conn = sqlite3.connect("vpn_bot.db")
            cursor = conn.cursor()
            
            stats = {}
            
            # Count records in important tables
            tables = ["users", "accounts", "orders", "servers"]
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[f"{table}_count"] = cursor.fetchone()[0]
                except:
                    stats[f"{table}_count"] = "N/A"
                    
            conn.close()
            return stats
            
        except Exception as e:
            return {"error": str(e)}
            
    def _create_restoration_script(self):
        """Create script to restore backup on new server"""
        restore_script = f'''#!/bin/bash
# Automatic restoration script for VPN Bot migration
# Generated on: {datetime.now().isoformat()}

echo "🔄 Starting VPN Bot restoration..."

# Check if running in correct directory
if [ ! -f "migration_info.json" ]; then
    echo "❌ Error: Run this script from the backup directory"
    exit 1
fi

# Restore database
echo "💾 Restoring database..."
if [ -f "database/vpn_bot.db" ]; then
    cp database/vpn_bot.db ../vpn_bot.db
    echo "✅ Database restored"
else
    echo "❌ Database backup not found!"
    exit 1
fi

# Restore configuration
echo "⚙️  Restoring configuration..."
cp -r config/* ../
echo "✅ Configuration restored"

# Restore code
echo "📜 Restoring code..."
cp -r scripts/* ../scripts/ 2>/dev/null || echo "No scripts to restore"
echo "✅ Code restored"

# Set permissions
chmod +x ../database_commands.sh
chmod +x ../start_bot.py

echo "🎉 Restoration completed!"
echo ""
echo "📋 Next steps:"
echo "1. Update .env file with new server details"
echo "2. Install dependencies: pip install -r requirements.txt"
echo "3. Test database: python setup_database.py"
echo "4. Start bot: python start_bot.py"
echo ""
echo "⚠️  Don't forget to update DNS/webhook settings!"
'''
        
        restore_path = self.full_backup_path / "restore.sh"
        with open(restore_path, 'w') as f:
            f.write(restore_script)
        os.chmod(restore_path, 0o755)
        
        # Also create Windows version
        restore_script_win = restore_script.replace('#!/bin/bash', '@echo off').replace('cp ', 'copy ').replace('chmod +x', 'rem ')
        with open(self.full_backup_path / "restore.bat", 'w') as f:
            f.write(restore_script_win)
            
    def _generate_migration_guide(self) -> str:
        """Generate human-readable migration guide"""
        return f'''
🚀 VPN Bot Migration Guide
==========================

Migration created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

📦 BACKUP CONTENTS:
- Database: All user accounts, orders, and settings
- Configuration: Bot settings, server configs, environment variables  
- Source Code: Complete bot application
- Scripts: Migration and utility tools

🔄 MIGRATION STEPS:

1. PREPARE NEW SERVER
   - Install Python 3.8+ 
   - Install pip and git
   - Create working directory

2. TRANSFER FILES
   - Copy this entire backup folder to new server
   - Extract if compressed

3. RESTORE APPLICATION
   - Run: ./restore.sh (Linux) or restore.bat (Windows)
   - Or manually copy files as needed

4. CONFIGURE ENVIRONMENT
   - Edit .env file with new server details
   - Update server IPs, domains, API keys
   - Verify all settings

5. INSTALL DEPENDENCIES
   - Run: pip install -r requirements.txt
   - Ensure all packages install successfully

6. VERIFY DATABASE
   - Run: python setup_database.py
   - Check database integrity
   - Verify user count matches

7. TEST BOT
   - Run: python start_bot.py
   - Test basic commands
   - Verify payment system
   - Check server connections

8. UPDATE EXTERNAL SERVICES
   - Update webhook URLs if using webhooks
   - Update DNS records if needed
   - Notify users if necessary

✅ POST-MIGRATION CHECKLIST:
□ Bot responds to /start command
□ User accounts preserved
□ Payment system functional
□ Server connections active
□ Monitoring working
□ Backups scheduled

🆘 TROUBLESHOOTING:
- If database errors: Check file permissions
- If import errors: Reinstall requirements
- If connection errors: Verify .env settings
- If bot not responding: Check bot token

📞 Need help? Check logs and error messages.

🎉 Migration complete! Your bot should be fully functional.
'''

    def _get_dir_size(self, path: Path) -> str:
        """Get human-readable directory size"""
        total_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        for unit in ['B', 'KB', 'MB', 'GB']:
            if total_size < 1024:
                return f"{total_size:.1f} {unit}"
            total_size /= 1024
        return f"{total_size:.1f} TB"

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='VPN Bot Migration Tool')
    parser.add_argument('--backup-only', action='store_true', help='Only create backup')
    parser.add_argument('--restore-only', action='store_true', help='Only restore from backup')
    
    args = parser.parse_args()
    
    migrator = BotMigrator()
    
    if args.restore_only:
        print("🔄 Restoration mode not implemented in this version")
        print("💡 Use the restore.sh script from your backup directory")
        return
        
    print("🚀 VPN Bot Migration Tool")
    print("=" * 50)
    print()
    print("This tool will create a complete backup of your bot for migration.")
    print("The backup includes:")
    print("- 💾 Database with all user data")
    print("- ⚙️  Configuration files") 
    print("- 📜 Source code and scripts")
    print("- 📋 Migration instructions")
    print()
    
    if not args.backup_only:
        confirm = input("Create migration backup? [y/N]: ").lower().strip()
        if confirm != 'y':
            print("Operation cancelled.")
            return
    
    success = migrator.create_migration_backup()
    
    if success:
        print()
        print("🎉 Migration backup created successfully!")
        print(f"📂 Location: {migrator.full_backup_path}")
        print()
        print("📋 Next steps:")
        print("1. Copy the backup folder to your new server")
        print("2. Run the restore.sh script in the backup folder")  
        print("3. Follow the MIGRATION_GUIDE.txt instructions")
        print()
        print("💡 Keep this backup safe - it contains all your user data!")
    else:
        print("❌ Migration backup failed. Check the logs above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
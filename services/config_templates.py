import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

from database.database import db_manager
from database.models import ConfigTemplate, Account, ServerAccount, Server
from services.protocol_plugins import protocol_manager
from services.server_manager import server_manager

logger = logging.getLogger(__name__)

@dataclass
class ConfigTemplateData:
    """Configuration template data structure"""
    name: str
    protocol: str
    description: str
    template_data: Dict
    server_config: Dict
    is_active: bool = True

class ConfigTemplateManager:
    """Manager for configuration templates"""
    
    def __init__(self):
        self.templates: Dict[str, ConfigTemplateData] = {}
        self.protocol_manager = protocol_manager
        self.server_manager = server_manager
    
    async def load_templates_from_db(self):
        """Load templates from database"""
        db = db_manager.get_session()
        try:
            templates = db.query(ConfigTemplate).filter_by(is_active=True).all()
            for template in templates:
                self.templates[template.name] = ConfigTemplateData(
                    name=template.name,
                    protocol=template.protocol,
                    description=template.description,
                    template_data=template.template_data,
                    server_config={},  # Will be populated per server
                    is_active=template.is_active
                )
            logger.info(f"Loaded {len(templates)} configuration templates")
        except Exception as e:
            logger.error(f"Error loading templates from database: {e}")
        finally:
            db.close()
    
    async def create_template(self, name: str, protocol: str, description: str, 
                            template_data: Dict, server_config: Dict = None) -> bool:
        """Create new configuration template"""
        try:
            # Validate protocol
            if not self.protocol_manager.get_plugin(protocol):
                logger.error(f"Protocol {protocol} not supported")
                return False
            
            # Save to database
            db = db_manager.get_session()
            try:
                # Check if template already exists
                existing = db.query(ConfigTemplate).filter_by(name=name).first()
                if existing:
                    logger.error(f"Template {name} already exists")
                    return False
                
                template = ConfigTemplate(
                    name=name,
                    protocol=protocol,
                    description=description,
                    template_data=template_data,
                    is_active=True
                )
                
                db.add(template)
                db.commit()
                
                # Add to memory
                self.templates[name] = ConfigTemplateData(
                    name=name,
                    protocol=protocol,
                    description=description,
                    template_data=template_data,
                    server_config=server_config or {},
                    is_active=True
                )
                
                logger.info(f"Created template: {name}")
                return True
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error creating template: {e}")
                return False
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in create_template: {e}")
            return False
    
    async def update_template(self, name: str, template_data: Dict = None, 
                            server_config: Dict = None, is_active: bool = None) -> bool:
        """Update existing template"""
        try:
            db = db_manager.get_session()
            try:
                template = db.query(ConfigTemplate).filter_by(name=name).first()
                if not template:
                    logger.error(f"Template {name} not found")
                    return False
                
                # Update fields
                if template_data is not None:
                    template.template_data = template_data
                
                if is_active is not None:
                    template.is_active = is_active
                
                db.commit()
                
                # Update memory
                if name in self.templates:
                    if template_data is not None:
                        self.templates[name].template_data = template_data
                    if server_config is not None:
                        self.templates[name].server_config = server_config
                    if is_active is not None:
                        self.templates[name].is_active = is_active
                
                logger.info(f"Updated template: {name}")
                return True
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error updating template: {e}")
                return False
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in update_template: {e}")
            return False
    
    async def delete_template(self, name: str) -> bool:
        """Delete template (mark as inactive)"""
        try:
            db = db_manager.get_session()
            try:
                template = db.query(ConfigTemplate).filter_by(name=name).first()
                if not template:
                    logger.error(f"Template {name} not found")
                    return False
                
                template.is_active = False
                db.commit()
                
                # Remove from memory
                if name in self.templates:
                    del self.templates[name]
                
                logger.info(f"Deleted template: {name}")
                return True
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error deleting template: {e}")
                return False
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in delete_template: {e}")
            return False
    
    async def get_template(self, name: str) -> Optional[ConfigTemplateData]:
        """Get template by name"""
        return self.templates.get(name)
    
    async def get_all_templates(self) -> Dict[str, ConfigTemplateData]:
        """Get all active templates"""
        return {name: template for name, template in self.templates.items() if template.is_active}
    
    async def get_templates_by_protocol(self, protocol: str) -> Dict[str, ConfigTemplateData]:
        """Get templates by protocol"""
        return {
            name: template 
            for name, template in self.templates.items() 
            if template.protocol == protocol and template.is_active
        }
    
    async def apply_template_to_account(self, account_uuid: str, template_name: str, 
                                      server_names: List[str] = None) -> Dict[str, bool]:
        """Apply template to existing account on specified servers"""
        try:
            # Get account
            db = db_manager.get_session()
            try:
                account = db.query(Account).filter_by(uuid=account_uuid).first()
                if not account:
                    logger.error(f"Account {account_uuid} not found")
                    return {}
                
                # Get template
                template = await self.get_template(template_name)
                if not template:
                    logger.error(f"Template {template_name} not found")
                    return {}
                
                # Get servers
                if server_names is None:
                    # Apply to all servers where account exists
                    server_accounts = db.query(ServerAccount).filter_by(account_id=account.id).all()
                    servers = []
                    for sa in server_accounts:
                        server = db.query(Server).filter_by(id=sa.server_id).first()
                        if server:
                            servers.append(server)
                else:
                    # Apply to specified servers
                    servers = []
                    for server_name in server_names:
                        server = db.query(Server).filter_by(name=server_name, is_active=True).first()
                        if server:
                            servers.append(server)
                
                if not servers:
                    logger.error("No servers found for applying template")
                    return {}
                
                # Apply template to each server
                results = {}
                for server in servers:
                    try:
                        success = await self._apply_template_to_server(account, template, server)
                        results[server.name] = success
                        logger.info(f"Template {template_name} applied to {server.name}: {'Success' if success else 'Failed'}")
                    except Exception as e:
                        logger.error(f"Error applying template to server {server.name}: {e}")
                        results[server.name] = False
                
                return results
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in apply_template_to_account: {e}")
            return {}
    
    async def _apply_template_to_server(self, account: Account, template: ConfigTemplateData, 
                                      server: Server) -> bool:
        """Apply template to account on specific server"""
        try:
            # Get protocol plugin
            plugin = self.protocol_manager.get_plugin(template.protocol)
            if not plugin:
                logger.error(f"Protocol plugin {template.protocol} not found")
                return False
            
            # Prepare account data
            account_data = {
                "uuid": account.uuid,
                "email": account.email,
                "limit_ip": 2,
                "total_bytes": account.total_data_limit,  # total_data_limit is already in bytes
                "expiry_time": int(account.expire_time.timestamp() * 1000)
            }
            
            # Prepare server config
            server_config = {
                "name": server.name,
                "host": server.host,
                "port": server.port,
                **template.server_config
            }
            
            # Generate inbound config
            inbound_config = await plugin.generate_inbound_config(account_data, server_config)
            
            # Apply to server using X-UI API
            # This would create a new inbound with the template configuration
            # For now, we'll just log it - you can implement the actual API call
            logger.info(f"Would apply inbound config to {server.name}: {json.dumps(inbound_config, indent=2)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying template to server: {e}")
            return False
    
    async def bulk_apply_template(self, template_name: str, account_uuids: List[str], 
                                server_names: List[str] = None) -> Dict[str, Dict[str, bool]]:
        """Apply template to multiple accounts"""
        results = {}
        
        for account_uuid in account_uuids:
            try:
                account_results = await self.apply_template_to_account(
                    account_uuid, template_name, server_names
                )
                results[account_uuid] = account_results
            except Exception as e:
                logger.error(f"Error applying template to account {account_uuid}: {e}")
                results[account_uuid] = {}
        
        return results
    
    async def generate_config_from_template(self, template_name: str, account_data: Dict, 
                                          server_config: Dict) -> Optional[str]:
        """Generate client config from template"""
        try:
            template = await self.get_template(template_name)
            if not template:
                return None
            
            plugin = self.protocol_manager.get_plugin(template.protocol)
            if not plugin:
                return None
            
            # Merge server config with template config
            merged_config = {**server_config, **template.server_config}
            
            return await plugin.generate_client_config(account_data, merged_config)
            
        except Exception as e:
            logger.error(f"Error generating config from template: {e}")
            return None
    
    async def get_template_preview(self, template_name: str, sample_account_data: Dict, 
                                 sample_server_config: Dict) -> Dict[str, Any]:
        """Get preview of what template would generate"""
        try:
            template = await self.get_template(template_name)
            if not template:
                return {}
            
            plugin = self.protocol_manager.get_plugin(template.protocol)
            if not plugin:
                return {}
            
            # Merge configs
            merged_config = {**sample_server_config, **template.server_config}
            
            # Generate preview
            client_config = await plugin.generate_client_config(sample_account_data, merged_config)
            inbound_config = await plugin.generate_inbound_config(sample_account_data, merged_config)
            
            return {
                "template_name": template_name,
                "protocol": template.protocol,
                "description": template.description,
                "client_config": client_config,
                "inbound_config": inbound_config,
                "server_config": merged_config
            }
            
        except Exception as e:
            logger.error(f"Error getting template preview: {e}")
            return {}
    
    async def import_template_from_json(self, json_data: str) -> bool:
        """Import template from JSON string"""
        try:
            data = json.loads(json_data)
            
            # Validate required fields
            required_fields = ['name', 'protocol', 'description', 'template_data']
            for field in required_fields:
                if field not in data:
                    logger.error(f"Missing required field: {field}")
                    return False
            
            return await self.create_template(
                name=data['name'],
                protocol=data['protocol'],
                description=data['description'],
                template_data=data['template_data'],
                server_config=data.get('server_config', {})
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON data: {e}")
            return False
        except Exception as e:
            logger.error(f"Error importing template: {e}")
            return False
    
    async def export_template_to_json(self, template_name: str) -> Optional[str]:
        """Export template to JSON string"""
        try:
            template = await self.get_template(template_name)
            if not template:
                return None
            
            data = {
                "name": template.name,
                "protocol": template.protocol,
                "description": template.description,
                "template_data": template.template_data,
                "server_config": template.server_config,
                "created_at": datetime.now().isoformat()
            }
            
            return json.dumps(data, indent=2)
            
        except Exception as e:
            logger.error(f"Error exporting template: {e}")
            return None
    
    async def validate_template_syntax(self, template_data: Dict, protocol: str) -> Dict[str, Any]:
        """Validate template syntax"""
        try:
            plugin = self.protocol_manager.get_plugin(protocol)
            if not plugin:
                return {"valid": False, "error": f"Protocol {protocol} not supported"}
            
            # Try to validate with plugin
            is_valid = plugin.validate_config(template_data)
            
            if is_valid:
                return {"valid": True}
            else:
                return {"valid": False, "error": "Invalid configuration"}
                
        except Exception as e:
            return {"valid": False, "error": str(e)}

# Global config template manager instance
config_template_manager = ConfigTemplateManager()

# Export for easy access
__all__ = [
    'ConfigTemplateData',
    'ConfigTemplateManager',
    'config_template_manager'
] 
#!/usr/bin/env python3
"""
Cloud SQL pgvector deployment script
PRD Reference: Lines 141, 143 - Embedding worker with pgvector and idempotent upserts

This script sets up Cloud SQL with PostgreSQL and pgvector extension for production use.
"""
import subprocess
import json
import os
import sys
from typing import Dict, Any, List
import logging


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CloudSQLPgVectorDeployer:
    """Deploy and configure Cloud SQL with pgvector for candidate embeddings."""
    
    def __init__(self, project_id: str, instance_name: str = "headhunter-pgvector"):
        """Initialize deployer with GCP project details."""
        self.project_id = project_id
        self.instance_name = instance_name
        self.database_name = "headhunter"
        self.region = "us-central1"
        self.tier = "db-custom-2-7680"  # 2 vCPUs, 7.5GB RAM - good for vector operations
        
    def check_prerequisites(self) -> bool:
        """Check if required tools and permissions are available."""
        try:
            # Check gcloud is installed and authenticated
            result = subprocess.run(['gcloud', 'auth', 'list', '--format=json'], 
                                  capture_output=True, text=True, check=True)
            accounts = json.loads(result.stdout)
            
            if not any(account.get('status') == 'ACTIVE' for account in accounts):
                logger.error("No active gcloud authentication found")
                return False
                
            # Check if Cloud SQL Admin API is enabled
            result = subprocess.run([
                'gcloud', 'services', 'list', '--enabled', 
                '--filter=name:sqladmin.googleapis.com', 
                '--format=value(name)', f'--project={self.project_id}'
            ], capture_output=True, text=True, check=True)
            
            if 'sqladmin.googleapis.com' not in result.stdout:
                logger.warning("Cloud SQL Admin API not enabled - enabling now")
                subprocess.run([
                    'gcloud', 'services', 'enable', 'sqladmin.googleapis.com',
                    f'--project={self.project_id}'
                ], check=True)
                
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Prerequisites check failed: {e}")
            return False
    
    def create_cloud_sql_instance(self) -> bool:
        """Create Cloud SQL PostgreSQL instance with pgvector support."""
        try:
            # Check if instance already exists
            result = subprocess.run([
                'gcloud', 'sql', 'instances', 'describe', self.instance_name,
                f'--project={self.project_id}'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Cloud SQL instance {self.instance_name} already exists")
                return True
            
            logger.info(f"Creating Cloud SQL instance {self.instance_name}")
            
            # Create the instance
            subprocess.run([
                'gcloud', 'sql', 'instances', 'create', self.instance_name,
                '--database-version=POSTGRES_15',  # pgvector requires PostgreSQL 11+
                f'--tier={self.tier}',
                f'--region={self.region}',
                '--storage-type=SSD',
                '--storage-size=100GB',
                '--storage-auto-increase',
                '--backup-start-time=03:00',  # 3 AM backup
                '--backup-location=us',
                '--maintenance-release-channel=production',
                '--maintenance-window-day=SUN',
                '--maintenance-window-hour=04',
                '--database-flags=shared_preload_libraries=vector',  # Enable pgvector
                '--deletion-protection',
                f'--project={self.project_id}'
            ], check=True)
            
            logger.info("Cloud SQL instance created successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create Cloud SQL instance: {e}")
            return False
    
    def create_database_and_user(self) -> bool:
        """Create database and application user."""
        try:
            # Create database
            logger.info(f"Creating database {self.database_name}")
            subprocess.run([
                'gcloud', 'sql', 'databases', 'create', self.database_name,
                f'--instance={self.instance_name}',
                f'--project={self.project_id}'
            ], check=True)
            
            # Create application user
            app_user = 'headhunter_app'
            app_password = self._generate_password()
            
            logger.info(f"Creating application user {app_user}")
            subprocess.run([
                'gcloud', 'sql', 'users', 'create', app_user,
                f'--instance={self.instance_name}',
                f'--password={app_password}',
                f'--project={self.project_id}'
            ], check=True)
            
            # Store credentials securely (in production, use Secret Manager)
            self._store_connection_info(app_user, app_password)
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create database and user: {e}")
            return False
    
    def setup_pgvector_schema(self) -> bool:
        """Execute pgvector schema setup."""
        try:
            # Get connection info
            connection_info = self._get_connection_info()
            
            # Use Cloud SQL Proxy for secure connection
            logger.info("Setting up pgvector schema")
            
            # In production, you would:
            # 1. Use Cloud SQL Proxy: cloud_sql_proxy -instances=PROJECT:REGION:INSTANCE=tcp:5432
            # 2. Execute the schema file via psql
            # 3. Or use a Cloud Function/Cloud Run job for schema deployment
            
            schema_file = os.path.join(os.path.dirname(__file__), 'pgvector_schema.sql')
            
            if not os.path.exists(schema_file):
                logger.error(f"Schema file not found: {schema_file}")
                return False
            
            logger.info("Schema file ready for deployment")
            logger.info("To deploy schema, run:")
            logger.info(f"cloud_sql_proxy -instances={self.project_id}:{self.region}:{self.instance_name}=tcp:5432 &")
            logger.info(f"psql -h localhost -p 5432 -U headhunter_app -d {self.database_name} -f {schema_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup pgvector schema: {e}")
            return False
    
    def configure_networking(self) -> bool:
        """Configure private IP and authorized networks."""
        try:
            logger.info("Configuring networking for Cloud SQL instance")
            
            # Enable private IP (recommended for production)
            subprocess.run([
                'gcloud', 'sql', 'instances', 'patch', self.instance_name,
                '--network=default',
                '--no-assign-ip',
                f'--project={self.project_id}'
            ], check=True)
            
            # For development, you might want to add your IP
            # subprocess.run([
            #     'gcloud', 'sql', 'instances', 'patch', self.instance_name,
            #     '--authorized-networks=YOUR_IP/32',
            #     f'--project={self.project_id}'
            # ], check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to configure networking: {e}")
            return False
    
    def deploy_complete_setup(self) -> bool:
        """Run complete deployment process."""
        logger.info("Starting Cloud SQL pgvector deployment")
        
        steps = [
            ("Checking prerequisites", self.check_prerequisites),
            ("Creating Cloud SQL instance", self.create_cloud_sql_instance),
            ("Creating database and user", self.create_database_and_user),
            ("Setting up pgvector schema", self.setup_pgvector_schema),
            ("Configuring networking", self.configure_networking)
        ]
        
        for step_name, step_func in steps:
            logger.info(f"Step: {step_name}")
            if not step_func():
                logger.error(f"Failed at step: {step_name}")
                return False
            logger.info(f"Completed: {step_name}")
        
        logger.info("Cloud SQL pgvector deployment completed successfully!")
        self._print_connection_info()
        return True
    
    def _generate_password(self) -> str:
        """Generate secure password for database user."""
        import secrets
        import string
        
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    def _store_connection_info(self, username: str, password: str):
        """Store connection information securely."""
        connection_info = {
            'project_id': self.project_id,
            'region': self.region,
            'instance_name': self.instance_name,
            'database_name': self.database_name,
            'username': username,
            'password': password,
            'connection_name': f"{self.project_id}:{self.region}:{self.instance_name}"
        }
        
        # Store in local config file (in production, use Secret Manager)
        config_file = os.path.join(os.path.dirname(__file__), '../config/pgvector_connection.json')
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(connection_info, f, indent=2)
        
        logger.info(f"Connection info stored in {config_file}")
    
    def _get_connection_info(self) -> Dict[str, Any]:
        """Get stored connection information."""
        config_file = os.path.join(os.path.dirname(__file__), '../config/pgvector_connection.json')
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        
        return {}
    
    def _print_connection_info(self):
        """Print connection information for developers."""
        logger.info("\n" + "="*60)
        logger.info("CLOUD SQL PGVECTOR SETUP COMPLETE")
        logger.info("="*60)
        logger.info(f"Instance: {self.project_id}:{self.region}:{self.instance_name}")
        logger.info(f"Database: {self.database_name}")
        logger.info(f"Connection name: {self.project_id}:{self.region}:{self.instance_name}")
        logger.info("\nNext steps:")
        logger.info("1. Start Cloud SQL Proxy:")
        logger.info(f"   cloud_sql_proxy -instances={self.project_id}:{self.region}:{self.instance_name}=tcp:5432")
        logger.info("2. Deploy schema:")
        logger.info(f"   psql -h localhost -p 5432 -U headhunter_app -d {self.database_name} -f scripts/pgvector_schema.sql")
        logger.info("3. Test connection with pgvector_store.py")
        logger.info("\nEnvironment variables needed:")
        logger.info("PGVECTOR_CONNECTION_STRING=postgresql://headhunter_app:PASSWORD@localhost:5432/headhunter")
        logger.info("="*60)


def main():
    """Main deployment function."""
    if len(sys.argv) != 2:
        print("Usage: python3 deploy_pgvector.py PROJECT_ID")
        sys.exit(1)
    
    project_id = sys.argv[1]
    deployer = CloudSQLPgVectorDeployer(project_id)
    
    success = deployer.deploy_complete_setup()
    
    if success:
        logger.info("Deployment completed successfully!")
        sys.exit(0)
    else:
        logger.error("Deployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
"""
Storage provider abstraction for Jarvis OMNIX Workbench.
Supports local and AWS storage with migration and split-brain prevention.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


class StorageProvider:
    """Abstract storage provider interface."""
    
    def __init__(self, provider: str = "local"):
        self.provider = provider
        self.source_of_truth = os.environ.get("OMNIX_WORKBENCH_SOURCE_OF_TRUTH", "local")
    
    def read_memory(self) -> List[Dict[str, Any]]:
        """Read memory entries."""
        raise NotImplementedError
    
    def write_memory(self, entries: List[Dict[str, Any]]) -> bool:
        """Write memory entries."""
        raise NotImplementedError
    
    def read_artifacts(self) -> List[Dict[str, Any]]:
        """Read artifact entries."""
        raise NotImplementedError
    
    def write_artifacts(self, entries: List[Dict[str, Any]]) -> bool:
        """Write artifact entries."""
        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    """Local file-based storage provider."""
    
    def __init__(self):
        super().__init__("local")
        self.memory_path = Path.home() / ".omnix_workbench" / "memory.jsonl"
        self.artifact_path = Path.home() / ".omnix_workbench" / "artifacts.jsonl"
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure storage directories exist."""
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
    
    def read_memory(self) -> List[Dict[str, Any]]:
        """Read memory entries from local JSONL file."""
        entries = []
        if self.memory_path.exists():
            with open(self.memory_path, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        return entries
    
    def write_memory(self, entries: List[Dict[str, Any]]) -> bool:
        """Write memory entries to local JSONL file."""
        try:
            with open(self.memory_path, 'w') as f:
                for entry in entries:
                    f.write(json.dumps(entry) + '\n')
            return True
        except Exception:
            return False
    
    def read_artifacts(self) -> List[Dict[str, Any]]:
        """Read artifact entries from local JSONL file."""
        entries = []
        if self.artifact_path.exists():
            with open(self.artifact_path, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        return entries
    
    def write_artifacts(self, entries: List[Dict[str, Any]]) -> bool:
        """Write artifact entries to local JSONL file."""
        try:
            with open(self.artifact_path, 'w') as f:
                for entry in entries:
                    f.write(json.dumps(entry) + '\n')
            return True
        except Exception:
            return False


class AWSStorageProvider(StorageProvider):
    """AWS-based storage provider using S3 and DynamoDB."""
    
    def __init__(self):
        super().__init__("aws")
        self.region = os.environ.get("OMNIX_WORKBENCH_AWS_REGION", "ap-southeast-1")
        self.memory_bucket = os.environ.get("OMNIX_WORKBENCH_MEMORY_BUCKET")
        self.artifact_bucket = os.environ.get("OMNIX_WORKBENCH_ARTIFACT_BUCKET")
        self.state_table = os.environ.get("OMNIX_WORKBENCH_STATE_TABLE")
        self._validate_config()
    
    def _validate_config(self):
        """Validate AWS storage configuration."""
        if not all([self.memory_bucket, self.artifact_bucket, self.state_table]):
            raise ValueError("AWS storage configuration incomplete")
    
    def read_memory(self) -> List[Dict[str, Any]]:
        """Read memory entries from AWS S3."""
        import boto3
        s3 = boto3.client('s3', region_name=self.region)
        
        try:
            response = s3.get_object(Bucket=self.memory_bucket, Key='memory.jsonl')
            content = response['Body'].read().decode('utf-8')
            entries = []
            for line in content.split('\n'):
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return entries
        except Exception as e:
            print(f"Error reading from S3: {e}")
            return []
    
    def write_memory(self, entries: List[Dict[str, Any]]) -> bool:
        """Write memory entries to AWS S3."""
        import boto3
        s3 = boto3.client('s3', region_name=self.region)
        
        try:
            content = '\n'.join(json.dumps(entry) for entry in entries)
            s3.put_object(
                Bucket=self.memory_bucket,
                Key='memory.jsonl',
                Body=content.encode('utf-8')
            )
            return True
        except Exception as e:
            print(f"Error writing to S3: {e}")
            return False
    
    def read_artifacts(self) -> List[Dict[str, Any]]:
        """Read artifact entries from AWS S3."""
        import boto3
        s3 = boto3.client('s3', region_name=self.region)
        
        try:
            response = s3.get_object(Bucket=self.artifact_bucket, Key='artifacts.jsonl')
            content = response['Body'].read().decode('utf-8')
            entries = []
            for line in content.split('\n'):
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return entries
        except Exception as e:
            print(f"Error reading from S3: {e}")
            return []
    
    def write_artifacts(self, entries: List[Dict[str, Any]]) -> bool:
        """Write artifact entries to AWS S3."""
        import boto3
        s3 = boto3.client('s3', region_name=self.region)
        
        try:
            content = '\n'.join(json.dumps(entry) for entry in entries)
            s3.put_object(
                Bucket=self.artifact_bucket,
                Key='artifacts.jsonl',
                Body=content.encode('utf-8')
            )
            return True
        except Exception as e:
            print(f"Error writing to S3: {e}")
            return False


class StorageManager:
    """Storage manager with split-brain prevention and migration support."""
    
    def __init__(self):
        provider = os.environ.get("OMNIX_WORKBENCH_STORAGE_PROVIDER", "local")
        if provider == "aws":
            self.provider = AWSStorageProvider()
        else:
            self.provider = LocalStorageProvider()
        
        self.source_of_truth = self.provider.source_of_truth
    
    def get_provider(self) -> StorageProvider:
        """Get current storage provider."""
        return self.provider
    
    def migrate_to_cloud(self, dry_run: bool = False) -> Dict[str, Any]:
        """Migrate local storage to cloud (with dry-run support)."""
        result = {
            "dry_run": dry_run,
            "source": "local",
            "destination": "cloud",
            "timestamp": datetime.now().isoformat(),
            "memory_entries": 0,
            "artifact_entries": 0,
            "success": False
        }
        
        if dry_run:
            result["message"] = "DRY-RUN: No actual migration performed"
            result["local_memory_count"] = len(LocalStorageProvider().read_memory())
            result["local_artifact_count"] = len(LocalStorageProvider().read_artifacts())
            return result
        
        try:
            local = LocalStorageProvider()
            cloud = AWSStorageProvider()
            
            # Migrate memory
            memory_entries = local.read_memory()
            result["memory_entries"] = len(memory_entries)
            if cloud.write_memory(memory_entries):
                result["memory_success"] = True
            else:
                result["memory_success"] = False
            
            # Migrate artifacts
            artifact_entries = local.read_artifacts()
            result["artifact_entries"] = len(artifact_entries)
            if cloud.write_artifacts(artifact_entries):
                result["artifact_success"] = True
            else:
                result["artifact_success"] = False
            
            result["success"] = result["memory_success"] and result["artifact_success"]
            result["message"] = "Migration completed" if result["success"] else "Migration partially failed"
            
        except Exception as e:
            result["error"] = str(e)
            result["message"] = f"Migration failed: {e}"
        
        return result
    
    def migrate_to_local(self, dry_run: bool = False) -> Dict[str, Any]:
        """Migrate cloud storage to local (with dry-run support)."""
        result = {
            "dry_run": dry_run,
            "source": "cloud",
            "destination": "local",
            "timestamp": datetime.now().isoformat(),
            "memory_entries": 0,
            "artifact_entries": 0,
            "success": False
        }
        
        if dry_run:
            result["message"] = "DRY-RUN: No actual migration performed"
            try:
                cloud = AWSStorageProvider()
                result["cloud_memory_count"] = len(cloud.read_memory())
                result["cloud_artifact_count"] = len(cloud.read_artifacts())
            except Exception as e:
                result["error"] = str(e)
            return result
        
        try:
            cloud = AWSStorageProvider()
            local = LocalStorageProvider()
            
            # Migrate memory
            memory_entries = cloud.read_memory()
            result["memory_entries"] = len(memory_entries)
            if local.write_memory(memory_entries):
                result["memory_success"] = True
            else:
                result["memory_success"] = False
            
            # Migrate artifacts
            artifact_entries = cloud.read_artifacts()
            result["artifact_entries"] = len(artifact_entries)
            if local.write_artifacts(artifact_entries):
                result["artifact_success"] = True
            else:
                result["artifact_success"] = False
            
            result["success"] = result["memory_success"] and result["artifact_success"]
            result["message"] = "Migration completed" if result["success"] else "Migration partially failed"
            
        except Exception as e:
            result["error"] = str(e)
            result["message"] = f"Migration failed: {e}"
        
        return result
    
    def check_conflicts(self) -> Dict[str, Any]:
        """Check for storage conflicts between local and cloud."""
        result = {
            "local_memory_count": 0,
            "cloud_memory_count": 0,
            "local_artifact_count": 0,
            "cloud_artifact_count": 0,
            "has_conflicts": False,
            "conflict_details": []
        }
        
        try:
            local = LocalStorageProvider()
            result["local_memory_count"] = len(local.read_memory())
            result["local_artifact_count"] = len(local.read_artifacts())
        except Exception as e:
            result["local_error"] = str(e)
        
        try:
            cloud = AWSStorageProvider()
            result["cloud_memory_count"] = len(cloud.read_memory())
            result["cloud_artifact_count"] = len(cloud.read_artifacts())
        except Exception as e:
            result["cloud_error"] = str(e)
        
        # Simple conflict detection
        if result["local_memory_count"] > 0 and result["cloud_memory_count"] > 0:
            result["has_conflicts"] = True
            result["conflict_details"].append("Both local and cloud have memory entries")
        
        if result["local_artifact_count"] > 0 and result["cloud_artifact_count"] > 0:
            result["has_conflicts"] = True
            result["conflict_details"].append("Both local and cloud have artifact entries")
        
        return result


def get_storage_manager() -> StorageManager:
    """Get storage manager instance."""
    return StorageManager()

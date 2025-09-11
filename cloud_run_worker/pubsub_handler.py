"""
Pub/Sub message handler for Cloud Run worker
"""

import base64
import json
import logging
from typing import Dict, Any
from datetime import datetime

from google.cloud import pubsub_v1
from google.cloud.pubsub_v1 import PublisherClient

from config import Config
from models import PubSubMessage, DeadLetterMessage

logger = logging.getLogger(__name__)


class PubSubHandler:
    """Handles Pub/Sub message parsing and dead letter queue operations"""
    
    def __init__(self, config: Config):
        self.config = config
        self.project_id = config.project_id
        self.dead_letter_topic = config.dead_letter_topic
        
        # Initialize publisher for dead letter queue
        self.dead_letter_publisher = None
        
    async def initialize(self):
        """Initialize Pub/Sub connections"""
        try:
            self.dead_letter_publisher = PublisherClient()
            self.dead_letter_topic_path = self.dead_letter_publisher.topic_path(
                self.project_id, 
                self.dead_letter_topic
            )
            logger.info(f"Initialized Pub/Sub handler for project: {self.project_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Pub/Sub handler: {e}")
            raise
    
    async def shutdown(self):
        """Cleanup Pub/Sub connections"""
        if self.dead_letter_publisher:
            self.dead_letter_publisher.close()
            logger.info("Pub/Sub handler shutdown complete")
    
    def parse_message(self, message_data: Dict[str, Any]) -> PubSubMessage:
        """
        Parse incoming Pub/Sub message from Cloud Run webhook
        
        Args:
            message_data: Raw message data from Pub/Sub webhook
            
        Returns:
            PubSubMessage: Parsed message object
            
        Raises:
            ValueError: If message format is invalid
        """
        try:
            # Extract message envelope
            if "message" not in message_data:
                raise ValueError("Missing message envelope in Pub/Sub data")
            
            message = message_data["message"]
            
            # Extract required fields
            if "data" not in message:
                raise ValueError("Missing message data")
            
            if "messageId" not in message:
                raise ValueError("Missing messageId")
            
            # Decode base64 data
            try:
                encoded_data = message["data"]
                decoded_data = base64.b64decode(encoded_data).decode('utf-8')
                payload = json.loads(decoded_data)
            except (ValueError, json.JSONDecodeError) as e:
                raise ValueError(f"Invalid message data encoding: {e}")
            
            # Validate required payload fields
            required_fields = ["candidate_id"]
            for field in required_fields:
                if field not in payload:
                    raise ValueError(f"Missing required field: {field}")
            
            # Extract attributes
            attributes = message.get("attributes", {})
            
            # Create parsed message
            parsed_message = PubSubMessage(
                candidate_id=payload["candidate_id"],
                action=payload.get("action", "enrich_profile"),
                org_id=payload.get("org_id") or attributes.get("org_id"),
                priority=payload.get("priority", "normal"),
                message_id=message["messageId"],
                publish_time=message.get("publishTime", datetime.now().isoformat()),
                attributes=attributes,
                timestamp=datetime.fromisoformat(payload.get("timestamp", datetime.now().isoformat()).replace('Z', '+00:00'))
            )
            
            logger.info(f"Parsed message for candidate: {parsed_message.candidate_id}")
            return parsed_message
            
        except Exception as e:
            logger.error(f"Failed to parse Pub/Sub message: {e}")
            raise ValueError(f"Message parsing failed: {e}")
    
    def send_to_dead_letter_queue(self, original_message: Dict[str, Any], error: str, retry_count: int = 0):
        """
        Send failed message to dead letter queue
        
        Args:
            original_message: Original Pub/Sub message
            error: Error description
            retry_count: Number of retry attempts made
        """
        try:
            if not self.dead_letter_publisher:
                logger.error("Dead letter publisher not initialized")
                return
            
            # Extract candidate_id if possible
            candidate_id = None
            org_id = None
            
            try:
                if "message" in original_message and "data" in original_message["message"]:
                    decoded = base64.b64decode(original_message["message"]["data"]).decode('utf-8')
                    payload = json.loads(decoded)
                    candidate_id = payload.get("candidate_id")
                    org_id = payload.get("org_id")
            except Exception:
                pass  # Best effort extraction
            
            # Create dead letter message
            dead_letter_msg = DeadLetterMessage(
                original_message=original_message,
                error=error,
                retry_count=retry_count,
                candidate_id=candidate_id,
                org_id=org_id
            )
            
            # Publish to dead letter queue
            message_data = json.dumps(dead_letter_msg.dict(), default=str).encode('utf-8')
            
            future = self.dead_letter_publisher.publish(
                self.dead_letter_topic_path,
                message_data,
                candidate_id=candidate_id or "unknown",
                error_type="processing_failed",
                retry_count=str(retry_count),
                failed_at=datetime.now().isoformat()
            )
            
            # Wait for publish to complete
            message_id = future.result(timeout=30)
            
            logger.info(f"Sent message to dead letter queue: {message_id}, candidate: {candidate_id}")
            
        except Exception as e:
            logger.error(f"Failed to send message to dead letter queue: {e}")
    
    def validate_message_format(self, message_data: Dict[str, Any]) -> bool:
        """
        Validate message format without full parsing
        
        Args:
            message_data: Raw message data
            
        Returns:
            bool: True if format is valid
        """
        try:
            # Basic structure validation
            if not isinstance(message_data, dict):
                return False
            
            if "message" not in message_data:
                return False
            
            message = message_data["message"]
            if not isinstance(message, dict):
                return False
            
            # Check required fields
            required_fields = ["data", "messageId"]
            for field in required_fields:
                if field not in message:
                    return False
            
            # Try to decode data
            try:
                decoded = base64.b64decode(message["data"]).decode('utf-8')
                payload = json.loads(decoded)
                
                # Check for candidate_id
                if "candidate_id" not in payload:
                    return False
                    
            except Exception:
                return False
            
            return True
            
        except Exception:
            return False
    
    def extract_candidate_id(self, message_data: Dict[str, Any]) -> str:
        """
        Extract candidate ID from message without full parsing
        
        Args:
            message_data: Raw message data
            
        Returns:
            str: Candidate ID or 'unknown'
        """
        try:
            message = message_data.get("message", {})
            if "data" in message:
                decoded = base64.b64decode(message["data"]).decode('utf-8')
                payload = json.loads(decoded)
                return payload.get("candidate_id", "unknown")
        except Exception:
            pass
        
        return "unknown"
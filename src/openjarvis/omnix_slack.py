"""
Slack integration for Jarvis OMNIX Workbench.
Provides safe Slack send functionality with token validation.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional


class SlackIntegration:
    """Slack integration with safe token handling."""
    
    def __init__(self):
        self.token = self._load_token()
        self.channel = self._load_channel()
        self.safe_channel = "C0BAF08SQTB"  # agent-orchestrator
    
    def _load_token(self) -> Optional[str]:
        """Load Slack token from environment or .env file."""
        # Check environment variables
        for key in ["OPENCLAW_SLACK_BOT_TOKEN", "SLACK_BOT_TOKEN", "SLACK_TOKEN"]:
            if key in os.environ:
                return os.environ[key]
        
        # Check local .env file
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            import dotenv
            dotenv.load_dotenv(env_path)
            for key in ["OPENCLAW_SLACK_BOT_TOKEN", "SLACK_BOT_TOKEN", "SLACK_TOKEN"]:
                if key in os.environ:
                    return os.environ[key]
        
        return None
    
    def _load_channel(self) -> Optional[str]:
        """Load Slack channel from environment."""
        return os.environ.get("OPENCLAW_SLACK_CONTINUOUS_OPS_CHANNEL", self.safe_channel)
    
    def check_token_exists(self) -> bool:
        """Check if Slack token exists (without exposing value)."""
        return self.token is not None
    
    def check_channel_configured(self) -> bool:
        """Check if Slack channel is configured."""
        return self.channel is not None
    
    def check_send_path_exists(self) -> bool:
        """Check if Slack send path exists (OpenClaw CLI or webhook)."""
        try:
            result = subprocess.run(
                ["command", "-v", "openclaw"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def send_message(self, message: str, channel: Optional[str] = None) -> dict:
        """Send message to Slack."""
        if not self.token:
            return {
                "success": False,
                "error": "Slack token not found",
                "error_type": "MISSING_TOKEN"
            }
        
        if not self.channel:
            return {
                "success": False,
                "error": "Slack channel not configured",
                "error_type": "MISSING_CHANNEL"
            }
        
        target_channel = channel or self.channel
        
        try:
            # Try OpenClaw CLI if available
            if self.check_send_path_exists():
                result = subprocess.run(
                    ["openclaw", "slack", "send", "--channel", target_channel, "--message", message],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return {
                        "success": True,
                        "channel": target_channel,
                        "message": message,
                        "method": "openclaw_cli"
                    }
                else:
                    return {
                        "success": False,
                        "error": result.stderr,
                        "error_type": "CLI_ERROR"
                    }
            else:
                return {
                    "success": False,
                    "error": "OpenClaw CLI not found",
                    "error_type": "MISSING_SEND_PATH"
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Slack send timed out",
                "error_type": "TIMEOUT"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "UNKNOWN"
            }
    
    def get_status(self) -> dict:
        """Get Slack integration status."""
        return {
            "token_exists": self.check_token_exists(),
            "channel_configured": self.check_channel_configured(),
            "send_path_exists": self.check_send_path_exists(),
            "safe_channel": self.safe_channel,
            "configured_channel": self.channel,
            "ready": self.check_token_exists() and self.check_channel_configured() and self.check_send_path_exists()
        }


def get_slack_integration() -> SlackIntegration:
    """Get Slack integration instance."""
    return SlackIntegration()

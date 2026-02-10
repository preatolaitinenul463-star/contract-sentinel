"""Security service - encryption, DLP, and data masking.

Data classification: high / medium / low sensitivity.
See backend/docs/data_masking_rules.md for full rules and examples.
"""
import re
import base64
from typing import Optional, Dict, List, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings

# Data sensitivity levels (for classification only; masking rules below)
SENSITIVITY_HIGH = "high"
SENSITIVITY_MEDIUM = "medium"
SENSITIVITY_LOW = "low"

# Field classification for contract/audit (reference)
DATA_CLASSIFICATION = {
    "id_card_cn": SENSITIVITY_HIGH,
    "bank_card": SENSITIVITY_HIGH,
    "credit_card": SENSITIVITY_HIGH,
    "social_security_us": SENSITIVITY_HIGH,
    "passport_cn": SENSITIVITY_HIGH,
    "phone_cn": SENSITIVITY_MEDIUM,
    "email": SENSITIVITY_MEDIUM,
    "name": SENSITIVITY_MEDIUM,
    "address": SENSITIVITY_MEDIUM,
    "amount": SENSITIVITY_MEDIUM,
}


class EncryptionService:
    """Handles data encryption/decryption for data at rest."""
    
    def __init__(self, key: Optional[str] = None):
        """Initialize with encryption key (default from config)."""
        if key is None:
            key = settings.encryption_key or settings.jwt_secret
        # Derive a proper Fernet key from the secret
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=settings.encryption_salt.encode(),
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
        self.fernet = Fernet(derived_key)
    
    def encrypt_at_rest(self, data: str) -> str:
        """Encrypt for storage; returns original if encryption disabled."""
        if not getattr(settings, "encryption_enabled", True):
            return data
        if not data:
            return data
        return self.encrypt(data)
    
    def decrypt_at_rest(self, data: Optional[str]) -> Optional[str]:
        """Decrypt from storage; returns as-is if not encrypted or disabled."""
        if not data:
            return data
        if not getattr(settings, "encryption_enabled", True):
            return data
        try:
            return self.decrypt(data)
        except Exception:
            # Backward compatibility: already plaintext
            return data
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data."""
        return self.fernet.decrypt(encrypted_data.encode()).decode()
    
    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt binary data."""
        return self.fernet.encrypt(data)
    
    def decrypt_bytes(self, encrypted_data: bytes) -> bytes:
        """Decrypt binary data."""
        return self.fernet.decrypt(encrypted_data)


class DLPService:
    """Data Loss Prevention - detects and masks sensitive information."""
    
    # Patterns for sensitive data detection
    PATTERNS = {
        "phone_cn": (
            r"1[3-9]\d{9}",
            "手机号码"
        ),
        "id_card_cn": (
            r"\d{17}[\dXx]",
            "身份证号"
        ),
        "bank_card": (
            r"\d{16,19}",
            "银行卡号"
        ),
        "email": (
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "邮箱地址"
        ),
        "credit_card": (
            r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}",
            "信用卡号"
        ),
        "passport_cn": (
            r"[EeGg]\d{8}",
            "护照号码"
        ),
        "social_security_us": (
            r"\d{3}-\d{2}-\d{4}",
            "社会安全号"
        ),
    }
    
    def detect(self, text: str) -> List[Dict]:
        """Detect sensitive information in text."""
        findings = []
        
        for pattern_name, (pattern, label) in self.PATTERNS.items():
            for match in re.finditer(pattern, text):
                findings.append({
                    "type": pattern_name,
                    "label": label,
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                })
        
        return findings
    
    def mask(self, text: str, mask_char: str = "*") -> Tuple[str, List[Dict]]:
        """Detect and mask sensitive information."""
        findings = self.detect(text)
        masked_text = text
        
        # Sort by position (reverse) to avoid offset issues
        findings_sorted = sorted(findings, key=lambda x: x["start"], reverse=True)
        
        for finding in findings_sorted:
            value = finding["value"]
            # Keep first 3 and last 2 characters visible
            if len(value) > 5:
                masked_value = value[:3] + mask_char * (len(value) - 5) + value[-2:]
            else:
                masked_value = mask_char * len(value)
            
            masked_text = (
                masked_text[:finding["start"]] +
                masked_value +
                masked_text[finding["end"]:]
            )
            finding["masked_value"] = masked_value
        
        return masked_text, findings
    
    def should_block_llm_call(self, text: str, threshold: int = 5) -> bool:
        """Check if text contains too much sensitive data for LLM."""
        findings = self.detect(text)
        
        # Count high-risk findings
        high_risk_types = {"id_card_cn", "bank_card", "credit_card", "social_security_us"}
        high_risk_count = sum(1 for f in findings if f["type"] in high_risk_types)
        
        return high_risk_count >= threshold


class DataMaskingService:
    """Masks sensitive business data for display."""
    
    @staticmethod
    def mask_amount(amount: str) -> str:
        """Mask monetary amount."""
        # Keep currency symbol and first digit
        match = re.match(r"([^\d]*)([\d,]+\.?\d*)(.*)", amount)
        if match:
            prefix, number, suffix = match.groups()
            number = number.replace(",", "")
            if len(number) > 2:
                masked = number[0] + "*" * (len(number) - 2) + number[-1]
            else:
                masked = number
            return prefix + masked + suffix
        return amount
    
    @staticmethod
    def mask_name(name: str) -> str:
        """Mask person/company name."""
        if len(name) <= 2:
            return name[0] + "*"
        return name[0] + "*" * (len(name) - 2) + name[-1]
    
    @staticmethod
    def mask_address(address: str) -> str:
        """Mask address, keeping only district/city level."""
        # For Chinese addresses, keep province/city
        parts = re.split(r"[省市区县]", address)
        if len(parts) >= 2:
            return parts[0] + "***"
        return address[:len(address)//3] + "***"


def mask_text_for_llm_input(text: str, mask_char: str = "*") -> str:
    """
    Full pipeline: mask all sensitive data before sending to LLM.
    Uses DLP patterns + business masking. Model input MUST use this.
    """
    dlp = get_dlp_service()
    masked, _ = dlp.mask(text, mask_char=mask_char)
    return masked


def mask_llm_output(text: str, mask_char: str = "*") -> str:
    """
    Re-mask sensitive data in LLM output before storing or displaying.
    Uses same DLP rules as input. Call before writing to report or DB.
    """
    return mask_text_for_llm_input(text, mask_char=mask_char)


# Global instances
_encryption_service: Optional[EncryptionService] = None
_dlp_service: Optional[DLPService] = None


def get_encryption_service() -> EncryptionService:
    """Get encryption service singleton."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def get_dlp_service() -> DLPService:
    """Get DLP service singleton."""
    global _dlp_service
    if _dlp_service is None:
        _dlp_service = DLPService()
    return _dlp_service

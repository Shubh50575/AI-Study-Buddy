# backend/validation_utils.py

import re
import dns.resolver
import smtplib
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from email_validator import validate_email, EmailNotValidError

# --------------------------------------------------------------
# Email Validation Functions
# --------------------------------------------------------------

def validate_email_address(email: str) -> dict:
    """
    Email validation using 3-layer check:
    1. Format validation
    2. Domain MX record check
    3. SMTP reachability check
    """
    result = {
        "valid": False,
        "message": "",
        "domain_exists": False,
        "mx_exists": False,
        "smtp_check": False,
        "is_disposable": False,
        "suggested": None
    }

    # Remove whitespace and convert to lowercase
    email = email.strip().lower()

    # Layer 1: Format validation using email-validator
    try:
        validation = validate_email(email, check_deliverability=False)
        email = validation.normalized
        result["suggested"] = validation.normalized
    except EmailNotValidError as e:
        result["message"] = f"Invalid email format: {str(e)}"
        return result

    # Layer 2: Domain existence check (DNS MX record)
    domain = email.split('@')[1]
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        if mx_records:
            result["mx_exists"] = True
            result["domain_exists"] = True
    except Exception:
        result["message"] = "Domain does not exist or has no mail server"
        return result

    # Layer 3: Check for disposable/temporary email domains
    disposable_domains = ['tempmail.com', 'throwaway.com', 'guerrillamail.com', 
                          'mailinator.com', '10minutemail.com', 'temp-mail.org']
    if domain in disposable_domains:
        result["is_disposable"] = True
        result["message"] = "Disposable/temporary email addresses are not allowed"
        return result

    # If all checks pass
    result["valid"] = True
    result["message"] = "Email is valid and deliverable"
    return result


def quick_email_syntax_check(email: str) -> bool:
    """Basic syntax check for frontend validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


# --------------------------------------------------------------
# Mobile Number Validation Functions
# --------------------------------------------------------------

def validate_mobile_number(mobile: str, default_region: str = "IN") -> dict:
    """
    Mobile number validation using Google's libphonenumber
    - Checks format validity
    - Checks if number is possible
    - Checks if number is valid for the region
    - Gets carrier/operator information
    """
    result = {
        "valid": False,
        "message": "",
        "country_code": None,
        "national_number": None,
        "carrier_name": None,
        "number_type": None,
        "is_possible": False,
        "e164_format": None
    }

    try:
        # Parse and validate number
        parsed_number = phonenumbers.parse(mobile, default_region)
        
        # Check if number is possible (basic format)
        if not phonenumbers.is_possible_number(parsed_number):
            result["message"] = "Number format is invalid"
            return result
        
        # Check if number is valid (exists in numbering plan)
        if not phonenumbers.is_valid_number(parsed_number):
            result["message"] = "Number is not a valid mobile number"
            return result
        
        # Get number details
        result["valid"] = True
        result["is_possible"] = True
        result["country_code"] = parsed_number.country_code
        result["national_number"] = parsed_number.national_number
        result["e164_format"] = phonenumbers.format_number(
            parsed_number, phonenumbers.PhoneNumberFormat.E164
        )
        
        # Try to get carrier information (if available)
        try:
            carrier_name = carrier.name_for_number(parsed_number, "en")
            if carrier_name:
                result["carrier_name"] = carrier_name
        except Exception:
            pass
        
        # Get number type
        number_type = phonenumbers.number_type(parsed_number)
        type_map = {
            phonenumbers.PhoneNumberType.MOBILE: "Mobile",
            phonenumbers.PhoneNumberType.FIXED_LINE: "Fixed Line",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed/Mobile",
            phonenumbers.PhoneNumberType.TOLL_FREE: "Toll Free",
            phonenumbers.PhoneNumberType.PREMIUM_RATE: "Premium Rate",
            phonenumbers.PhoneNumberType.SHARED_COST: "Shared Cost",
            phonenumbers.PhoneNumberType.VOIP: "VoIP",
            phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Personal",
            phonenumbers.PhoneNumberType.PAGER: "Pager",
            phonenumbers.PhoneNumberType.UAN: "UAN",
            phonenumbers.PhoneNumberType.VOICEMAIL: "Voicemail",
            phonenumbers.PhoneNumberType.UNKNOWN: "Unknown"
        }
        result["number_type"] = type_map.get(number_type, "Unknown")
        
        result["message"] = "Valid mobile number"
        
    except phonenumbers.NumberParseException as e:
        result["message"] = f"Invalid number format: {str(e)}"
    except Exception as e:
        result["message"] = f"Validation error: {str(e)}"
    
    return result


def quick_mobile_syntax_check(mobile: str) -> bool:
    """Basic syntax check for frontend - Indian mobile numbers"""
    # Indian mobile numbers: 10 digits, starts with 6-9
    pattern = r'^[6-9]\d{9}$'
    if re.match(pattern, mobile.strip()):
        return True
    # International format with +91
    pattern2 = r'^\+91[6-9]\d{9}$'
    return bool(re.match(pattern2, mobile.strip()))
"""
Document Generation Mixin for ProcessingQueue.

Handles document generation operations including:
- SOAP note generation from transcripts
- Referral generation from SOAP notes
- Letter generation from content

This mixin is designed to be used with ProcessingQueue to keep the main
class focused on core queue operations.
"""

from typing import Optional

from settings.settings_manager import settings_manager
from utils.error_handling import ErrorContext
from utils.exceptions import APIError, APITimeoutError
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class DocumentGenerationMixin:
    """Mixin providing document generation capabilities for ProcessingQueue."""

    def _generate_soap_note(self, transcript: str, context: str = "") -> Optional[str]:
        """Generate SOAP note from transcript with optional context.

        Args:
            transcript: The transcript text
            context: Optional context/background information to include

        Returns:
            Generated SOAP note or None if failed

        Note:
            Returns None on failure rather than raising to allow partial
            processing to continue. Errors are logged with full context.
        """
        try:
            from ai.ai import create_soap_note_with_openai

            provider = settings_manager.get_ai_provider()
            model = settings_manager.get_nested(f"{provider}.model", "gpt-4")

            # Generate SOAP note with context if provided
            soap_note = create_soap_note_with_openai(transcript, context)
            return soap_note
        except (APIError, APITimeoutError) as e:
            ctx = ErrorContext.capture(
                operation="Generate SOAP note",
                exception=e,
                error_code=getattr(e, 'error_code', 'SOAP_API_ERROR'),
                transcript_length=len(transcript),
                has_context=bool(context)
            )
            ctx.log()
            return None
        except (ConnectionError, TimeoutError) as e:
            ctx = ErrorContext.capture(
                operation="Generate SOAP note",
                exception=e,
                error_code="SOAP_NETWORK_ERROR",
                transcript_length=len(transcript)
            )
            ctx.log()
            return None
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Generate SOAP note",
                exception=e,
                error_code="SOAP_UNEXPECTED_ERROR",
                transcript_length=len(transcript)
            )
            ctx.log()
            return None

    def _generate_referral(self, soap_note: str) -> Optional[str]:
        """Generate referral from SOAP note.

        Args:
            soap_note: The SOAP note text

        Returns:
            Generated referral or None if failed

        Note:
            Returns None on failure rather than raising to allow partial
            processing to continue. Errors are logged with full context.
        """
        try:
            from ai.ai import create_referral_with_openai

            provider = settings_manager.get_ai_provider()
            model = settings_manager.get_nested(f"{provider}.model", "gpt-4")

            # For batch processing, use a default condition
            conditions = "Based on the clinical findings in the SOAP note"

            # Generate referral
            referral = create_referral_with_openai(soap_note, conditions)
            return referral
        except (APIError, APITimeoutError) as e:
            ctx = ErrorContext.capture(
                operation="Generate referral",
                exception=e,
                error_code=getattr(e, 'error_code', 'REFERRAL_API_ERROR'),
                soap_note_length=len(soap_note)
            )
            ctx.log()
            return None
        except (ConnectionError, TimeoutError) as e:
            ctx = ErrorContext.capture(
                operation="Generate referral",
                exception=e,
                error_code="REFERRAL_NETWORK_ERROR",
                soap_note_length=len(soap_note)
            )
            ctx.log()
            return None
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Generate referral",
                exception=e,
                error_code="REFERRAL_UNEXPECTED_ERROR",
                soap_note_length=len(soap_note)
            )
            ctx.log()
            return None

    def _generate_letter(self, content: str, recipient_type: str = "other", specs: str = "") -> Optional[str]:
        """Generate letter from content.

        Args:
            content: The source content (SOAP note or transcript)
            recipient_type: Type of recipient (insurance, employer, specialist, etc.)
            specs: Additional specifications for the letter

        Returns:
            Generated letter or None if failed

        Note:
            Returns None on failure rather than raising to allow partial
            processing to continue. Errors are logged with full context.
        """
        try:
            from ai.ai import create_letter_with_ai

            provider = settings_manager.get_ai_provider()
            model = settings_manager.get_nested(f"{provider}.model", "gpt-4")

            # Generate letter with recipient type and specs
            letter = create_letter_with_ai(content, recipient_type, specs)
            return letter
        except (APIError, APITimeoutError) as e:
            ctx = ErrorContext.capture(
                operation="Generate letter",
                exception=e,
                error_code=getattr(e, 'error_code', 'LETTER_API_ERROR'),
                content_length=len(content),
                recipient_type=recipient_type
            )
            ctx.log()
            return None
        except (ConnectionError, TimeoutError) as e:
            ctx = ErrorContext.capture(
                operation="Generate letter",
                exception=e,
                error_code="LETTER_NETWORK_ERROR",
                content_length=len(content)
            )
            ctx.log()
            return None
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Generate letter",
                exception=e,
                error_code="LETTER_UNEXPECTED_ERROR",
                content_length=len(content)
            )
            ctx.log()
            return None

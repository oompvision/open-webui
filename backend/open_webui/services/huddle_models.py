"""
Huddle Model Service for AlumniHuddle Chat

This service ensures each huddle has a properly configured custom model
that wraps the Claude pipeline with huddle-specific branding:
- Custom name (e.g., "Holy Cross Men's Lacrosse Mentor Coach")
- Huddle logo as profile image
- Description/blurb about the AI assistant
- Pre-set prompt suggestions for mentor matching
"""

import logging
import time
from typing import Optional

from open_webui.internal.db import get_db_context
from open_webui.models.models import Model, ModelForm, ModelMeta, ModelParams, Models
from open_webui.models.tenants import HuddleModel, Huddles

log = logging.getLogger(__name__)


# Default Claude model to use as base (Opus 4.1)
DEFAULT_BASE_MODEL = "anthropic.claude-opus-4-1-20250805"

# Default prompt suggestions for mentor matching
DEFAULT_SUGGESTION_PROMPTS = [
    {
        "title": ["Help me find", "a mentor"],
        "content": "I'm looking for a mentor who can help me with my career. Can you help me find someone from the alumni network?"
    },
    {
        "title": ["Help improve", "my resume"],
        "content": "Can you help me improve my resume? I'm looking for feedback and suggestions."
    },
    {
        "title": ["Help me prep", "for an interview"],
        "content": "I have an interview coming up. Can you help me prepare with practice questions and tips?"
    },
    {
        "title": ["Help me explore", "career paths"],
        "content": "I'm not sure what career path to pursue. Can you help me explore my options based on my interests and skills?"
    }
]


def get_huddle_model_id(huddle: HuddleModel) -> str:
    """Generate the model ID for a huddle."""
    return f"alumnihuddle-{huddle.slug}"


def get_huddle_model_name(huddle: HuddleModel) -> str:
    """Generate the display name for a huddle's model."""
    return f"{huddle.name} Mentor Coach"


def get_huddle_model_description(huddle: HuddleModel) -> str:
    """Generate the description/blurb for a huddle's model."""
    return (
        f"AI assistant for {huddle.name} that helps students connect with "
        f"alumni mentors and prepare for careers after graduation"
    )


def build_huddle_model_meta(huddle: HuddleModel) -> ModelMeta:
    """Build the ModelMeta for a huddle, including suggestion prompts."""
    meta = ModelMeta(
        profile_image_url=huddle.logo_url or "/static/favicon.png",
        description=get_huddle_model_description(huddle),
    )
    # ModelMeta allows extra fields via ConfigDict(extra="allow")
    # We need to add suggestion_prompts as an extra field
    meta.suggestion_prompts = DEFAULT_SUGGESTION_PROMPTS
    return meta


def ensure_huddle_model(
    huddle: HuddleModel,
    system_user_id: str = "system",
    base_model_id: Optional[str] = None,
) -> bool:
    """
    Ensure a huddle-specific model exists in the database.
    Creates or updates the model with current huddle branding.

    Args:
        huddle: The HuddleModel to create a model for
        system_user_id: User ID to own the model (default: "system")
        base_model_id: Override the base model (default: Claude Sonnet)

    Returns:
        True if successful, False otherwise
    """
    model_id = get_huddle_model_id(huddle)
    base_model = base_model_id or DEFAULT_BASE_MODEL

    try:
        # Check if model already exists
        existing = Models.get_model_by_id(model_id)

        # Build model meta with huddle branding
        meta = build_huddle_model_meta(huddle)

        if existing:
            # Update existing model with current branding
            log.info(f"Updating huddle model: {model_id}")
            result = Models.update_model_by_id(
                model_id,
                ModelForm(
                    id=model_id,
                    base_model_id=base_model,
                    name=get_huddle_model_name(huddle),
                    meta=meta,
                    params=ModelParams(),
                    is_active=True,
                )
            )
            return result is not None
        else:
            # Create new model
            log.info(f"Creating huddle model: {model_id}")
            result = Models.insert_new_model(
                ModelForm(
                    id=model_id,
                    base_model_id=base_model,
                    name=get_huddle_model_name(huddle),
                    meta=meta,
                    params=ModelParams(),
                    is_active=True,
                ),
                user_id=system_user_id,
            )
            if result:
                log.info(f"Created huddle model: {model_id}")
                return True
            return False

    except Exception as e:
        log.error(f"Failed to ensure huddle model for {huddle.slug}: {e}")
        return None


def ensure_all_huddle_models(system_user_id: str = "system") -> int:
    """
    Ensure all active huddles have corresponding models.
    Useful for startup initialization.

    Returns:
        Number of models created/updated
    """
    count = 0
    try:
        huddles = Huddles.get_all_huddles(include_deleted=False, limit=100)
        log.info(f"Found {len(huddles)} huddles to create models for")
        for huddle in huddles:
            if ensure_huddle_model(huddle, system_user_id):
                count += 1
    except Exception as e:
        log.error(f"Failed to ensure all huddle models: {e}")

    log.info(f"Ensured {count} huddle models")
    return count


def get_default_model_for_huddle(huddle: HuddleModel) -> Optional[str]:
    """
    Get the default model ID for a huddle.
    Ensures the model exists before returning.

    Args:
        huddle: The HuddleModel

    Returns:
        The model ID if available, None otherwise
    """
    model_id = get_huddle_model_id(huddle)

    # Try to get existing model first
    existing = Models.get_model_by_id(model_id)
    if existing:
        return model_id

    # Create the model if it doesn't exist
    if ensure_huddle_model(huddle):
        return model_id

    return None

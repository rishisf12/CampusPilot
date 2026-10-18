"""Audio summary module - generate TTS summaries for opportunities."""

from typing import Optional


class AudioSummaryGenerator:
    """
    Generates short text-to-speech summaries.
    Feature flag: ENABLE_AUDIO_SUMMARY (default OFF, stretch goal)
    """

    def __init__(self):
        self._enabled = False

    def enable(self):
        """Enable audio summary generation."""
        self._enabled = True

    def disable(self):
        """Disable audio summary generation."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if audio summary generation is enabled."""
        return self._enabled

    async def generate_summary(
        self,
        opportunity: dict,
        output_format: str = "mp3",
    ) -> Optional[bytes]:
        """
        Generate audio summary for an opportunity.
        Returns audio bytes or None if generation fails.
        """
        if not self._enabled:
            return None

        try:
            # TODO: Implement NVIDIA hosted TTS
            # For now, return None (feature is stretch goal)
            return None

        except Exception:
            return None

    def get_summary_text(self, opportunity: dict) -> str:
        """Get the text that would be spoken."""
        title = opportunity.get("title", "")
        org = opportunity.get("organization_name", "")
        opp_type = opportunity.get("opportunity_type", "opportunity")
        location = opportunity.get("location", "")
        deadline = opportunity.get("registration_deadline", "")

        parts = [f"{title} at {org}."]
        if opp_type:
            parts.append(f"This is a {opp_type}.")
        if location:
            parts.append(f"Location: {location}.")
        if deadline:
            parts.append(f"Apply before {deadline}.")

        return " ".join(parts)

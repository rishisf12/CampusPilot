"""Banner generation module - generate card banners for opportunities."""

from typing import Optional


class BannerGenerator:
    """
    Generates card banners for opportunities.
    Feature flag: ENABLE_BANNER_GEN (default OFF)
    Uses NVIDIA hosted image endpoints with SVG/Tailwind fallback.
    """

    def __init__(self):
        self._enabled = False

    def enable(self):
        """Enable banner generation."""
        self._enabled = True

    def disable(self):
        """Disable banner generation."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if banner generation is enabled."""
        return self._enabled

    def generate_svg_banner(self, opportunity: dict) -> str:
        """
        Generate an SVG banner as fallback.
        Returns SVG string.
        """
        title = opportunity.get("title", "Opportunity")
        org = opportunity.get("organization_name", "")
        opp_type = opportunity.get("opportunity_type", "Internship")
        location = opportunity.get("location", "")

        # Truncate long titles
        if len(title) > 40:
            title = title[:37] + "..."

        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300" viewBox="0 0 600 300">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#4f46e5;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#7c3aed;stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="600" height="300" fill="url(#bg)" rx="12"/>
  <text x="30" y="60" font-family="system-ui" font-size="14" fill="#e0e7ff" font-weight="500">{opp_type}</text>
  <text x="30" y="120" font-family="system-ui" font-size="28" fill="#ffffff" font-weight="700">{title}</text>
  <text x="30" y="170" font-family="system-ui" font-size="18" fill="#c7d2fe">{org}</text>
  <text x="30" y="220" font-family="system-ui" font-size="14" fill="#a5b4fc">{location}</text>
</svg>"""
        return svg

    async def generate_banner(self, opportunity: dict) -> Optional[str]:
        """
        Generate a banner URL for an opportunity.
        Returns URL string or None if generation fails.
        """
        if not self._enabled:
            return None

        try:
            # TODO: Implement NVIDIA hosted image generation
            # For now, return SVG data URI
            svg = self.generate_svg_banner(opportunity)
            import base64
            svg_b64 = base64.b64encode(svg.encode()).decode()
            return f"data:image/svg+xml;base64,{svg_b64}"

        except Exception:
            return None

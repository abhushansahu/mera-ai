from app.adapters.obsidian.client import ObsidianAdapter

# Export as ObsidianClient for backward compatibility
ObsidianClient = ObsidianAdapter

__all__ = ["ObsidianAdapter", "ObsidianClient"]

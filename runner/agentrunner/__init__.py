"""A job runner that verifies before it acts.

    from agentrunner.tools import Tools
    from agentrunner.loop import oldest_job, run_job

The guarantees live in two places: `fence.py` decides where a run may write,
`tools.py` decides what it may never write. Everything else is plumbing.
"""

from .fence import Fence, FenceError
from .journal import Journal
from .tools import ToolError, Tools, dispatch

__all__ = ["Fence", "FenceError", "Journal", "ToolError", "Tools", "dispatch"]
__version__ = "0.1.0"

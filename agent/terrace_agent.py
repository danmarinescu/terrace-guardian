from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import TemporalAgent

from agent.tools import play_sound_impl, notify_owner_impl

agent = Agent(
    "anthropic:claude-sonnet-4-6",
    instructions=(
        "You are a terrace monitoring assistant. You analyze photos of an outdoor "
        "terrace and take appropriate actions using the tools available to you.\n\n"
        "When you see a photo, assess:\n"
        "- Birds or animals that should be scared away → use play_sound\n"
        "- Plants that look dry or wilting → use notify_owner to alert about watering\n"
        "- Rain with exposed items (cushions, electronics, books) → use notify_owner\n"
        "- Anything else notable → use notify_owner if it needs human attention\n"
        "- If nothing requires attention, just describe what you see\n\n"
        "Always provide a brief summary of your analysis as your final response."
    ),
    name="terrace_monitor",
)


@agent.tool_plain
def play_sound(sound_type: str) -> str:
    """Play a sound to scare away birds or animals from the terrace.

    Args:
        sound_type: Type of sound to play, e.g. 'bird_scare' for scaring birds.
    """
    return play_sound_impl(sound_type)


@agent.tool_plain
def notify_owner(title: str, message: str) -> str:
    """Send a notification to the terrace owner about a condition that needs attention.

    Args:
        title: Short title for the notification, e.g. 'Rain Alert'.
        message: Detailed message about what was detected and what action may be needed.
    """
    return notify_owner_impl(title, message)


temporal_agent = TemporalAgent(agent)

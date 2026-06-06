"""prompts — extracted from univ_defs.py."""

from __future__ import annotations

import logging

from emmykit.logging_utils import fallback_logging_config


def prompt_then_confirm(prompt: str) -> bool:
    """Prompt the user with the given message and return True if the user enters 'yes', False otherwise."""
    confirmation = input(prompt)
    return confirmation.casefold() == "yes" or confirmation.casefold() == "y"

def prompt_then_choose(prompt: str, choices: list[str], default: str | None = None) -> str:
    """
    Show a numbered list of choices and prompt the user to select one.

    Args:
        prompt:  The message to display before the choices.
        choices: A list of choices to present to the user.
        default: The default choice to return if the user presses Enter without inputting a choice.

    Returns:
        str : The selected choice from the list (or the default if provided).

    Raises:
        None: If the user input is invalid, it will keep prompting until a valid choice is made.
    """
    fallback_logging_config()

    logging.info(prompt)
    for i, choice in enumerate(choices, 1):
        logging.info("  %d) %s", i, choice)
    prompt = f"Select [1-{len(choices)}]"
    if default is not None:
        prompt += f" (default {default}): "
    else:
        prompt += ": "

    while True:
        ans = input(prompt).strip()
        if not ans and default:
            logging.info("No input provided, using default: %s", default)
            return default
        if ans.isdigit() and 1 <= int(ans) <= len(choices):
            logging.info("User selected choice %d: %s", int(ans), choices[int(ans)-1])
            return choices[int(ans)-1]
        logging.warning("Invalid choice, try again.")

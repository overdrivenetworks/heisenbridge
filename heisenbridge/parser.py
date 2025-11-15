import re
from typing import Dict
from typing import Optional
from typing import Pattern

from mautrix.types import UserID
from mautrix.util.formatter.formatted_string import EntityType
from mautrix.util.formatter.html_reader import HTMLNode
from mautrix.util.formatter.markdown_string import MarkdownString
from mautrix.util.formatter.parser import MatrixParser
from mautrix.util.formatter.parser import RecursionContext
from mautrix.util.formatter.parser import T

IRC_ALLOWED_CONTROL_CHARS = (
    "\x02"  # bold
    "\x03"  # ASCII color
    "\x04"  # hex color
    "\x1d"  # italics
    "\x1e"  # strikethrough
    "\x1f"  # underline
    "\u200b"  # ZWSP (not strictly IRC formatting, but added here for convenience)
)


class IRCString(MarkdownString):
    def format(self, entity_type: EntityType, **kwargs) -> "IRCString":
        if entity_type == EntityType.BOLD:
            self.text = f"\x02{self.text}\x02"
        elif entity_type == EntityType.ITALIC:
            self.text = f"\x1d{self.text}\x1d"
        elif entity_type == EntityType.STRIKETHROUGH:
            self.text = f"\x1e{self.text}\x1e"
        elif entity_type == EntityType.UNDERLINE:
            self.text = f"\x1f{self.text}\x1f"
        elif entity_type == EntityType.URL:
            if kwargs["url"] != self.text:
                self.text = f"{self.text} ({kwargs['url']})"
        elif entity_type == EntityType.EMAIL:
            self.text = self.text
        elif entity_type == EntityType.PREFORMATTED:
            self.text = re.sub(r"\n+", "\n", self.text) + "\n"
        elif entity_type == EntityType.INLINE_CODE:
            self.text = f'"{self.text}"'
        elif entity_type == EntityType.BLOCKQUOTE:
            children = self.trim().split("\n")
            children = [child.prepend("> ") for child in children]
            self.text = self.join(children, "\n").text
        elif entity_type == EntityType.USER_MENTION:
            if kwargs["displayname"] is not None:
                self.text = kwargs["displayname"]
        elif entity_type == EntityType.COLOR:
            if kwargs["color"] is not None:
                color = kwargs["color"].lstrip("#")
                self.text = f"\x04{color}{self.text}\x04"

        return self


class IRCMatrixParser(MatrixParser):
    fs = IRCString
    list_bullets = ("-", "*", "+", "=")
    displaynames = Dict[str, str]

    # use .* to account for legacy empty mxid
    mention_regex: Pattern = re.compile("https://matrix.to/#/(@.*:.+)")

    def __init__(self, displaynames: Dict[str, str]) -> T:
        self.displaynames = displaynames

    async def tag_aware_parse_node(self, node: HTMLNode, ctx: RecursionContext) -> T:
        msgs = await self.node_to_tagged_fstrings(node, ctx)
        output = self.fs()
        prev_was_block = True
        for msg, tag in msgs:
            if tag in self.block_tags:
                msg = msg.trim()
                if not prev_was_block:
                    output.append("\n")
                prev_was_block = True
            else:
                prev_was_block = False
            output = output.append(msg)
        return output.trim()

    async def user_pill_to_fstring(self, msg: T, user_id: UserID) -> Optional[T]:
        displayname = None
        if user_id in self.displaynames:
            displayname = self.displaynames[user_id]
        return msg.format(self.e.USER_MENTION, user_id=user_id, displayname=displayname)

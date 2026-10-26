---
name: setup
description: Name this Machine and set the Factory server's address. Run once per Machine.
disable-model-invocation: true
---

Ask the human, in one question each unless they already gave them as arguments:

1. A name for this Machine (e.g. `wsl`, `windows`, `mac`). WSL and Windows on one PC are two Machines.
2. The Factory server's URL (e.g. `http://mac.local:47821`).

Then run `factory setup --machine <name> --server <url>` and show its output.

It prints a shell alias for running `factory` from a plain terminal. Offer to add that line to the human's shell profile (the file it names); add it only if they say yes.

Arguments: $ARGUMENTS

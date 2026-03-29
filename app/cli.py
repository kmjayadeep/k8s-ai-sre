from dataclasses import dataclass, field


@dataclass
class Command:
    name: str
    args: tuple = field(default_factory=tuple)


def parse_cli_args(argv: list[str]) -> Command:
    if len(argv) >= 2 and argv[1] == "serve":
        port = int(argv[2]) if len(argv) >= 3 else 8080
        return Command("serve", (port,))

    if len(argv) >= 2 and argv[1] == "telegram-poll":
        return Command("telegram-poll")

    if len(argv) == 4 and argv[1] == "propose-delete-pod":
        return Command("propose-delete-pod", (argv[2], argv[3]))

    if len(argv) == 4 and argv[1] == "propose-rollout-restart":
        return Command("propose-rollout-restart", (argv[2], argv[3]))

    if len(argv) == 5 and argv[1] == "propose-scale":
        return Command("propose-scale", (argv[2], argv[3], int(argv[4])))

    if len(argv) == 4 and argv[1] == "propose-rollout-undo":
        return Command("propose-rollout-undo", (argv[2], argv[3]))

    if len(argv) == 3 and argv[1] == "approve":
        return Command("approve", (argv[2],))

    if len(argv) == 3 and argv[1] == "reject":
        return Command("reject", (argv[2],))

    if len(argv) >= 4 and argv[1] == "delete-pod":
        confirm = len(argv) >= 5 and argv[4] == "--confirm"
        return Command("delete-pod", (argv[2], argv[3], confirm))

    if len(argv) >= 4 and argv[1] == "rollout-restart":
        confirm = len(argv) >= 5 and argv[4] == "--confirm"
        return Command("rollout-restart", (argv[2], argv[3], confirm))

    if len(argv) >= 5 and argv[1] == "scale":
        confirm = len(argv) >= 6 and argv[5] == "--confirm"
        return Command("scale", (argv[2], argv[3], int(argv[4]), confirm))

    if len(argv) >= 4 and argv[1] == "rollout-undo":
        confirm = len(argv) >= 5 and argv[4] == "--confirm"
        return Command("rollout-undo", (argv[2], argv[3], confirm))

    if len(argv) == 4:
        return Command("investigate", (argv[1], argv[2], argv[3]))

    return Command("investigate", ("deployment", "ai-sre-demo", "bad-deploy"))

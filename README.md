# Retired

This experimental orchestration policy is retired. Do not install or use it.

It added a private dispatcher, model-routing rules, prompt bridges, guards, and retry constraints on top of Herdr. In practice, that duplicated the runtime’s job, made sessions brittle, and could consume more tokens than direct execution.

Use Herdr’s official, version-matched skill instead:

```sh
herdr --skill
```

Official source: [herdrdev/herdr](https://github.com/herdrdev/herdr) and its [Herdr skill](https://github.com/herdrdev/herdr/blob/master/skills/herdr/SKILL.md).

This repository remains only as a historical record. Its installer, guard, dispatcher skill, migration script, and tests were removed on 2026-08-10.

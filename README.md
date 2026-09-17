# moe-skills

harukizmoe's reusable Agent Skills. One skill per directory under `skills/`,
`SKILL.md` as the entry point — every skill is self-contained and independently
installable.

## Skills

| Skill | Description | Version |
|---|---|---|
| [herdr-collab](skills/herdr-collab/) | Herdr layout and pane commands plus agent lifecycle: create panes, start agents, discover, verify, prompt, and read coding-agent results. | 0.1.1 |

## Installation

Install a single skill with the [skills CLI](https://github.com/vercel-labs/skills):

```bash
# list available skills
npx skills add harukizmoe/moe-skills --list

# install one skill
npx skills add harukizmoe/moe-skills --skill herdr-collab

# install globally (across projects)
npx skills add harukizmoe/moe-skills --skill herdr-collab --global
```

The repo is the canonical source; installed copies are deployment targets.
Update with `npx skills update`.

## Development

- Layout: `skills/<name>/SKILL.md` (+ optional `references/`, `scripts/`, `tests/`).
- Skill name must equal its directory name and be unique repo-wide.
- Skills are self-contained: no inter-skill dependencies.
- Version each skill independently (SemVer); tag `herdr-collab/vX.Y.Z`;
  changelog per skill (`CHANGELOG.md`).
- `main` must always be installable. Behavior changes go through PRs.
- CI validates structure on every push/PR (`.github/workflows/validate.yml`).

## License

MIT

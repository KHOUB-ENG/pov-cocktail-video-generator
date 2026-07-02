# Repository Structure

The repository is intentionally separated into distinct concerns:

| Category          | Folder       |
| ----------------- | ------------ |
| Source Code       | `src/`       |
| Generated Content | `protocols/` |
| Generated Media   | `assets/`    |
| Persistent Data   | `data/`      |
| Runtime Logs      | `logs/`      |
| Documentation     | `docs/`      |
| Testing           | `tests/`     |

This separation keeps application code, generated outputs, media assets, system memory, and documentation independent and easy to maintain.

---

## Root Structure

```text
pov-cocktail-video-generator/
│
├── src/
├── protocols/
├── assets/
├── data/
├── logs/
├── docs/
├── tests/
│
├── .env
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Source Code

### `src/`

Contains all application source code.

Nothing in this folder should contain generated content, generated media, or persistent data.

Future structure:

```text
src/
└── pov_cocktail/
    ├── agents/
    ├── orchestrator/
    ├── protocols/
    ├── storage/
    ├── generation/
    └── config/
```

### `agents/`

Specialist AI workers.

Examples:

* Creative Director
* Recipe Architect
* Science Director
* Storyboard Director
* Voice Director
* Prompt Director
* Publishing Director

Purpose: Perform the creative and reasoning work.

---

### `orchestrator/`

Controls workflow execution.

Purpose: Coordinates agent execution and manages Protocol generation.

Acts as the system brain.

---

### `protocols/`

Contains Protocol models and lifecycle logic.

Purpose: Defines what a Protocol is and how it moves through the system.

Contains code only, not generated Protocol content.

---

### `storage/`

Database and persistence layer.

Purpose: Save, load, update and query data.

Prevents agents from interacting directly with SQLite.

---

### `generation/`

External AI service integrations.

Examples:

* OpenAI
* ElevenLabs
* Ideogram
* Kling

Purpose: Keeps API communication separate from business logic.

---

### `config/`

Application settings and constants.

Examples:

* Model names
* Database paths
* Cost limits
* Global configuration

Purpose: Centralised configuration management.

---

## Generated Content

### `protocols/`

Stores completed Protocol packages.

Example:

```text
protocols/
└── 004-negroni/
```

May contain:

```text
concept.md
recipe.md
storyboard.md
voiceover.md
prompts.md
upload-pack.md
```

Think:

> What did the AI create?

---

## Generated Media

### `assets/`

Stores generated media files.

Example:

```text
assets/
└── 004-negroni/
```

May contain:

```text
hero.png
scene01.png
clip01.mp4
voice01.mp3
final.mp4
```

Think:

> What media files were generated?

---

## Persistent Data

### `data/`

Stores system memory.

Primary file:

```text
data/pov_cocktail.db
```

Stores:

* Protocol records
* Asset references
* Analytics
* Cost tracking
* Knowledge base
* Metadata

Does not store generated content or media.

Think:

> What does the system remember?

---

## Runtime Logs

### `logs/`

Stores runtime activity records.

Examples:

```text
app.log
errors.log
```

Tracks:

* Agent execution
* API calls
* Costs
* Errors
* Performance metrics

Think:

> What did the system do?

---

## Documentation

### `docs/`

Human-readable project documentation.

Contains:

* Architecture decisions
* Design notes
* Development principles
* Planning documents

Think:

> How does the project work?

### `docs/architecture/`

Core architecture documentation.

Files:

* `vision.md` → project purpose and long-term goals
* `requirements.md` → functional and non-functional requirements
* `system-design.md` → architecture and component design
* `roadmap.md` → development phases and milestones

### `meeting-notes.md`

Architectural decision log.

Records important decisions and their rationale.

---

## Testing

### `tests/`

Automated tests.

Purpose: Ensure future changes do not break existing functionality.

Currently empty because implementation has not started.

---

# Architectural Principle

The project is organised around a simple separation of concerns:

* `src/` = The code
* `protocols/` = What the AI writes
* `assets/` = What the AI generates
* `data/` = What the system remembers
* `logs/` = What the system does
* `docs/` = How the project works

This structure supports a clean, maintainable, local-first architecture centred around the generation of complete POV Cocktail Protocols.

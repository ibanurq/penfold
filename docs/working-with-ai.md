# Working with an AI assistant

Penfold is developed by a person who does not write code, together with an AI coding assistant. This document
describes the working method, so that anyone can reproduce it with an AI assistant of their choice.

## Starting a session

Give the assistant this repository and ask it to read, in this order:

1. this document;
2. [specification.md](specification.md), which describes the app as it is and how it is built;
3. the code (`penfold/`, the interface files in `data/ui/` and the tests in `tests/`).

Then say what you want to do. The code is the source of truth: if the specification disagrees with it, the code wins,
and the specification is corrected.

## Rules of conversation

- **Language:** the person and the assistant talk in Spanish. Everything in the repository (code, comments, commit
  messages, documentation) is in English. The interface is in American English and is translated with gettext; the
  Spanish translation is always kept up to date.
- **Explain first.** Before running a command or changing a file, the assistant explains in plain words what it will
  do and why. The person is not expected to know git or programming terms; when one is needed, it is explained in a
  sentence.
- **One question at a time.** When there are several options, the assistant explains their advantages and limits and
  recommends one. The person decides.
- **Only what is asked.** No other part of the code is touched, and the assistant adds nothing on its own initiative,
  even if it looks like an improvement: it suggests it instead.
- **“Don’t program” or “let’s leave it”** mean: talk about options without touching the code.
- **No half implementations.** If something cannot be done or does not fit the PDF format, the assistant says so,
  explains why and carries on with the rest.
- **Stop after each commit.** The assistant waits for the person to say it can go on.

## Design first, then code

Before any programming, the complete design of the version was written and agreed with the person: what it does and
what it does not, how it looks (with mockups), how it is built, the plan in phases and every decision with its reason.
That design is kept private.

- **The scope is closed.** A new idea goes on a list for later, unless the person decides to change the scope; then it
  is recorded as a decision and the design is updated before it is programmed.
- If something in the design cannot be done, is ambiguous or conflicts with something else, the assistant asks instead
  of deciding on its own.

## In phases

- The work is split into phases. At the start of each one, the assistant proposes what it includes and how it will be
  done (how it will look and behave, and in which steps), and programs nothing until the person confirms.
- **Small steps:** the code with its tests, and a commit with a single idea. Before each commit, the assistant reviews
  its own code as a demanding colleague would.
- At the end of a phase, the assistant checks with the real app what the phase had to achieve and shows screenshots of
  anything that looks different. The person tries it and, if they approve, the phase closes with a test version
  (alpha) and an entry in `CHANGELOG.md`.
- **One conversation per phase.** When closing one, the assistant writes down in the private notes where the work
  stands and what comes next, so that the next conversation starts with everything clear. It also says when a
  conversation has grown so long that it is better to continue in a new one.
- After the phases come the betas, which the person uses in their daily work; what they find is fixed in further
  betas. Then a release candidate and, if nothing turns up, the final version.

## Original code

- All the code is written from scratch for Penfold. No code from other apps is copied or adapted, even if their
  license would allow it, and their source code is not opened for guidance.
- “As in such-and-such app” refers to the look and the behavior, which are achieved with the standard GTK and
  libadwaita widgets, following the official documentation of the libraries and the GNOME guidelines.
- Nothing from third parties (icons, images, texts, fonts) goes in without the person’s approval, and it is recorded
  in `THIRD-PARTY-NOTICES.md` with its author and license.

## Safety net: automatic checks

Every change must keep the app working exactly the same, except for what was asked for. That is checked automatically,
not by eye:

- Before every commit, Ruff (style and likely mistakes), mypy (types) and pytest (tests) run, with no warnings allowed.
  GitHub Actions repeats it all on every push and builds the Flatpak.
- A new feature or a bug fix comes with its test. The document tests open, change, undo, save and reopen PDFs and
  check the result, because that is where data can be lost. The interface tests drive the real windows on a virtual
  display, never on the person’s screen.
- The details (rules, tools, how to set up the environment and run the app from the source code) are in the
  specification, under “Quality, tests and building”.

## Versions and git

- Each change is a separate commit with a clear message, so it can be reviewed and undone on its own.
- **The assistant never publishes.** It does not run `git push`: when something has to go to GitHub, it gives the
  person the folder, a command to review which commits will be sent and the exact command, explained in plain words,
  and the person runs it.
- Releases are created by the person on GitHub, with the Flatpak built by GitHub Actions.
- Private notes (the design, research, ideas not yet decided) are kept outside the repository, in a folder ignored by
  git.

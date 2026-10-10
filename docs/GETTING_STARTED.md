# Getting started: connect Claude to this repo

This guide is for someone who has never used Claude with GitHub. Follow the steps in order. Each step ends with a check. If a check fails, stop and fix it before moving on.

**Never paste passwords, tokens, or API keys into chat or into any file in this repo.**

## What you need

- A GitHub account with access to this repo.
- A Claude account with Claude Code access (a paid Claude plan or an API key). Check your plan at claude.ai.
- Git installed.
- Python 3.10 or newer.
- Node.js 18 or newer, only if you use the npm install in Step 4.
- A Kaggle account (needed later for the GPU fine-tune, Step 5b of the spec).

## Step 1: Install Git

1. Download Git from https://git-scm.com/downloads and install it. Default options are fine.
2. Open a new terminal and run:

```bash
git --version
```

**Check:** it prints a version number such as `git version 2.x`.

## Step 2: Install the GitHub CLI and log in

The GitHub CLI (`gh`) lets Git and Claude use your GitHub login without you pasting a token anywhere.

1. Install it from https://cli.github.com.
2. Log in:

```bash
gh auth login
```

3. Answer the prompts:
   - Account: **GitHub.com**
   - Protocol: **HTTPS**
   - Authenticate Git with your GitHub credentials: **Yes**
   - Login method: **Login with a web browser**
4. Copy the one-time code shown in the terminal, paste it in the browser page that opens, and approve.

**Check:**

```bash
gh auth status
```

It should say "Logged in to github.com". If it does not, run `gh auth login` again.

## Step 3: Set your Git name and email

Commits need an author. Use your own details. Run these once:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

**Check:**

```bash
git config --global user.email
```

It should print your email.

## Step 4: Clone the repo

Pick a folder where you keep projects, then run:

```bash
git clone https://github.com/Elena549-prog/Hackathon_neatlogs.git
cd Hackathon_neatlogs
```

**Check:**

```bash
git log --oneline -3
```

You should see the commits `bdf6807`, `7ee33e3`, and the others.

## Step 5: Install Claude Code

Claude Code is the tool that reads this repo and runs the steps for you.

1. Install it with the official instructions at https://docs.anthropic.com/en/docs/claude-code (look for the install method for your operating system). If you have Node.js, this also works:

```bash
npm install -g @anthropic-ai/claude-code
```

2. Check the install:

```bash
claude --version
```

**Check:** it prints a version number. If it says "command not found", close and reopen the terminal, then try again.

## Step 6: Start Claude in the repo and log in

1. From inside the `Hackathon_neatlogs` folder, run:

```bash
claude
```

2. The first time, Claude asks you to trust this folder. Read the prompt. Trust it only because this is the repo you cloned.
3. Log in when prompted. It opens a browser. Sign in with your Claude account and approve.

**Check:** the Claude prompt opens and you can type a message.

## Step 7: Confirm Claude reads the project instructions

Type this in the Claude prompt:

```
What does CLAUDE.md say about where to start?
```

**Check:** Claude names `docs/SPEC.md` as the place to start. If it does not, make sure you started `claude` from the repo's top-level folder, not a subfolder.

## Step 8: Create your working branch

Do not work on `main`. In a second terminal (or after exiting Claude with `/exit`), run:

```bash
git checkout -b step-1-4
```

Then start `claude` again from the same folder.

**Check:**

```bash
git branch --show-current
```

It should print `step-1-4`.

## Step 9: Give Claude the first task

Type this in the Claude prompt:

```
Follow docs/SPEC.md. Start with section 1 (repo setup). Stop and report after each step's "Done when" check, and do not start the next step until I say so.
```

Claude will ask permission before it runs commands or edits files. Read each request before you approve it.

- Approve commands that install packages, create folders, or run tests.
- Stop and ask if a request asks to push to `main`, delete files, or use a token.
- Do not switch to a mode that skips permission prompts.

## Step 10: Push your work

After each step passes its checks, Claude should commit. To push your branch:

```bash
git push -u origin step-1-4
```

**Check:** the branch appears on GitHub at https://github.com/Elena549-prog/Hackathon_neatlogs/branches.

## Troubleshooting

| Problem | Fix |
|---|---|
| `gh auth status` says not logged in | Run `gh auth login` again and finish the browser step. |
| `git push` asks for a password | Run `gh auth setup-git`, then push again. Do not type a password into chat. |
| `claude` says not logged in | Run `claude`, then complete the browser login. |
| `python` not found | Install Python 3.10+ from python.org and reopen the terminal. On Windows, try `py` instead of `python`. |
| Claude does not mention `CLAUDE.md` | Confirm you are in the top-level repo folder with `pwd` (macOS/Linux) or `cd` (Windows). |
| Push rejected | Run `git pull origin step-1-4` first, then push again. Ask for help if there is a conflict. |

## Rules to keep

- Work on `step-1-4`, not `main`.
- Never commit `data/`, `runs/`, checkpoints, `.env` files, or tokens. The `.gitignore` covers them. Check with `git status` before each commit.
- Stop and ask the project owner before any step marked "Stop and report" in `docs/SPEC.md`.

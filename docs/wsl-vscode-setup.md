# WSL and VS Code Setup — Phase 1–4 Checkpoint

The ZIP contains one top-level folder, so it can be extracted once without
scattering files. Use Ubuntu in WSL and VS Code with the WSL extension.

## 1. Move the ZIP to the Windows laptop

Download `Daily-Checkin-Part1-Configuration-v0.5.0.zip` into the Windows Downloads
folder. Email, WhatsApp Web, USB, or another approved transfer method is fine
for this source-only ZIP. Do not use those channels later for company secrets or
private evidence.

## 2. Extract once into WSL

Open Ubuntu/WSL and run:

```bash
sudo apt update
sudo apt install -y unzip make python3 python3-venv
mkdir -p "$HOME/projects"
unzip -q /mnt/c/Users/godsw/Downloads/Daily-Checkin-Part1-Configuration-v0.5.0.zip -d "$HOME/projects"
cd "$HOME/projects/daily-checkin-part1-platform"
```

If the Windows account is not `godsw`, replace `godsw` with the name shown by:

```bash
cmd.exe /c echo %USERNAME%
```

## 3. Bootstrap and validate

```bash
bash scripts/bootstrap_wsl.sh
```

The script creates a local `.venv`, installs the pinned development dependency,
runs the complete validation gate, and prints the next command. It does not
contact or change company systems.

## 4. Open the exact WSL folder in VS Code

```bash
code .
```

Confirm the lower-left VS Code indicator says `WSL: Ubuntu`. If `code` is not
available, install the Microsoft **WSL** extension in Windows VS Code, run
`wsl --shutdown` in PowerShell, reopen Ubuntu, and retry `code .`.

## 5. Confirm the checkpoint

```bash
cat VERSION
git status 2>/dev/null || true
find . -maxdepth 2 -type d | sort
```

`VERSION` must print `0.5.0`. Do not copy `.env.example` into a populated `.env`
until the company endpoints and Vault delivery method are confirmed.

## 6. Initialize and push only after the official repository is supplied

From the project root:

```bash
git init
git add .
git commit -m "feat: deliver Task 5585 Part 1 phases 1-4"
git branch -M main
git remote add origin OFFICIAL_PRIVATE_REPOSITORY_URL
git push -u origin main
```

Replace `OFFICIAL_PRIVATE_REPOSITORY_URL` with the URL provided by Friendy or
the repository owner. If the official repository already contains history,
clone it first and follow its branch/PR policy instead of initializing a new
repository. Never force-push or commit `.env`, tokens, private evidence, or
rendered runtime secret files.

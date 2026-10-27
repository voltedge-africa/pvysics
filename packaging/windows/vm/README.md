# Building the Windows app

The Windows app (a zip, and a one-file installer) has to be built on Windows: PyInstaller, which freezes the app with
its own Python and Qt, cannot cross-compile. There are two ways to get a Windows to build on.

| You have | Run | Where it is explained |
| --- | --- | --- |
| A Linux machine | `packaging/windows/vm/build-from-linux.sh` | [From Linux](#from-linux-in-a-windows-container) |
| A Windows machine | `uv run --group build python packaging/build.py` | [On Windows](#on-windows) |

Either way the result is in `dist/`:

- `pvysics-<version>-windows.zip`: the app folder. Unzip it and run `pvysics\pvysics.exe`.
- `pvysics-<version>-windows-setup.exe`: an installer (Inno Setup). It adds *PV Digital Twin* to the Start menu and,
  if the user ticks the box, to the desktop. It is only made when Inno Setup is installed on the machine that builds.

Neither file is code-signed, so Windows may warn on first run (*More info*, then *Run anyway*).

## From Linux, in a Windows container

The script starts a real Windows 11 in a container ([`dockurr/windows`](https://github.com/dockur/windows), which runs
QEMU with KVM), builds inside it and copies the results into `dist/`. It downloads Windows from Microsoft, and
Microsoft's licence terms apply to it.

### What you need

| | |
| --- | --- |
| `docker` or `podman` | the script uses `docker`, or `podman` if there is no `docker`; set `ENGINE` to choose |
| `/dev/kvm` | readable and writable by you (on most distributions, be in the `kvm` group). Without it Windows is far too slow to be useful |
| RAM and CPU | 8 GB of RAM and 4 cores go to Windows while it runs |
| Disk | up to 64 GB. The Windows disk is a sparse file, so it takes about 12 GB until the build fills it |
| Network | Windows is downloaded on the first run, and the build downloads `uv`, Inno Setup and the Python packages |
| A git checkout | the script builds from git (see the next section) |

### Run it

```
git status                                     # commit what you want built first
packaging/windows/vm/build-from-linux.sh
```

It prints where to watch the Windows screen (<http://127.0.0.1:8006>, only reachable from your machine), waits, and ends
by listing the files it put into `dist/`. The first run installs Windows, which takes about 25 minutes. After that the
Windows disk is reused and a build takes about 10 minutes. When it finishes it stops the
Windows container but does not delete it.

**It builds the last commit, not your working tree.** The script exports `HEAD` with `git archive`, so edits that are
not committed are not in the build. Uncommitted files under `packaging/windows/vm/` are the one exception: the two
`.bat` files are copied from your working tree.

### What it does, step by step

Folders on your machine (all under `$WORK`, by default `~/.cache/pvysics-winbuild`):

| Folder | Seen from Windows as | Holds |
| --- | --- | --- |
| `$STORAGE`, by default `$WORK/storage` | the disk `C:` | the installed Windows |
| `$WORK/shared` | `\\host.lan\Data` | the source, the queued build, the results and the log |
| `$WORK/oem` | read once by Windows setup | `install.bat` |

1. **Export the source.** It empties `shared/src-tree`, `shared/out` and `shared/DONE`, then runs `git archive HEAD` into
   `shared/src-tree`.
2. **Copy the two Windows scripts.** `install.bat` goes to `oem/`, and `build.bat` to `shared/run.bat.initial`.
3. **Start Windows, or queue the build if it is running.**
   - If the `pvysics-win` container is already running, it copies `build.bat` to `shared/run.bat`.
   - Otherwise it removes any stopped `pvysics-win` container and starts a new one on `$STORAGE`.
     If `$STORAGE` already holds an installed Windows (it has a `data.img`), it also queues `shared/run.bat`.
4. **Windows does the build.** What happens inside depends on whether Windows is new:
   - *A new disk.* Windows installs itself, then runs `install.bat` once. That script creates a scheduled task,
     `pvysics-poll`, installs `uv` and Inno Setup, and then builds by running `run.bat.initial`.
   - *An installed disk.* Windows boots in about a minute, and the `pvysics-poll` task, which runs every minute, finds
     `shared/run.bat`, moves it to `C:\run-now.bat` and runs it. This is also how a second build is queued.
5. **`build.bat`, which is the build itself.** It installs Inno Setup if `ISCC.exe` is missing, copies `src-tree` to
   `C:\src`, runs `uv run --group build python packaging/build.py`, copies the zip and the setup exe to `shared/out`,
   and writes `shared/DONE`. Its output is appended to `shared/build.log`.
6. **Collect.** The script waits for `shared/DONE`, copies `shared/out/*` into `dist/` and stops the container.

`DONE` is written whether or not the build worked. If `dist/` has no new files, read `shared/build.log`.

### Settings

Set these as environment variables when you run the script.

| Variable | Default | Meaning |
| --- | --- | --- |
| `WORK` | `~/.cache/pvysics-winbuild` | where the shared folders and, by default, the Windows disk live |
| `STORAGE` | `$WORK/storage` | the Windows disk. Point it at an installed one to skip installing Windows |
| `ENGINE` | `docker`, else `podman` | the container program |

The container's RAM, cores, disk size and viewer port are set inside the script, on the `run` line.

### Reusing a Windows you already have

`STORAGE` is how a Windows disk made some other way is reused:

```
STORAGE=$HOME/winvm/storage packaging/windows/vm/build-from-linux.sh
```

The disk needs `uv` installed and the `pvysics-poll` task, which `install.bat` creates. A disk that was made by this
script's first run has both.

If you do not give `STORAGE`, the script uses an empty folder and starts installing Windows again, downloading several
gigabytes. Do not start it that way while a Windows disk you meant to use is somewhere else.

### Watching and following progress

- The Windows screen: <http://127.0.0.1:8006>.
- The build: `tail -f ~/.cache/pvysics-winbuild/shared/build.log`.
- Whether it is done: `shared/DONE` exists.

### Cleaning up

- Do not remove the container (`docker rm -f pvysics-win`) while a build is running. Stop it, or let the script do it.
- `docker rm pvysics-win` removes the container only. The Windows disk is in `$STORAGE`, so the next run keeps it.
- `rm -rf ~/.cache/pvysics-winbuild` (or `$WORK`) removes the shared folders and the default Windows disk. The next run
  installs Windows again. If you set `STORAGE` elsewhere, that disk is not touched.

### Putting the Windows files next to the Linux ones

`packaging/build.py` deletes `dist/` when it starts, so a Linux build or `packaging/release.sh` run after the Windows
build removes the Windows files. Build Linux first, then Windows, then write the checksums:

```
packaging/release.sh                           # tests, Linux build, checksums (clears dist/ first)
packaging/windows/vm/build-from-linux.sh       # adds the Windows zip and setup exe to dist/
cd dist && sha256sum *.tar.gz *.deb *.zip *-setup.exe | tee SHA256SUMS
```

The script copies new files over old ones with the same name and removes nothing, so check the dates in `dist/` after a
run. An older `-setup.exe` that this build did not make would stay there looking current.

### Problems

| Problem | What to check |
| --- | --- |
| It stops at once, or says KVM is missing | `ls -l /dev/kvm`, and that your user can read and write it. Virtualisation must be on in the firmware |
| Docker says it cannot connect or is denied | the Docker service is running and your user can use it |
| It waits a long time with nothing new | open the viewer on port 8006. A new disk takes 25 minutes; an installed one should boot in about a minute and then needs up to one more minute for the poll task |
| It finishes, but `dist/` has no new files | read `shared/build.log`, from the last `--- building` line |
| There is a zip but no setup exe | the log should show `installing Inno Setup`. If that download failed, the build skips the installer without an error |
| The viewer port is in use | another program has port 8006. Change the `-p` in the script |
| Two builds at once | do not. The second one empties `shared/src-tree` under the first |

## On Windows

On a Windows machine with [uv](https://docs.astral.sh/uv/) installed:

```
uv run --group build python packaging/build.py
```

This makes the zip, and the setup exe too if Inno Setup 6 (`iscc`) is installed and on the `PATH`. Get it from
<https://github.com/jrsoftware/issrc/releases> (the files are called `innosetup-6.x.exe`). The build starts by deleting
`dist/`.

## Files in this folder

| File | Used by | Does |
| --- | --- | --- |
| `build-from-linux.sh` | you, on Linux | starts the container, queues the build, collects the results |
| `install.bat` | Windows setup, once | creates the poll task, installs `uv` and Inno Setup, then builds |
| `build.bat` | every build, inside Windows | installs Inno Setup if missing, builds, copies the results out and writes `DONE` |

The Inno Setup script is `../pvysics.iss`, and the freeze is described in `../pvysics.spec`.

## What has been verified

- **Run end to end on an installed Windows disk (27 October 2026, about 12 minutes).** With `STORAGE` pointing at the
  disk from the first build, the script queued the build, the poll task picked it up, `build.bat` installed Inno Setup
  6.7.3 into a Windows that did not have it, and built the zip and the setup exe from the last commit. The script then
  copied both into `dist/` and stopped the container. The frozen app contains the simple window of that commit.
- **Not run as one script: a brand-new Windows.** The first-run path (an empty `STORAGE`, Windows installing, then
  `install.bat`) was run by hand for v0.1.1, with the same steps, but not through this script from start to finish.
- **Not tested: the result on Windows.** The zip and the setup exe have not been unzipped, installed or started on a
  Windows machine here, and `podman` has not been tried.

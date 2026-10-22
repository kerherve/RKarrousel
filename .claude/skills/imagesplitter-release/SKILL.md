---
name: imagesplitter-release
description: Release workflow for imageSplitter. Use when tagging a new version, cutting a release, or publishing PhotoSplitter.exe. Every release MUST ship a freshly built Windows .exe.
---

# imageSplitter release

Every new release (git tag `vX.Y.Z`) requires a freshly built `PhotoSplitter.exe`
built from the tagged commit. Never reuse an old `dist/PhotoSplitter.exe`.

## Versioning (semver, currently 0.x)
- `0.MINOR.0` for new features, `0.x.PATCH` for fixes. Go to `1.0.0` when the app is considered stable.
- Last release: check `git tag --sort=-v:refname | head -1`.

## Steps
1. Make sure the work is committed and pushed on `master` (`git status` clean apart from ignored/untracked build output).
2. Pick the next version, set `__version__` in `version.py` (shown in the GUI title and the "À propos" dialog), commit and push it, then create an annotated tag on that commit: `git tag -a vX.Y.Z -m "vX.Y.Z - summary"`. The tag must never be created before the version bump.
3. Build the .exe from WSL using the Windows Python (`python.exe`/`py.exe` are on the PATH). `cmd.exe` rejects UNC paths,
   so build in a Windows folder from the tagged sources, then copy the result into `dist/`:
   ```
   W=/mnt/c/Users/riwal/AppData/Local/Temp/imagesplitter_build
   rm -rf $W && mkdir -p $W && git archive vX.Y.Z | tar -x -C $W
   (cd $W && cmd.exe /c build_windows.bat)
   cp $W/dist/PhotoSplitter.exe dist/PhotoSplitter.exe
   ```
   The final `dist/PhotoSplitter.exe` must always be the one built for the release being cut.
4. Install locally for the user (their desktop shortcut points at the unversioned name): copy the new build into
   `/mnt/c/Users/riwal/Photos/imageSplitter/dist/` as TWO files, overwriting the old ones:
   `PhotoSplitter.exe` (stable name, used by the shortcut) and `PhotoSplitter-vX.Y.Z.exe` (versioned copy).
   Leave `.image_splitter_config.json` in that folder untouched (it holds the user's preferences).
5. Push the tag: `git push origin vX.Y.Z`.
6. Publish a GitHub release with the exe attached (`gh` lives in `~/.local/bin`, add it to PATH):
   first `cp dist/PhotoSplitter.exe dist/PhotoSplitter-vX.Y.Z.exe` so the asset name carries the version, then
   `gh release create vX.Y.Z dist/PhotoSplitter-vX.Y.Z.exe --title "vX.Y.Z" --notes "<changelog from git log since previous tag>"`
7. Confirm the release page lists `PhotoSplitter-vX.Y.Z.exe`.

## Notes
- Repo: https://github.com/kerherve/imageSplitter (private). Default branch: `master`.
- `build/`, `dist/` and `PhotoSplitter.spec` are build artefacts, not committed.

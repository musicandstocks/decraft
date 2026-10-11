# Decraft build download

This delivery contains the tested Linux host and the source/runtime SDK as verified 32 MiB chunks. Shared chunks are included once. The original ZIP files are reassembled exactly, with checks of every chunk and the complete archive.

1. Download this branch using GitHub's **Code → Download ZIP** button and extract it.
2. Install Python 3 if necessary, then open a terminal in the extracted folder.
3. Run `python assemble.py` (or `py assemble.py` on Windows).
4. Extract `Decraft-combined-linux-host-and-sources.zip` and run `./launch-game.sh` on Linux x64.

The Linux host includes the original Forge modpack, Java, verified assets, the Minecraft hub and five saved destination layouts. Entry/return checks and a moved BT3 checkpoint save/reload passed. These are limited imports/adaptations; full original campaigns, enemies, game-specific combat and a Windows fused-game launcher remain unfinished. The SDK includes the selected Windows DLL and matching console outputs.

The complete ZIP hashes are:

- Linux host: `72d802e117fd6c69d1e20d6f5f26a5a5906f5852158545cd826775503cd6d8d2`
- Source SDK: `3eb0553d2324f79923e0b3e7545817ed323951097ed620a6ae5a219e8f47914d`

Existing different ZIP files are preserved. Reassembly does not run the game, modify saved progress, download dependencies or publish files. All original release files remain in the development workspace.

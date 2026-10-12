# Legacy Console Edition target

Download this branch ZIP and extract it, then double-click **Install-Legacy.cmd**. This installs the supplied native Legacy Windows client with the rebuilt launcher and Xbox forwarding adapter. It does not yet include the native portal hub or ported Forge gameplay. See **Decraft-Legacy-porting-sources.zip** for all 22 readable new mod decompilations, 190 converted Halo/PvZ models, the Isaac model port and exact status manifests. The older Java downloads below are retained as references.

# Decraft build download

## Windows 10/11, 64-bit

1. Download this branch with **Code → Download ZIP** and extract it.
2. Double-click **Launch-Game.cmd** in the extracted folder.
3. The launcher downloads local, checksum-verified Python and Java 8 runtimes, reconstructs the host ZIP, and extracts the game into `Decraft-game`. No separate Python/Java installation or administrator rights are required.
4. Wait for the modpack menu; the first load can take about ten minutes. Open **New World** to use the Minecraft hub and five destination gates.

Already have the old download? Download `Decraft-Windows-launch-fix.zip` from this branch and extract its contents into your existing game folder (the one containing `runtime` and `tools`), or your original downloaded branch folder containing `assemble.py` and `chunks`. Double-click **Launch-Game.cmd**. Existing saved progress is preserved. The Windows launcher uses Java's supported IPv4 compatibility mode.

The launcher keeps its console open on errors and prints the log folder. Internet access to NuGet and GitHub is needed for the first runtime setup; subsequent launches reuse the installed local runtimes. Use a writable local folder and allow the game through local loopback firewall prompts.

## Linux x64 / source SDK

Run `python3 assemble.py`, extract `Decraft-combined-linux-host-and-sources.zip`, and run `./launch-game.sh` on a desktop with Python 3 and OpenGL/OpenAL support. Reassembly verifies every chunk and the complete ZIP and preserves existing different archives. `--archive Decraft-combined-sources-and-runtime.zip` reconstructs only the SDK.

The original host ZIP and SDK are unchanged. Windows uses the same Forge modpack, supplied Windows native libraries, shared runtime DLL, Minecraft hub and five persistent imported/adapted destinations. Complete original campaigns, enemies and game-specific combat remain unfinished. Windows executable checks run under Wine in the development environment; native Windows desktop behavior still needs verification.

Original archive SHA-256 hashes:

- Host: `72d802e117fd6c69d1e20d6f5f26a5a5906f5852158545cd826775503cd6d8d2`
- SDK: `3eb0553d2324f79923e0b3e7545817ed323951097ed620a6ae5a219e8f47914d`

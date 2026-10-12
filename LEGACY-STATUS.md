# Legacy Console Edition port status

The selected base is the supplied native Legacy Console Edition Windows64 client. Java Forge is retained as a development reference. Neither the Legacy runtime download nor the source SDK is a completed fused game.

## Launch the correct edition

Download the `build-download-20261011` branch ZIP from GitHub and extract it. Double-click **Install-Legacy.cmd**. It verifies and assembles `Decraft-Legacy-Windows.zip`, extracts into a new `Decraft-Legacy` folder, then launches **Launch-Legacy.exe**. Later launches can use **Decraft-Legacy/Launch-Legacy.cmd**. Java is not required. The installer may download the pinned local Python runtime for archive assembly.

The native launcher uses `runtime/legacy/x64/Release/Minecraft.Client.exe`, sets the working directory to `runtime/legacy/Minecraft.Client`, and passes the supplied client's `1` argument. It retains console errors and client logs. The baseline executable and game assets are supplied binaries, not a newly rebuilt engine. No test worlds or user saves are distributed in this fresh installation.

To use an existing extracted native archive instead, put the launcher and `Legacy-input` folder together and run:

```bat
Launch-Legacy.exe --root "C:\path\to\minecraff2"
```

Existing worlds and the executable stay in place. Known previous input DLLs receive a backup before replacement. An unrecognized input DLL is preserved and installation stops; `--keep-input` uses it unchanged.

## Xbox controls

The adapter forwards connected system XInput controllers, including analog sticks, triggers, capabilities, vibration and enable/disable. It loads an absolute system DLL path. It provides keyboard fallback for controller slot zero when no real controller occupies that slot. Xbox uses the original game's mapping. Physical Xbox hardware is unavailable here; forwarding is verified against a controlled Windows XInput backend under Wine, separately from keyboard/menu/world/HUD/camera/inventory tests in the actual client. The bounded world test closed its owned client with WM_CLOSE and returned code 2138; normal in-game Save and Quit and native save/reload parity are unverified.

Keyboard fallback: Enter/Space = A, Backspace/R = B, Q = X/crafting, E = Y/inventory, WASD = movement, IJKL = look, mouse buttons = triggers, brackets = bumpers, Escape = Start, Tab = Back, arrows = D-pad.

## Decompiled mod source

The earlier source SDK contains 82,175 Java files from the original modpack. The new porting SDK adds 6,342 Java files covering the 8,912 bytecode classes in all 22 readable new uploads. CFR 0.152 coverage found no missing containing source units or hard decompiler failures. Missing-dependency warnings appear in 6,265 source files and control-flow warnings in 27. Source coverage does not establish recompilation or behavioral equivalence.

`pvz_gw_plus-0.8-forge-1.20.1.jar` and `Digimobs-1.1.8d.jar` exceed the upload-download tool's 32 MiB limit and remain unread. They need archive parts no larger than 32 MiB to transfer into this environment.

## Native model work

There are 190 converted supplied Gecko geometry meshes: 16 Halo weapons/projectiles and 174 PvZ plant/zombie/prop models. Conversion preserves signed and fractional cube dimensions, inflation, cube rotation/pivots, bone hierarchy, mirrored faces, fractional/per-face UVs and missing faces. Original texture, geometry and animation resources are retained unmodified with hashes. Utility-library demo models are excluded.

The portable C++ reader and hierarchical pose code compile for Linux and Windows and verify all 190 meshes. `LegacyImportedModel` renders posed quads through the actual Legacy `Tesselator` interface and avoids rounding fractional geometry into integer `ModelPart::addBox` dimensions. Its client-specific subclass has not been compiled or linked here.

`IsaacModModel` ports the supplied Suzu Isaac model's six cuboids, UVs, limb cosine animation and head rotation to the actual Legacy `Model`/`ModelPart` API. Its source texture is `tboi_suzu/textures/entities/isaac.png`. This port is also unlinked. Gecko animation JSON is retained; a native Molang/animation runtime and model-to-entity/texture registration remain necessary.

Halo models are temporary supplied Minecraft-mod artwork, as authorized. PvZ models are assigned to PvZ. The supplied Dragon Ball mod contains Dragon Balls, equipment and textures; it does not supply BT3 NPC combat or a complete BT3 character-model set. Digimobs models cannot be inspected until its oversized upload transfers. Repentance content is not enabled.

## Build and remaining work

In the prepared cloud workspace:

```sh
cd /workspace/decraft
python tools/convert_legacy_models.py
python tools/build_legacy_ports.py
python -m unittest discover -s tests -v
```

The regression suite needs loopback access for its companion-service tests. The Windows launcher, XInput DLL and portable mesh probe build with the retained MinGW toolchain. `native/legacy/LegacyModelPorts.props` is an optional import for the real Minecraft.Client project; it includes the model implementation files but does not register gameplay.

Full engine recompilation requires matching **MSVC v110 / Visual Studio 2012, Windows SDK and MSBuild**, absent from this cloud machine. The supplied successful build logs identify that toolchain. Its Clang project configurations target ORBIS, not Windows. Closed 4J libraries and the existing C++ ABI prevent treating a MinGW helper build as a rebuilt engine.

No supplied Forge mod is fully ported into this native client yet. Forge/NeoForge APIs, mod registration, entity AI, blocks/items, rendering, networking, recipes, world generation and dependencies still need real native implementations. The native Minecraft portal hub, five crossover dimensions, original campaigns and shared progression are not integrated. The earlier Java reference's portal worlds do not transfer automatically to native 4J saves.

See `legacy-mod-port-status.json`, `legacy-model-conversion.json`, `legacy-port-build.json`, the test logs and the development ledger for distinct source/conversion/build/runtime statuses. Work does not continue after the active environment stops.

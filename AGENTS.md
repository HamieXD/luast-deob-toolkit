# Luast Automated Deobfuscation Workspace

This workspace is used to deobfuscate and reconstruct Roblox Lua/Luau scripts obfuscated with Luast (Levels 1, 2, and 3).

The user should not need to supervise individual deobfuscation stages.

When the user says:

    deobfuscate <filename>

perform the ENTIRE workflow automatically from start to finish.

Example:

    deobfuscate CarveWood.lua


# 1. PROJECT STRUCTURE

Use these directories:

    ./Obfuscate script/
        Input obfuscated scripts.

    ./analysis/<script-name>/
        All static-analysis output, runtime reports, temporary files,
        working reconstructions, debug scripts, extracted functions,
        semantic maps, and other intermediate material.

    ./Deobfuscate Script/
        FINAL ready-to-execute deobfuscated scripts only.

Example:

    Obfuscate script/
        CarveWood.lua

    analysis/
        CarveWood/
            AI_HANDOFF.md
            analysis.json
            report.md
            constants.tsv
            permutations.tsv
            working/
            functions/

    Deobfuscate Script/
        CarveWood_deob.lua


# 2. INPUT DISCOVERY

When the user requests:

    deobfuscate CarveWood.lua

automatically locate:

    ./Obfuscate script/CarveWood.lua

unless the user explicitly supplies another path.

Do not ask the user to manually locate files that are already inside `Obfuscate script`.


# 3. STATIC DEOBFUSCATION

Run the local deobfuscation toolkit automatically:

    luast_deob.py

Auto-detect the main constant pool.

Never assume the constant table is named `yM` (it may be `au`, `zp`, `adq`, `aCC`, `xl`, `Ac`, `tN`, etc.).

Generate analysis under:

    ./analysis/<script-name>/

Use the toolkit internally whenever useful, including:

    analyze
    candidates
    deobfuscate
    search
    trace
    refs
    show
    remotes
    perm


# 4. STATIC ANALYSIS GOALS

Automatically identify as much as possible about:

- constant pool
- constant aliases
- permutations (executed sequentially to obtain true runtime values)
- function constants and closures
- string decryption (Types 1-4 stream ciphers and b4 hash inversion)
- UI controls, tabs, groupboxes, toggles, sliders, dropdowns
- setting keys and config tables
- worker loops and coroutines
- delays, thresholds, and filters
- network wrappers and remote calls (FireServer, InvokeServer, Knit services)
- player data keys and workspace objects


# 5. PERMUTATION & CRYPTOGRAPHIC RESOLUTION

Constant-pool initial values are NOT automatically runtime values.
Luast mutates the pool at startup via parallel tuple assignments (`lhs = rhs`).

The deobfuscator executes these permutation statements sequentially to reconstruct the true `runtime_constant_pool`.

For Level 2 and Level 3 scripts:
- Invert the 7-round mixer hash function using `b4_inv(y)`.
- Derive master seeds (`b2`, `b3`) analytically.
- Decrypt all stream cipher payloads (Types 1, 2, 3, and 4) into plaintext.


# 6. AI HANDOFF

Generate:

    ./analysis/<script-name>/AI_HANDOFF.md
    ./analysis/<script-name>/AI_HANDOFF.json

These files summarize:
- discovered features
- UI settings and controls
- worker functions and logic chains
- remote evidence and Knit interfaces
- data/config evidence
- decrypted strings and runtime mappings


# 7. FIDELITY & PRESERVATION POLICY

Preserve the original script's authentic design:
- **Preserve Original UI Framework:** Maintain the original library used (e.g. Orion, Rayfield, Linoria, Obsidian, custom UI).
- **Preserve Original Branding & Titles:** Keep the original window title, hub name, notifications, and metadata as written by the original author.
- **Preserve Original Behavior & Quirks:** Preserve original logic, math operations, and workflow without inventing foreign mechanics.
- **Semantic Code Quality:** Produce clean, readable, well-commented Luau code with meaningful variable names (`getPlayerData`, `autoFarm`, `collectDrops`, `buyUpgrade`).


# 8. OUTPUT POLICY

The folder:

    ./Deobfuscate Script/

is STRICTLY reserved for final ready-to-execute deobfuscated scripts.

Final file naming:

    <original-name>_deob.lua

Example:

    CarveWood.lua -> Deobfuscate Script/CarveWood_deob.lua
    Tapping Simulator.lua -> Deobfuscate Script/Tapping Simulator_deob.lua


# 9. FINAL RESPONSE STYLE

After completing a deobfuscation request, keep the response concise:
- script analyzed
- major systems and remotes recovered
- original UI framework identified
- final ready-to-execute script path

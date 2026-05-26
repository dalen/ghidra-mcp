# Step 2: Rename Function + Set Prototype

## Allowed Tools
- `rename_function_by_address`
- `set_function_prototype`
- `get_function_callers`
- `decompile_function`

## Rename Policy

**Step 2a: Class/prefix decision (MUST do first)**

Before choosing any function name, determine whether it belongs to a C++ class (use `Class__Method` with double underscore) or a module (use `Module__Function`). Check these signals in priority order:

### Priority 1: Vtable membership (strongest signal)

Check if the function's address appears in a known vtable. Use `inspect_memory_content` on known vtable addresses to read the function pointer slots, or check if the function is called via an indirect `CALL dword ptr [EAX + N]` where EAX was loaded from `*(this + 0)`.

**If the function is in a vtable**: name it `ClassName__vmethod_N` (or a descriptive name if the method's purpose is clear), where `ClassName` comes from the vtable's RTTI or the constructor that writes it.

Two RTTI systems exist in WAR.exe:
- **MSVC RTTI**: search for `.?AV<ClassName>@@` strings near the vtable address. Works for all C++ classes with virtual functions.
- **Gamebryo NiRTTI**: for `Ni*` classes, vtable slot 0 is `GetRTTI()` returning a static `NiRTTI` struct (`{pcName, pkBaseRTTI}`). The `pcName` field is the authoritative class name (plain ASCII, e.g. `"NiNode"`). Search for the bare class name string and follow its DATA xrefs to find the NiRTTI struct. See core.md for the struct layout and walkable parent chain.

### Priority 2: `this` pointer / field offsets (strong signal)

If the function operates on `this` (ECX in `__thiscall`, or EAX/EDI-implicit), check what field offsets it accesses. Different classes own different offset ranges:

| Class | Ctor | Vtable | TypeId | Distinctive fields |
|---|---|---|---|---|
| `GameObject` | 0x00431a31 | 0x00A76FD4 | — | +0x00..+0xDC (base fields) |
| `MonsterObject` | 0x00432257 | 0x00A7703C | 3 | +0xFC/+0x17C (equipment arrays), +0x268 (mesh refs), +0x3be..+0x3dc (obf weapon cache) |
| `PlayerObject` | 0x00432ad8 | (inherits Monster) | 2 | extends MonsterObject |
| `StaticObject` | 0x00432f5a | — | 1 | — |

If the function reads/writes fields ONLY in the +0x00..+0xDC range → `GameObject__`. If it touches +0xFC/+0x17C/+0x268 → `MonsterObject__`. Inheritance applies: `PlayerObject` extends `MonsterObject`.

### Priority 3: Caller context / module signals (medium signal)

Check these signals (need at least 2 to apply a prefix):

1. **Source/path hint** -- plate comment `Source:` line, string references pointing to a .cpp file
2. **Core behavior domain** -- function clearly belongs to one system (pathfinding, data tables, skills, etc.)
3. **Callee family** -- majority of called functions share a common prefix or module

If 2+ signals match a known prefix from the Known Module Prefixes table: the name **must** include that prefix.
If signals are mixed or weak: no prefix.

### Critical: Do NOT invent class names

Only use class names that exist in WAR.exe's C++ codebase (confirmed via RTTI strings, constructors, or vtables). Do not create synthetic grouping prefixes like `EquipmentVisual__` or `StringHelper__` — if no real class owns the function, use a module/subsystem prefix (`Entity__`, `Network__`) or no prefix at all. Check RTTI: search for `.?AV<Name>@@` in Ghidra strings before using any class name.

**Step 2b: Choose the full name (prefix + PascalCase verb)**

1. Combine the prefix decision with a descriptive PascalCase name: `DataCollection__LoadFromBlobWar.exe`, `WarStateManager__AddState`
2. If no rename is needed (current name already has correct prefix + accurate description): **SKIP** `rename_function_by_address`.
3. If the name needs changing: call `rename_function_by_address` with the complete prefixed name.

Call rename + prototype in parallel **only when rename is actually needed**. If later tool calls in the same pass need to re-query the function, use its address instead of assuming the new name is available immediately. If rename is skipped, call only `set_function_prototype`.

## Naming Rules

PascalCase, verb-first. Module prefixes (`AbilityLib__`) are allowed.

Valid patterns:
- `GetPlayerHealth`, `ProcessInputEvent`, `ValidateItemSlot` (plain PascalCase)
- `AbilityLib__GetAbilityCastTime`, `OldWorldArmoryData__LoadCsv`, `DataCollection__GetByIndex` (with module prefix)

Invalid patterns:
- `processData` -> `ProcessData` (must be PascalCase)
- `doStuff` -> descriptive name based on actual behavior
- `AbilityLib__getAbilityCastTime` -> `AbilityLib__GetAbilityCastTime` (part after prefix must be PascalCase)

## Verb Specificity Tier (HARD-ENFORCED)

`rename_function_by_address` will REJECT names that fail these rules with a structured error. The model must retry with a better name; the function is unchanged on rejection.

**Tier 1** (specific verbs — accept any specifier):
`Allocate`, `Append`, `Apply`, `Calculate`, `Compile`, `Compress`, `Connect`, `Decode`, `Decompress`, `Decrypt`, `Destroy`, `Detect`, `Encode`, `Encrypt`, `Free`, `Generate`, `Initialize`, `Insert`, `Iterate`, `Lookup`, `Match`, `Merge`, `Parse`, `Render`, `Resolve`, `Schedule`, `Serialize`, `Sort`, `Subscribe`, `Truncate`, `Validate`

**Tier 2** (medium — accept any one specifier):
`Add`, `Build`, `Check`, `Clear`, `Close`, `Compare`, `Copy`, `Count`, `Create`, `Delete`, `Find`, `Format`, `Get`, `Has`, `Is`, `Load`, `Move`, `Open`, `Print`, `Push`, `Pop`, `Read`, `Receive`, `Remove`, `Reset`, `Save`, `Search`, `Send`, `Set`, `Show`, `Start`, `Stop`, `Update`, `Write`

**Tier 3** (vague — REQUIRE ≥2 specifier tokens after the verb):
`Do`, `Handle`, `Make`, `Manage`, `Process`, `Run`, `Use`

**Weak nouns** that DO NOT count as specifiers (they add no information):
`Data`, `Info`, `Stuff`, `Thing`, `Item`, `Object`, `Value`, `Result`, `State`, `Func`, `Method`, `Action`, `Helper`, `Util`

| Name | Verdict | Reason |
|---|---|---|
| `GetSize` | ✅ pass | Tier 2 + 1 specifier (Size) |
| `GetData` | ❌ reject | Tier 2 + 0 specifiers (Data is weak) |
| `ProcessNetworkPacket` | ✅ pass | Tier 3 + 2 specifiers (Network, Packet) |
| `ProcessData` | ❌ reject | Tier 3 + 0 specifiers (Data is weak) |
| `HandleInput` | ❌ reject | Tier 3 + 1 specifier — Tier 3 needs ≥2 |
| `HandleNetworkInput` | ✅ pass | Tier 3 + 2 specifiers |
| `CalculateDamage` | ✅ pass | Tier 1 + 1 specifier |
| `Process` | ❌ reject | Tier 3 + 0 specifiers (no tokens at all) |
| `AbilityLib__GetAbilityCastTime` | ✅ pass | Tier 1 (Compile) + 3 specifiers — prefix doesn't change tier rules |

If your candidate name fails: replace the vague verb with a more specific one OR add concrete specifiers describing what the function operates on.

## No Token-Subset Duplicates (HARD-ENFORCED)

`rename_function_by_address` will REJECT a name that is a strict token-subset (or superset) of another already-named function in the same program — same module-prefix scope. Examples:

| Existing | Candidate | Verdict |
|---|---|---|
| `SendStateUpdateCommand` | `SendStateUpdate` | ❌ reject (candidate ⊂ existing) |
| `SendStateUpdate` | `SendStateUpdateCommand` | ❌ reject (existing ⊂ candidate) |
| `GetItemPrice` | `GetItemValue` | ✅ pass (different last token, neither subset) |
| `ProcessNetworkPacket` | `ProcessLocalPacket` | ✅ pass (Network ≠ Local) |

If the rejection error includes a `conflicts_with` field, do not just suffix `_2` or `New` — add a meaningful distinguisher that captures *why* this function differs from the conflicting one (e.g., `Broadcast`, `Local`, `ByIndex`, `ForPlayer`, `WithRetry`). The rejection's `suggestion` field gives concrete alternatives.

## Handling a Rejection Round-Trip

When `rename_function_by_address` returns `{"status": "rejected", "error": ...}`, the function name was NOT changed. Do not assume the rename succeeded. Read the `message` and `suggestion` fields, pick a better name, and retry. Common rejection codes:
- `vague_verb` — verb is Tier 3 with too few specifiers; add specifiers or pick a Tier 1/2 verb.
- `weak_noun_only` — only weak nouns after the verb; replace with a concrete domain term.
- `missing_specifier` — single-token name; add a specifier.
- `name_collision` / `token_subset_duplicate` — pick a name with a distinguishing token vs `conflicts_with`.

## Prototype Rules

- Use typed struct pointers (`UnitAny *` not `int *`) when the struct is known
- Use Hungarian camelCase for parameter names
- Verify calling convention from disassembly
- Mark implicit register parameters with IMPLICIT keyword in plate comment (Step 4)
- `__thiscall`: first param is `this` in ECX -- do NOT include a typed `this` in the prototype (see Step 3 known limitation)

**Note**: Prototype changes trigger re-decompilation and may create new SSA variables. Step 3 will refresh the variable list by address.

## Caller Verification (required for register params and enums)

Before committing semantic names to these parameter types, you MUST verify against callers:

1. **Register-passed parameters** (`in_EAX`, `in_EDX`, `in_ECX`): Call `get_function_callers` and `decompile_function` on 2-3 callers. Verify what value they pass in that register. Only assign a semantic name if callers confirm the role.
2. **Enum-like parameters** (compared against small integer sets, used in switch/case): Check callers to see what constants they pass. Do not assign names like `nCostMode` or `nVendorId` based solely on how the function uses the value internally.
3. **Flags/booleans**: If a parameter is compared to 0/1/true/false, check callers before naming it `bIsExclusive` vs `bCheckBoxType` -- the caller's context reveals intent.

If callers are unavailable or ambiguous, use conservative names (`nParam1`, `dwParam2`) and note in the plate comment:
```
Parameters:
  nParam3: int - Probable: cost mode (0/1/2 switch observed) -- not verified at call sites
```
